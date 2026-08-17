from __future__ import annotations

import logging
from datetime import datetime, timezone

from hwr_sync.backends import get_backend
from hwr_sync.config import build_ics_url, get_current_semester, load_config
from hwr_sync.conflicts import (
    Conflict,
    STATUS_OPEN,
    STATUS_RESOLVED_USER_DELETED,
    STATUS_RESOLVED_USER_EDITED,
    add_conflicts,
    load_conflicts,
    save_conflicts,
)
from hwr_sync.diff import compute_diff
from hwr_sync.fetcher import fetch_ics
from hwr_sync.filter import apply_filters, filter_past
from hwr_sync.notify import notify
from hwr_sync.state import load_state, make_hash, save_state

logger = logging.getLogger("hwr_sync")


def sync(emit_notifications: bool = True, create_missing_calendar: bool = False) -> bool:
    """Single sync pass. Returns True if sync ran, False if study period is over."""
    config = load_config()
    now = datetime.now(tz=timezone.utc)

    semester = get_current_semester(config, now)
    if semester is None:
        logger.info("Study period complete — sync stopped.")
        return False

    logger.info("Syncing semester %d (%s) ...", semester.number, semester.course)

    # 1. Fetch + filter ICS (= what HWR currently says)
    url = build_ics_url(config.faculty, semester.number, semester.course)
    all_events = fetch_ics(url)
    events = filter_past(all_events, now)
    active_filters = semester.filters if semester.filters is not None else config.filters
    events = apply_filters(events, active_filters)

    # 2. Load state (= what HWR said last sync)
    #    Drop past events silently — they fell out of the ICS naturally and
    #    must not be deleted from the calendar by the diff.
    state = load_state()
    state = {
        uid: m for uid, m in state.items()
        if datetime.fromisoformat(m.end) >= now
        or uid in {e.uid for e in events}
    }

    # 3. Read current calendar state for all managed UIDs
    backend = get_backend(config, create_missing_calendar=create_missing_calendar)
    calendar = backend.read_managed(set(state.keys()))

    # 4. Re-open resolved_user_edited conflicts whose event is no longer in the calendar
    all_conflicts = load_conflicts()
    reopened = False
    for c in all_conflicts:
        if c.status == STATUS_RESOLVED_USER_EDITED and c.uid not in calendar:
            c.status = STATUS_OPEN
            # Clear stale cal_* fields — event is gone, showing old edit data would confuse the user
            c.cal_title = ""
            c.cal_start = ""
            c.cal_end = ""
            c.cal_location = ""
            c.kind = "user_deleted"
            reopened = True
    if reopened:
        save_conflicts(all_conflicts)

    # 5. Build resolved UID sets for diff
    resolved_deleted_uids = {c.uid for c in all_conflicts if c.status == STATUS_RESOLVED_USER_DELETED}
    resolved_edited_uids = {c.uid for c in all_conflicts if c.status == STATUS_RESOLVED_USER_EDITED}

    # 6. Diff: ICS vs state vs calendar
    diff = compute_diff(
        incoming=events,
        known=state,
        calendar=calendar,
        resolved_uids=resolved_deleted_uids,
        resolved_edited_uids=resolved_edited_uids,
    )

    # 7. Apply clean changes
    new_cal_ids = backend.insert(diff.new)
    backend.update(diff.updated)
    backend.delete(diff.deleted)

    # 8. Collect cal_ids for state (existing + newly inserted)
    cal_ids = {uid: m.cal_id for uid, m in state.items()}
    cal_ids.update(new_cal_ids)

    # 9. Save state = ICS stand (all incoming events we manage)
    save_state(events, cal_ids=cal_ids)

    # 10. Record divergences as conflicts for user to resolve
    new_conflicts: list[Conflict] = []

    for ics_event, managed in diff.user_deleted:
        new_conflicts.append(Conflict(
            uid=ics_event.uid,
            kind="user_deleted",
            title=ics_event.title,
            ics_title=ics_event.title,
            ics_start=ics_event.start.isoformat(),
            ics_end=ics_event.end.isoformat(),
            ics_location=ics_event.location,
            cal_title="",
            cal_start="",
            cal_end="",
            cal_location="",
            cal_id=managed.cal_id,
            ics_hash=make_hash(ics_event),
        ))

    for ics_event, managed, cal_event in diff.user_modified:
        new_conflicts.append(Conflict(
            uid=ics_event.uid,
            kind="user_modified",
            title=ics_event.title,
            ics_title=ics_event.title,
            ics_start=ics_event.start.isoformat(),
            ics_end=ics_event.end.isoformat(),
            ics_location=ics_event.location,
            cal_title=cal_event.title,
            cal_start=cal_event.start.isoformat(),
            cal_end=cal_event.end.isoformat(),
            cal_location=cal_event.location,
            cal_id=managed.cal_id,
            ics_hash=make_hash(ics_event),
        ))

    for ics_event, managed, cal_event in diff.both_changed:
        new_conflicts.append(Conflict(
            uid=ics_event.uid,
            kind="both_changed",
            title=ics_event.title,
            ics_title=ics_event.title,
            ics_start=ics_event.start.isoformat(),
            ics_end=ics_event.end.isoformat(),
            ics_location=ics_event.location,
            cal_title=cal_event.title,
            cal_start=cal_event.start.isoformat(),
            cal_end=cal_event.end.isoformat(),
            cal_location=cal_event.location,
            cal_id=managed.cal_id,
            ics_hash=make_hash(ics_event),
        ))

    for ics_event, managed in diff.hwr_changed_user_deleted:
        new_conflicts.append(Conflict(
            uid=ics_event.uid,
            kind="hwr_changed_user_deleted",
            title=ics_event.title,
            ics_title=ics_event.title,
            ics_start=ics_event.start.isoformat(),
            ics_end=ics_event.end.isoformat(),
            ics_location=ics_event.location,
            cal_title="",
            cal_start="",
            cal_end="",
            cal_location="",
            cal_id=managed.cal_id,
            ics_hash=make_hash(ics_event),
        ))

    if new_conflicts:
        add_conflicts(new_conflicts)

    # Count open conflicts (includes newly re-opened ones) for notifications
    from hwr_sync.conflicts import open_conflicts
    open_count = len(open_conflicts())
    if open_count:
        logger.warning("%d open conflict(s) — run `hwr-sync conflicts` to review.", open_count)
        if emit_notifications:
            notify(
                "HWR Sync: Conflicts",
                f"{open_count} conflict(s) found — run `hwr-sync conflicts` to review.",
            )

    logger.info("Sync complete: %s", diff.summary())
    return True
