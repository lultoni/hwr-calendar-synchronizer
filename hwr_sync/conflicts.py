from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from hwr_sync.config import CONFIG_DIR

CONFLICTS_PATH = CONFIG_DIR / "conflicts.json"

# Status values
STATUS_OPEN = "open"
STATUS_RESOLVED_USER_DELETED = "resolved_user_deleted"
STATUS_RESOLVED_USER_EDITED = "resolved_user_edited"


@dataclass
class Conflict:
    uid: str
    kind: str        # "user_deleted" | "user_modified" | "both_changed" | "hwr_changed_user_deleted"
    title: str       # display title
    ics_title: str   # what HWR says (may differ from state if HWR changed)
    ics_start: str
    ics_end: str
    ics_location: str
    cal_title: str   # what's currently in the calendar ("" if deleted)
    cal_start: str
    cal_end: str
    cal_location: str
    cal_id: str      # backend cal_id for restore operations
    status: str = STATUS_OPEN
    ics_hash: str = ""  # hash of ICS event at time of conflict detection


def load_conflicts(path: Path = CONFLICTS_PATH) -> list[Conflict]:
    if not path.exists():
        return []
    raw: list[Any] = json.loads(path.read_text())
    result = []
    for c in raw:
        c.setdefault("status", STATUS_OPEN)
        c.setdefault("ics_hash", "")
        result.append(Conflict(**c))
    return result


def save_conflicts(conflicts: list[Conflict], path: Path = CONFLICTS_PATH) -> None:
    path.write_text(json.dumps([asdict(c) for c in conflicts], indent=2, ensure_ascii=False))


def add_conflicts(new: list[Conflict], path: Path = CONFLICTS_PATH) -> None:
    """Merge new open conflicts into the list.

    - Existing resolved entries are re-opened if the ICS hash changed (HWR updated the event).
    - Already-open entries get their ics_hash updated (ICS may have changed since first detection).
    - New conflicts for UIDs not yet tracked are appended.
    """
    existing = load_conflicts(path)
    by_uid: dict[str, Conflict] = {c.uid: c for c in existing}

    for c in new:
        if c.uid in by_uid:
            prev = by_uid[c.uid]
            if prev.status == STATUS_OPEN:
                # Already open — just refresh the ICS snapshot in case HWR changed it
                prev.ics_hash = c.ics_hash
                prev.ics_title = c.ics_title
                prev.ics_start = c.ics_start
                prev.ics_end = c.ics_end
                prev.ics_location = c.ics_location
            elif prev.ics_hash != c.ics_hash:
                # Resolved but HWR changed the event since → re-open
                by_uid[c.uid] = c
            # else: resolved, same ICS hash — leave untouched
        else:
            by_uid[c.uid] = c

    save_conflicts(list(by_uid.values()), path)


def open_conflicts(path: Path = CONFLICTS_PATH) -> list[Conflict]:
    """Return only conflicts that still need user action."""
    return [c for c in load_conflicts(path) if c.status == STATUS_OPEN]


def resolve_conflict(uid: str, status: str, path: Path = CONFLICTS_PATH) -> None:
    """Mark a conflict as resolved with the given status."""
    conflicts = load_conflicts(path)
    for c in conflicts:
        if c.uid == uid:
            c.status = status
            break
    save_conflicts(conflicts, path)


def remove_conflict(uid: str, path: Path = CONFLICTS_PATH) -> None:
    conflicts = [c for c in load_conflicts(path) if c.uid != uid]
    save_conflicts(conflicts, path)


def clear_conflicts(path: Path = CONFLICTS_PATH) -> None:
    save_conflicts([], path)
