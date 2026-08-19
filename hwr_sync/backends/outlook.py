from __future__ import annotations

import json
import sys
from datetime import timezone
from pathlib import Path

import requests

from hwr_sync.backends.base import CalendarBackend
from hwr_sync.config import CONFIG_DIR
from hwr_sync.fetcher import CalEvent
from hwr_sync.state import ManagedEvent, STATE_PATH

GRAPH = "https://graph.microsoft.com/v1.0"
TOKEN_CACHE_PATH = CONFIG_DIR / "outlook_token_cache.bin"

# App-specific GUID for storing the ICS UID as a singleValueExtendedProperty.
# Fixed constant — must never change once events are written.
_UID_PROP = "String {3e3b8b26-17f3-4e8e-b8b8-1a2b3c4d5e6f} Name hwr_uid"


class OutlookCalendarBackend(CalendarBackend):
    """Microsoft Graph backend — writes to a named Outlook/Teams calendar."""

    def __init__(
        self,
        calendar_name: str,
        client_id: str,
        tenant_id: str,
        create_missing_calendar: bool = False,
        state_path: Path = STATE_PATH,
    ) -> None:
        try:
            import msal  # type: ignore
        except ImportError:
            raise ImportError(
                "msal is required for the Outlook backend.\n"
                "Install it with: uv tool install -e '.[outlook]'"
            )
        self._msal = msal
        self._client_id = client_id
        self._tenant_id = tenant_id
        self._state_path = state_path
        self._token: str = self._get_token()
        self._calendar_id: str = self._resolve_calendar(calendar_name, create_missing_calendar)

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _get_token(self) -> str:
        cache = self._msal.SerializableTokenCache()
        if TOKEN_CACHE_PATH.exists():
            cache.deserialize(TOKEN_CACHE_PATH.read_text())

        app = self._msal.PublicClientApplication(
            self._client_id,
            authority=f"https://login.microsoftonline.com/{self._tenant_id}",
            token_cache=cache,
        )

        scopes = ["Calendars.ReadWrite"]
        result = None
        accounts = app.get_accounts()
        if accounts:
            result = app.acquire_token_silent(scopes, account=accounts[0])

        if not result:
            flow = app.initiate_device_flow(scopes=scopes)
            if "user_code" not in flow:
                raise RuntimeError(f"Device flow failed: {flow.get('error_description')}")
            print(f"\n[hwr-sync] Outlook login required:\n{flow['message']}\n")
            result = app.acquire_token_by_device_flow(flow)

        if cache.has_state_changed:
            TOKEN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            TOKEN_CACHE_PATH.write_text(cache.serialize())

        if "access_token" not in result:
            raise RuntimeError(
                f"Outlook auth failed: {result.get('error_description', result)}"
            )
        return result["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Calendar resolution
    # ------------------------------------------------------------------

    def _resolve_calendar(self, name: str, create_if_missing: bool) -> str:
        r = requests.get(f"{GRAPH}/me/calendars", headers=self._headers())
        r.raise_for_status()
        calendars = {c["name"]: c["id"] for c in r.json().get("value", [])}

        if name in calendars:
            return calendars[name]

        available = "\n".join(f"  - {n}" for n in sorted(calendars))
        if create_if_missing:
            return self._create_calendar(name)

        import click
        click.echo(
            f"\nCalendar '{name}' not found in Outlook.\n"
            f"Available calendars:\n{available}\n"
        )
        if click.confirm(f"Create calendar '{name}' now?", default=True):
            return self._create_calendar(name)

        click.echo(
            f"\nCreate a calendar named '{name}' in Outlook, "
            "then run `hwr-sync run` again.\n"
            "Or update calendar_name in your config: `hwr-sync settings`"
        )
        sys.exit(1)

    def _create_calendar(self, name: str) -> str:
        r = requests.post(
            f"{GRAPH}/me/calendars",
            headers=self._headers(),
            json={"name": name},
        )
        r.raise_for_status()
        cal_id = r.json()["id"]
        print(f"[hwr-sync] Created calendar '{name}' in Outlook.")
        return cal_id

    # ------------------------------------------------------------------
    # CalendarBackend implementation
    # ------------------------------------------------------------------

    def read_managed(self, uids: set[str]) -> dict[str, CalEvent]:
        found: dict[str, CalEvent] = {}
        from hwr_sync.state import load_state

        state = load_state(self._state_path)
        for uid in uids:
            managed = state.get(uid)
            if not managed or not managed.cal_id:
                continue
            ev = self._get_event(managed.cal_id)
            if ev is None:
                continue
            found[uid] = _graph_event_to_cal_event(uid, ev)
        return found

    def insert(self, events: list[CalEvent]) -> dict[str, str]:
        cal_ids: dict[str, str] = {}
        for e in events:
            body = _cal_event_to_body(e)
            body["singleValueExtendedProperties"] = [
                {"id": _UID_PROP, "value": e.uid}
            ]
            r = requests.post(
                f"{GRAPH}/me/calendars/{self._calendar_id}/events",
                headers=self._headers(),
                json=body,
            )
            r.raise_for_status()
            cal_ids[e.uid] = r.json()["id"]
        return cal_ids

    def update(self, events: list[CalEvent]) -> None:
        from hwr_sync.state import load_state

        state = load_state(self._state_path)
        for e in events:
            managed = state.get(e.uid)
            if not managed or not managed.cal_id:
                self.insert([e])
                continue
            r = requests.patch(
                f"{GRAPH}/me/events/{managed.cal_id}",
                headers=self._headers(),
                json=_cal_event_to_body(e),
            )
            if r.status_code == 404:
                self.insert([e])
            else:
                r.raise_for_status()

    def delete(self, events: list[ManagedEvent]) -> None:
        for e in events:
            if not e.cal_id:
                continue
            r = requests.delete(
                f"{GRAPH}/me/events/{e.cal_id}",
                headers=self._headers(),
            )
            if r.status_code not in (204, 404):
                r.raise_for_status()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_event(self, event_id: str) -> dict | None:
        r = requests.get(
            f"{GRAPH}/me/events/{event_id}"
            "?$select=id,subject,start,end,location",
            headers=self._headers(),
        )
        if r.status_code in (400, 404):
            return None
        r.raise_for_status()
        return r.json()


# ------------------------------------------------------------------
# Conversion helpers
# ------------------------------------------------------------------

def _cal_event_to_body(e: CalEvent) -> dict:
    return {
        "subject": e.title,
        "start": {
            "dateTime": e.start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
            "timeZone": "UTC",
        },
        "end": {
            "dateTime": e.end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
            "timeZone": "UTC",
        },
        "location": {"displayName": e.location or ""},
        "body": {"contentType": "text", "content": e.description or ""},
    }


def _graph_event_to_cal_event(uid: str, ev: dict) -> CalEvent:
    from datetime import datetime

    def _parse_dt(dt_obj: dict) -> datetime:
        dt_str = dt_obj["dateTime"]
        # Graph returns ISO-like strings without Z; timeZone is separate
        tz_name = dt_obj.get("timeZone", "UTC")
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            if tz_name == "UTC":
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                try:
                    from zoneinfo import ZoneInfo
                    dt = dt.replace(tzinfo=ZoneInfo(tz_name))
                except Exception:
                    dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    return CalEvent(
        uid=uid,
        title=ev.get("subject", ""),
        start=_parse_dt(ev["start"]),
        end=_parse_dt(ev["end"]),
        location=(ev.get("location") or {}).get("displayName", ""),
        description=(ev.get("body") or {}).get("content", ""),
    )
