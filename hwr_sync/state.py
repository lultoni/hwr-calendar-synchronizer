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
    cal_id: str = ""  # backend-native identifier (e.g. EKEvent.calendarItemIdentifier)


def _event_hash(event) -> str:
    payload = f"{event.title}|{event.start.isoformat()}|{event.end.isoformat()}|{event.location}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def load_state(path: Path = STATE_PATH) -> dict[str, ManagedEvent]:
    if not path.exists():
        return {}
    raw: dict[str, Any] = json.loads(path.read_text())
    result = {}
    for uid, data in raw.get("events", raw).items():
        data.setdefault("cal_id", "")
        result[uid] = ManagedEvent(**data)
    return result


def load_user_deleted(path: Path = STATE_PATH) -> set[str]:
    if not path.exists():
        return set()
    raw: dict[str, Any] = json.loads(path.read_text())
    return set(raw.get("user_deleted", []))


def save_state(events, cal_ids: dict[str, str] | None = None,
               user_deleted: set[str] | None = None, path: Path = STATE_PATH) -> None:
    # Preserve existing user_deleted unless explicitly overridden
    existing_deleted = load_user_deleted(path)
    merged_deleted = (existing_deleted | (user_deleted or set()))

    events_dict: dict[str, Any] = {}
    for e in events:
        events_dict[e.uid] = asdict(ManagedEvent(
            uid=e.uid,
            title=e.title,
            start=e.start.isoformat(),
            end=e.end.isoformat(),
            location=e.location,
            description=e.description,
            event_hash=_event_hash(e),
            cal_id=(cal_ids or {}).get(e.uid, ""),
        ))

    path.write_text(json.dumps(
        {"events": events_dict, "user_deleted": sorted(merged_deleted)},
        indent=2, ensure_ascii=False,
    ))


def make_hash(event) -> str:
    return _event_hash(event)
