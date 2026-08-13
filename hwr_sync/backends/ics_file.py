from __future__ import annotations

from datetime import timezone
from pathlib import Path

from icalendar import Calendar, Event

from hwr_sync.backends.base import CalendarBackend
from hwr_sync.fetcher import CalEvent
from hwr_sync.state import ManagedEvent

DEFAULT_OUTPUT = Path("hwr_schedule.ics")


class ICSFileBackend(CalendarBackend):
    """
    Writes a static .ics file that can be subscribed to in any calendar app.
    Read-only from the calendar's perspective — no overrides applied here.
    """

    def __init__(self, output_path: Path = DEFAULT_OUTPUT) -> None:
        self._path = output_path
        self._events: dict[str, CalEvent] = {}
        if output_path.exists():
            self._load_existing()

    def _load_existing(self) -> None:
        from hwr_sync.fetcher import _parse_ics
        for e in _parse_ics(self._path):
            self._events[e.uid] = e

    def read_managed(self, uids: set[str]) -> dict[str, CalEvent]:
        return {uid: e for uid, e in self._events.items() if uid in uids}

    def insert(self, events: list[CalEvent]) -> dict[str, str]:
        for e in events:
            self._events[e.uid] = e
        self._write()
        return {e.uid: e.uid for e in events}

    def update(self, events: list[CalEvent]) -> None:
        for e in events:
            self._events[e.uid] = e
        self._write()

    def delete(self, events: list[ManagedEvent]) -> None:
        for e in events:
            self._events.pop(e.uid, None)
        self._write()

    def _write(self) -> None:
        cal = Calendar()
        cal.add("prodid", "-//hwr-calendar-synchronizer//EN")
        cal.add("version", "2.0")
        cal.add("x-wr-calname", "HWR Stundenplan")

        for e in self._events.values():
            component = Event()
            component.add("uid", e.uid)
            component.add("summary", e.title)
            component.add("dtstart", e.start.astimezone(timezone.utc))
            component.add("dtend", e.end.astimezone(timezone.utc))
            component.add("location", e.location)
            component.add("description", e.description)
            cal.add_component(component)

        self._path.write_bytes(cal.to_ical())
