from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
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
    cal_id: str = ""  # backend-native identifier (e.g. EKEvent.calendarItemIdentifier)


def _event_hash(event) -> str:
    payload = f"{event.title}|{event.start.isoformat()}|{event.end.isoformat()}|{event.location}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def load_state(path: Path = STATE_PATH) -> dict[str, ManagedEvent]:
    if not path.exists():
        return {}
    raw: dict[str, Any] = json.loads(path.read_text())
    # Support both old flat format and new {events: ...} format
    events_raw = raw.get("events", raw) if isinstance(raw, dict) else raw
    result = {}
    for uid, data in events_raw.items():
        if not isinstance(data, dict):
            continue
        data.setdefault("cal_id", "")
        result[uid] = ManagedEvent(**data)
    return result


def save_state(events, cal_ids: dict[str, str] | None = None, path: Path = STATE_PATH) -> None:
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
            cal_id=(cal_ids or {}).get(e.uid, ""),
        ))
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def make_hash(event) -> str:
    return _event_hash(event)
