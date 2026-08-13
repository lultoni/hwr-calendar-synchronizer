from __future__ import annotations

from dataclasses import dataclass, field

from hwr_sync.fetcher import CalEvent
from hwr_sync.state import ManagedEvent, make_hash


@dataclass
class Diff:
    new: list[CalEvent] = field(default_factory=list)
    updated: list[CalEvent] = field(default_factory=list)
    deleted: list[ManagedEvent] = field(default_factory=list)
    unchanged: list[CalEvent] = field(default_factory=list)
    conflicts: list[tuple[CalEvent | None, ManagedEvent]] = field(default_factory=list)

    def summary(self) -> str:
        parts = []
        if self.new:
            parts.append(f"{len(self.new)} added")
        if self.updated:
            parts.append(f"{len(self.updated)} updated")
        if self.deleted:
            parts.append(f"{len(self.deleted)} deleted")
        if self.unchanged:
            parts.append(f"{len(self.unchanged)} unchanged")
        if self.conflicts:
            parts.append(f"{len(self.conflicts)} conflicts (check log)")
        return ", ".join(parts) if parts else "nothing to do"


def compute_diff(
    incoming: list[CalEvent],
    known: dict[str, ManagedEvent],
    overrides: dict,
) -> Diff:
    diff = Diff()
    incoming_by_uid = {e.uid: e for e in incoming}

    # Check each incoming event against known state
    for uid, event in incoming_by_uid.items():
        if uid not in known:
            diff.new.append(event)
            continue

        current_hash = make_hash(event)
        stored_hash = known[uid].event_hash

        if current_hash == stored_hash:
            diff.unchanged.append(event)
        elif uid in overrides:
            diff.conflicts.append((event, known[uid]))
        else:
            diff.updated.append(event)

    # Check known events that are no longer in the ICS
    for uid, managed in known.items():
        if uid not in incoming_by_uid:
            if uid in overrides:
                diff.conflicts.append((None, managed))
            else:
                diff.deleted.append(managed)

    return diff
