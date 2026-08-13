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
    # (incoming_ics_event_or_None, managed_state, user_cal_event_or_None)
    conflicts: list[tuple[CalEvent | None, ManagedEvent, CalEvent | None]] = field(default_factory=list)
    # User deleted or modified in calendar — accepted, removed from state
    user_deleted: list[ManagedEvent] = field(default_factory=list)
    user_modified: list[tuple[ManagedEvent, CalEvent]] = field(default_factory=list)

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
        if self.user_deleted:
            parts.append(f"{len(self.user_deleted)} removed by you")
        if self.user_modified:
            parts.append(f"{len(self.user_modified)} modified by you")
        if self.conflicts:
            parts.append(f"{len(self.conflicts)} conflicts (check log)")
        return ", ".join(parts) if parts else "nothing to do"


def compute_diff(
    incoming: list[CalEvent],
    known: dict[str, ManagedEvent],
    calendar: dict[str, CalEvent],  # current state of managed events in the calendar
    overrides: dict,
) -> Diff:
    diff = Diff()
    incoming_by_uid = {e.uid: e for e in incoming}

    for uid, event in incoming_by_uid.items():
        if uid not in known:
            # New event from ICS — not yet in calendar
            diff.new.append(event)
            continue

        managed = known[uid]
        ics_changed = make_hash(event) != managed.event_hash
        in_calendar = uid in calendar

        if not in_calendar:
            # User deleted this event from the calendar
            if ics_changed:
                # ICS also changed — conflict: HWR updated an event user deleted
                diff.conflicts.append((event, managed, None))
            else:
                # ICS unchanged, user deleted → respect user's choice
                diff.user_deleted.append(managed)
            continue

        cal_event = calendar[uid]
        cal_changed = make_hash(cal_event) != managed.event_hash

        if not ics_changed and not cal_changed:
            diff.unchanged.append(event)
        elif ics_changed and not cal_changed:
            # HWR changed, user didn't → update calendar
            diff.updated.append(event)
        elif not ics_changed and cal_changed:
            # User modified in calendar, ICS unchanged → respect user's change
            diff.user_modified.append((managed, cal_event))
        else:
            # Both ICS and user changed → conflict
            diff.conflicts.append((event, managed, cal_event))

    # Events in state but no longer in ICS (and not past)
    for uid, managed in known.items():
        if uid not in incoming_by_uid:
            if uid not in calendar:
                # Already gone from calendar too — just clean up state
                diff.user_deleted.append(managed)
            else:
                # Still in calendar, ICS removed it → delete
                diff.deleted.append(managed)

    return diff
