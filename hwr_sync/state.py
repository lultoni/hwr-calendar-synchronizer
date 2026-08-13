from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from hwr_sync.config import CONFIG_DIR
STATE_PATH = CONFIG_DIR / "state.json"


@dataclass
class ManagedEvent:
    uid: str
    title: str
    start: str   # ISO format
    end: str
    location: str
    description: str
    event_hash: str


def _event_hash(event) -> str:
    payload = f"{event.title}|{event.start.isoformat()}|{event.end.isoformat()}|{event.location}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def load_state(path: Path = STATE_PATH) -> dict[str, ManagedEvent]:
    if not path.exists():
        return {}
    raw: dict[str, Any] = json.loads(path.read_text())
    return {uid: ManagedEvent(**data) for uid, data in raw.items()}


def save_state(events, path: Path = STATE_PATH) -> None:
    from hwr_sync.fetcher import CalEvent
    state: dict[str, Any] = {}
    for e in events:
        state[e.uid] = asdict(ManagedEvent(
            uid=e.uid,
            title=e.title,
            start=e.start.isoformat(),
            end=e.end.isoformat(),
            location=e.location,
            description=e.description,
            event_hash=_event_hash(e),
        ))
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def make_hash(event) -> str:
    return _event_hash(event)
