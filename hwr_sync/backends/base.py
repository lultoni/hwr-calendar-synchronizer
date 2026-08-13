from __future__ import annotations

from abc import ABC, abstractmethod

from hwr_sync.fetcher import CalEvent
from hwr_sync.state import ManagedEvent


class CalendarBackend(ABC):
    @abstractmethod
    def read_managed(self, uids: set[str]) -> dict[str, CalEvent]:
        """Read events by UID from the calendar. Returns only UIDs that exist."""
        ...

    @abstractmethod
    def insert(self, events: list[CalEvent]) -> dict[str, str]:
        """Insert events. Returns {uid: cal_id} for state storage."""
        ...

    @abstractmethod
    def update(self, events: list[CalEvent]) -> None: ...

    @abstractmethod
    def delete(self, events: list[ManagedEvent]) -> None: ...
