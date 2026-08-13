from __future__ import annotations

import logging
from datetime import datetime, timezone

from hwr_sync.backends import get_backend
from hwr_sync.config import build_ics_url, get_current_semester, load_config, load_overrides
from hwr_sync.diff import compute_diff
from hwr_sync.fetcher import fetch_ics
from hwr_sync.filter import apply_filters, filter_past
from hwr_sync.notify import notify
from hwr_sync.state import load_state, load_user_deleted, save_state

logger = logging.getLogger("hwr_sync")


def sync() -> bool:
    """
    Single sync pass. Returns True if sync ran, False if study period is over.
    """
    config = load_config()
    now = datetime.now(tz=timezone.utc)

    semester = get_current_semester(config, now)
    if semester is None:
        logger.info("Study period complete — sync stopped.")
        return False

    logger.info("Syncing semester %d (%s) ...", semester.number, semester.course)

    # 1. Fetch + filter ICS
    url = build_ics_url(config.faculty, semester.number, semester.course)
    all_events = fetch_ics(url)
    events = filter_past(all_events, now)
    active_filters = semester.filters if semester.filters is not None else config.filters
    events = apply_filters(events, active_filters)

    # 2. Load state, overrides, and previously user-deleted UIDs
    state = load_state()
    overrides = load_overrides()
    user_deleted_uids = load_user_deleted()

    # Skip events the user explicitly deleted (until HWR removes them from ICS too)
    events = [e for e in events if e.uid not in user_deleted_uids]

    # 3. Read current calendar state for all managed UIDs
    backend = get_backend(config)
    calendar = backend.read_managed(set(state.keys()))

    # 4. Compute diff (ICS vs state vs calendar)
    diff = compute_diff(
        incoming=events,
        known=state,
        calendar=calendar,
        overrides=overrides,
    )

    # 5. Apply changes
    new_cal_ids = backend.insert(diff.new)
    backend.update(diff.updated)
    backend.delete(diff.deleted)

    # 6. Build cal_ids map: existing from state + newly inserted
    cal_ids = {uid: m.cal_id for uid, m in state.items()}
    cal_ids.update(new_cal_ids)

    # 6. Handle user changes — accept them, update state accordingly
    if diff.user_deleted:
        uids = {m.uid for m in diff.user_deleted}
        logger.info("Accepted %d deletion(s) you made in the calendar.", len(uids))

    if diff.user_modified:
        logger.info("Accepted %d modification(s) you made in the calendar.", len(diff.user_modified))

    # 7. Conflicts
    if diff.conflicts:
        _handle_conflicts(diff.conflicts)

    # 8. Save new state — include newly user-deleted UIDs persistently
    new_user_deleted = {m.uid for m in diff.user_deleted}
    user_modified_uids = {m.uid for m, _ in diff.user_modified}
    final_events = [e for e in events if e.uid not in new_user_deleted]
    user_modified_map = {m.uid: cal_e for m, cal_e in diff.user_modified}
    final_events = [user_modified_map.get(e.uid, e) for e in final_events]

    save_state(final_events, cal_ids=cal_ids, user_deleted=new_user_deleted)

    logger.info("Sync complete: %s", diff.summary())
    return True


def _handle_conflicts(conflicts) -> None:
    lines = []
    for incoming, managed, cal_event in conflicts:
        if incoming is None:
            lines.append(f"  • '{managed.title}' removed from HWR timetable")
        elif cal_event is None:
            lines.append(f"  • '{managed.title}' changed in HWR timetable but you deleted it")
        else:
            lines.append(f"  • '{managed.title}' changed in both HWR timetable and your calendar")

    msg = "\n".join(lines)
    logger.warning("Conflicts (calendar not changed — review manually):\n%s", msg)
    notify(
        "HWR Sync: Conflicts",
        f"{len(conflicts)} event(s) changed in both HWR and your calendar. Check the log.",
    )
