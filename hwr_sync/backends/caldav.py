from __future__ import annotations

from datetime import timezone

import caldav  # type: ignore
from icalendar import Calendar, Event, vText

from hwr_sync.backends.base import CalendarBackend
from hwr_sync.fetcher import CalEvent
from hwr_sync.state import ManagedEvent


class CalDAVBackend(CalendarBackend):
    def __init__(self, url: str, calendar_name: str) -> None:
        client = caldav.DAVClient(url)
        principal = client.principal()
        calendars = principal.calendars()
        match = next((c for c in calendars if c.name == calendar_name), None)
        if match is None:
            available = [c.name for c in calendars]
            raise ValueError(
                f"Calendar '{calendar_name}' not found on CalDAV server.\n"
                f"Available: {available}"
            )
        self._cal = match

    def read_managed(self, uids: set[str]) -> dict[str, CalEvent]:
        from hwr_sync.fetcher import _parse_ics
        from pathlib import Path
        import tempfile, uuid as _uuid

        found: dict[str, CalEvent] = {}
        for uid in uids:
            try:
                event = self._cal.event_by_uid(uid)
                tmp = Path(tempfile.gettempdir()) / f"hwr_sync_{_uuid.uuid4().hex}.ics"
                tmp.write_bytes(event.data)
                events = _parse_ics(tmp)
                tmp.unlink()
                if events:
                    found[uid] = events[0]
            except Exception:
                pass
        return found

    def insert(self, events: list[CalEvent]) -> dict[str, str]:
        for e in events:
            self._cal.save_event(_to_ical(e))
        return {e.uid: e.uid for e in events}  # CalDAV uses UID natively

    def update(self, events: list[CalEvent]) -> None:
        for e in events:
            try:
                event = self._cal.event_by_uid(e.uid)
                event.icalendar_component["SUMMARY"] = vText(e.title)
                event.icalendar_component["LOCATION"] = vText(e.location)
                event.icalendar_component["DESCRIPTION"] = vText(e.description)
                event.save()
            except caldav.error.NotFoundError:
                self.insert([e])

    def delete(self, events: list[ManagedEvent]) -> None:
        for e in events:
            try:
                event = self._cal.event_by_uid(e.uid)
                event.delete()
            except caldav.error.NotFoundError:
                pass


def _to_ical(e: CalEvent) -> str:
    cal = Calendar()
    cal.add("prodid", "-//hwr-calendar-synchronizer//EN")
    cal.add("version", "2.0")

    event = Event()
    event.add("uid", e.uid)
    event.add("summary", e.title)
    event.add("dtstart", e.start.astimezone(timezone.utc))
    event.add("dtend", e.end.astimezone(timezone.utc))
    event.add("location", e.location)
    event.add("description", e.description)
    cal.add_component(event)

    return cal.to_ical().decode()
