from __future__ import annotations

import logging
from datetime import datetime, timezone

from hwr_sync.backends import get_backend
from hwr_sync.config import build_ics_url, get_current_semester, load_config, load_overrides
from hwr_sync.diff import compute_diff
from hwr_sync.fetcher import fetch_ics
from hwr_sync.filter import apply_filters, filter_past
from hwr_sync.notify import notify
from hwr_sync.state import load_state, save_state

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

    logger.info(
        "Syncing semester %d (%s) ...", semester.number, semester.course
    )

    url = build_ics_url(config.faculty, semester.number, semester.course)
    all_events = fetch_ics(url)

    events = filter_past(all_events, now)
    events = apply_filters(events, config.filters)

    state = load_state()
    overrides = load_overrides()

    diff = compute_diff(
        incoming=events,
        known=state,
        overrides=overrides,
    )

    backend = get_backend(config)
    backend.insert(diff.new)
    backend.update(diff.updated)
    backend.delete(diff.deleted)

    if diff.conflicts:
        _handle_conflicts(diff.conflicts)

    save_state(events)

    summary = diff.summary()
    logger.info("Sync complete: %s", summary)
    return True


def _handle_conflicts(conflicts) -> None:
    lines = []
    for incoming, managed in conflicts:
        if incoming is None:
            lines.append(f"  • '{managed.title}' removed from ICS but has an active override")
        else:
            lines.append(f"  • '{managed.title}' changed in ICS but has an active override")

    msg = "\n".join(lines)
    logger.warning("Conflicts detected (calendar not changed):\n%s", msg)
    notify(
        "HWR Sync: Conflicts",
        f"{len(conflicts)} event(s) changed in ICS but have active overrides. Check the log.",
    )
