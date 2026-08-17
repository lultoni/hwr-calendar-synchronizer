from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from hwr_sync.config import CONFIG_DIR

CHANGES_PATH = CONFIG_DIR / "last_changes.json"


@dataclass
class ChangeEvent:
    uid: str
    title: str
    start: str
    end: str


@dataclass
class SyncChanges:
    added: list[ChangeEvent] = field(default_factory=list)
    updated: list[ChangeEvent] = field(default_factory=list)
    deleted: list[ChangeEvent] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.added or self.updated or self.deleted)


def save_changes(changes: SyncChanges, path: Path = CHANGES_PATH) -> None:
    path.write_text(json.dumps(asdict(changes), indent=2, ensure_ascii=False))


def load_changes(path: Path = CHANGES_PATH) -> SyncChanges | None:
    if not path.exists():
        return None
    raw: dict[str, Any] = json.loads(path.read_text())
    return SyncChanges(
        added=[ChangeEvent(**e) for e in raw.get("added", [])],
        updated=[ChangeEvent(**e) for e in raw.get("updated", [])],
        deleted=[ChangeEvent(**e) for e in raw.get("deleted", [])],
    )


def clear_changes(path: Path = CHANGES_PATH) -> None:
    save_changes(SyncChanges(), path)
