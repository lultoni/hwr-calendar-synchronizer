from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from hwr_sync.config import CONFIG_DIR

CONFLICTS_PATH = CONFIG_DIR / "conflicts.json"


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


def load_conflicts(path: Path = CONFLICTS_PATH) -> list[Conflict]:
    if not path.exists():
        return []
    raw: list[Any] = json.loads(path.read_text())
    return [Conflict(**c) for c in raw]


def save_conflicts(conflicts: list[Conflict], path: Path = CONFLICTS_PATH) -> None:
    path.write_text(json.dumps([asdict(c) for c in conflicts], indent=2, ensure_ascii=False))


def add_conflicts(new: list[Conflict], path: Path = CONFLICTS_PATH) -> None:
    existing = load_conflicts(path)
    existing_uids = {c.uid for c in existing}
    merged = existing + [c for c in new if c.uid not in existing_uids]
    save_conflicts(merged, path)


def remove_conflict(uid: str, path: Path = CONFLICTS_PATH) -> None:
    conflicts = [c for c in load_conflicts(path) if c.uid != uid]
    save_conflicts(conflicts, path)


def clear_conflicts(path: Path = CONFLICTS_PATH) -> None:
    save_conflicts([], path)
