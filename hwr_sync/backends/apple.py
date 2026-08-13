from __future__ import annotations

import threading
from datetime import datetime, timezone

from hwr_sync.backends.base import CalendarBackend
from hwr_sync.fetcher import CalEvent
from hwr_sync.state import ManagedEvent


class AppleCalendarBackend(CalendarBackend):
    """Uses pyobjc EventKit to write directly to Apple Calendar (macOS only)."""

    def __init__(self, calendar_name: str) -> None:
        try:
            import EventKit  # type: ignore
        except ImportError:
            raise ImportError(
                "pyobjc-framework-EventKit is required for the Apple Calendar backend.\n"
                "Install it with: uv tool install -e '.[apple]'"
            )
        self._ek = EventKit
        self._store = EventKit.EKEventStore.alloc().init()
        self._request_access()
        self._calendar = self._get_or_raise(calendar_name)

    def _request_access(self) -> None:
        done = threading.Event()
        result = {"granted": False}

        def handler(granted, error):
            result["granted"] = granted
            done.set()

        self._store.requestFullAccessToEventsWithCompletion_(handler)
        done.wait(timeout=10)

        if not result["granted"]:
            raise PermissionError(
                "Apple Calendar access denied.\n"
                "Go to System Settings → Privacy & Security → Calendars "
                "and allow access for Terminal (or your app)."
            )

    def _get_or_raise(self, name: str):
        calendars = self._store.calendarsForEntityType_(0)
        for cal in calendars:
            if cal.title() == name:
                return cal
        available = [c.title() for c in calendars]
        raise ValueError(
            f"Calendar '{name}' not found in Apple Calendar.\n"
            f"Available calendars: {available}\n"
            "Create it in Apple Calendar first, then update calendar_name in config.yaml."
        )

    def read_managed(self, uids: set[str]) -> dict[str, CalEvent]:
        """Look up managed events by their stored calendarItemIdentifier."""
        found: dict[str, CalEvent] = {}
        from hwr_sync.state import load_state

        state = load_state()
        for uid in uids:
            managed = state.get(uid)
            if not managed or not managed.cal_id:
                continue
            ev = self._store.calendarItemWithIdentifier_(managed.cal_id)
            if ev is None:
                continue  # deleted by user
            found[uid] = CalEvent(
                uid=uid,
                title=str(ev.title() or ""),
                start=_nsdate_to_datetime(ev.startDate()),
                end=_nsdate_to_datetime(ev.endDate()),
                location=str(ev.location() or ""),
                description=str(ev.notes() or ""),
            )
        return found

    def insert(self, events: list[CalEvent]) -> dict[str, str]:
        """Insert events and return {uid: cal_id} for state storage."""
        cal_ids: dict[str, str] = {}
        for e in events:
            ek_event = self._ek.EKEvent.eventWithEventStore_(self._store)
            _populate(ek_event, e)
            ek_event.setCalendar_(self._calendar)
            ok, err = self._store.saveEvent_span_commit_error_(ek_event, 0, True, None)
            if not ok:
                raise RuntimeError(f"Failed to save event '{e.title}': {err}")
            cal_ids[e.uid] = str(ek_event.calendarItemIdentifier())
        return cal_ids

    def update(self, events: list[CalEvent]) -> None:
        from hwr_sync.state import load_state
        state = load_state()
        for e in events:
            managed = state.get(e.uid)
            ev = None
            if managed and managed.cal_id:
                ev = self._store.calendarItemWithIdentifier_(managed.cal_id)
            if ev:
                _populate(ev, e)
                self._store.saveEvent_span_commit_error_(ev, 0, True, None)
            else:
                self.insert([e])

    def delete(self, events: list[ManagedEvent]) -> None:
        for e in events:
            if not e.cal_id:
                continue
            ev = self._store.calendarItemWithIdentifier_(e.cal_id)
            if ev:
                self._store.removeEvent_span_commit_error_(ev, 0, True, None)


def _populate(ek_event, e: CalEvent) -> None:
    ek_event.setTitle_(e.title)
    ek_event.setLocation_(e.location or "")
    ek_event.setNotes_(e.description or "")
    ek_event.setStartDate_(_to_nsdate(e.start))
    ek_event.setEndDate_(_to_nsdate(e.end))


def _nsdate_to_datetime(nsdate) -> datetime:
    return datetime.fromtimestamp(float(nsdate.timeIntervalSince1970()), tz=timezone.utc)


def _to_nsdate(dt):
    import Foundation  # type: ignore
    return Foundation.NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())


def _ns_date_far_past():
    import Foundation  # type: ignore
    return Foundation.NSDate.dateWithTimeIntervalSince1970_(0)


def _ns_date_far_future():
    import Foundation  # type: ignore
    return Foundation.NSDate.dateWithTimeIntervalSince1970_(9999999999)
