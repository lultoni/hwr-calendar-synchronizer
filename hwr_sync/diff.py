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
    resolved_uids: set[str] | None = None,
    resolved_edited_uids: set[str] | None = None,
) -> Diff:
    """
    incoming            = filtered ICS events (what HWR says)
    known               = state (what HWR said last sync)
    calendar            = current calendar contents for managed UIDs
    resolved_uids       = UIDs resolved as user_deleted — skip entirely
    resolved_edited_uids = UIDs resolved as user_edited — skip only if still in calendar;
                          if missing from calendar, fall through to normal conflict detection
    """
    diff = Diff()
    incoming_by_uid = {e.uid: e for e in incoming}
    _resolved_deleted = resolved_uids or set()
    _resolved_edited = resolved_edited_uids or set()

    for uid, ics_event in incoming_by_uid.items():
        if uid not in known:
            if uid not in _resolved_deleted and uid not in _resolved_edited:
                diff.new.append(ics_event)
            continue

        managed = known[uid]
        ics_changed = make_hash(ics_event) != managed.event_hash
        in_calendar = uid in calendar

        if not in_calendar:
            if uid in _resolved_deleted:
                # User chose to keep it deleted — honour that
                continue
            # resolved_edited but now gone from calendar: fall through to conflict detection
            if ics_changed:
                diff.hwr_changed_user_deleted.append((ics_event, managed))
            else:
                diff.user_deleted.append((ics_event, managed))
            continue

        cal_event = calendar[uid]
        cal_changed = make_hash(cal_event) != managed.event_hash

        if uid in _resolved_deleted or uid in _resolved_edited:
            # Still in calendar and resolved — treat as unchanged
            diff.unchanged.append(ics_event)
            continue

        if not ics_changed and not cal_changed:
            diff.unchanged.append(ics_event)
        elif ics_changed and not cal_changed:
            diff.updated.append(ics_event)
        elif not ics_changed and cal_changed:
            diff.user_modified.append((ics_event, managed, cal_event))
        else:
            diff.both_changed.append((ics_event, managed, cal_event))

    # ICS removed an event that's still in state
    for uid, managed in known.items():
        if uid not in incoming_by_uid:
            if uid in calendar:
                diff.deleted.append(managed)
            # if not in calendar either: already gone, just falls out of state

    return diff
