from __future__ import annotations

from abc import ABC, abstractmethod

from hwr_sync.fetcher import CalEvent
from hwr_sync.state import ManagedEvent


class CalendarBackend(ABC):
    @abstractmethod
    def insert(self, events: list[CalEvent]) -> None: ...

    @abstractmethod
    def update(self, events: list[CalEvent]) -> None: ...

    @abstractmethod
    def delete(self, events: list[ManagedEvent]) -> None: ...
