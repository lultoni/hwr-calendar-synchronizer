from __future__ import annotations

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
                "Install it with: uv pip install 'hwr-calendar-synchronizer[apple]'"
            )
        self._ek = EventKit
        self._store = EventKit.EKEventStore.alloc().init()
        self._calendar = self._get_or_raise(calendar_name)

    def _get_or_raise(self, name: str):
        calendars = self._store.calendarsForEntityType_(0)  # EKEntityTypeEvent = 0
        for cal in calendars:
            if cal.title() == name:
                return cal
        available = [c.title() for c in calendars]
        raise ValueError(
            f"Calendar '{name}' not found in Apple Calendar.\n"
            f"Available calendars: {available}\n"
            "Create it in Apple Calendar first, then update calendar_name in config.yaml."
        )

    def insert(self, events: list[CalEvent]) -> None:
        for e in events:
            ek_event = self._ek.EKEvent.eventWithEventStore_(self._store)
            _populate(ek_event, e)
            ek_event.setCalendar_(self._calendar)
            self._store.saveEvent_span_error_(ek_event, 0, None)

    def update(self, events: list[CalEvent]) -> None:
        for e in events:
            existing = self._find_by_uid(e.uid)
            if existing:
                _populate(existing, e)
                self._store.saveEvent_span_error_(existing, 0, None)
            else:
                self.insert([e])

    def delete(self, events: list[ManagedEvent]) -> None:
        for e in events:
            existing = self._find_by_uid(e.uid)
            if existing:
                self._store.removeEvent_span_error_(existing, 0, None)

    def _find_by_uid(self, uid: str):
        import objc  # type: ignore
        predicate = self._store.predicateForEventsWithStartDate_endDate_calendars_(
            _ns_date_far_past(), _ns_date_far_future(), [self._calendar]
        )
        all_events = self._store.eventsMatchingPredicate_(predicate)
        for ev in all_events:
            if ev.notes() and uid in str(ev.notes()):
                return ev
        return None


def _populate(ek_event, e: CalEvent) -> None:
    import Foundation  # type: ignore

    ek_event.setTitle_(e.title)
    ek_event.setLocation_(e.location or "")
    # Store UID in notes for later lookup (EventKit has no custom UID field)
    ek_event.setNotes_(f"[hwr-sync:{e.uid}]\n{e.description}".strip())
    ek_event.setStartDate_(_to_nsdate(e.start))
    ek_event.setEndDate_(_to_nsdate(e.end))


def _to_nsdate(dt):
    import Foundation  # type: ignore
    return Foundation.NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())


def _ns_date_far_past():
    import Foundation  # type: ignore
    return Foundation.NSDate.dateWithTimeIntervalSince1970_(0)


def _ns_date_far_future():
    import Foundation  # type: ignore
    return Foundation.NSDate.dateWithTimeIntervalSince1970_(9999999999)
