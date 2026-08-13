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
    # Divergences between calendar and ICS-state — go to conflicts.json
    user_deleted: list[tuple[CalEvent, ManagedEvent]] = field(default_factory=list)
    user_modified: list[tuple[CalEvent, ManagedEvent, CalEvent]] = field(default_factory=list)
    both_changed: list[tuple[CalEvent, ManagedEvent, CalEvent]] = field(default_factory=list)
    hwr_changed_user_deleted: list[tuple[CalEvent, ManagedEvent]] = field(default_factory=list)

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
        divergences = (len(self.user_deleted) + len(self.user_modified) +
                       len(self.both_changed) + len(self.hwr_changed_user_deleted))
        if divergences:
            parts.append(f"{divergences} conflict(s) — run `hwr-sync conflicts`")
        return ", ".join(parts) if parts else "nothing to do"


def compute_diff(
    incoming: list[CalEvent],
    known: dict[str, ManagedEvent],
    calendar: dict[str, CalEvent],
) -> Diff:
    """
    incoming  = filtered ICS events (what HWR says)
    known     = state (what HWR said last sync)
    calendar  = current calendar contents for managed UIDs
    """
    diff = Diff()
    incoming_by_uid = {e.uid: e for e in incoming}

    for uid, ics_event in incoming_by_uid.items():
        if uid not in known:
            diff.new.append(ics_event)
            continue

        managed = known[uid]
        ics_changed = make_hash(ics_event) != managed.event_hash
        in_calendar = uid in calendar

        if not in_calendar:
            if ics_changed:
                # HWR changed it AND user deleted it → conflict
                diff.hwr_changed_user_deleted.append((ics_event, managed))
            else:
                # HWR unchanged, user deleted → notify, don't re-insert
                diff.user_deleted.append((ics_event, managed))
            continue

        cal_event = calendar[uid]
        cal_changed = make_hash(cal_event) != managed.event_hash

        if not ics_changed and not cal_changed:
            diff.unchanged.append(ics_event)
        elif ics_changed and not cal_changed:
            diff.updated.append(ics_event)
        elif not ics_changed and cal_changed:
            # User modified, HWR unchanged → notify, respect user's version
            diff.user_modified.append((ics_event, managed, cal_event))
        else:
            # Both changed → conflict
            diff.both_changed.append((ics_event, managed, cal_event))

    # ICS removed an event that's still in state
    for uid, managed in known.items():
        if uid not in incoming_by_uid:
            if uid in calendar:
                diff.deleted.append(managed)
            # if not in calendar either: already gone, just falls out of state

    return diff
