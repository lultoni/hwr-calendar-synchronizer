from __future__ import annotations

import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests
from icalendar import Calendar, Event


@dataclass
class CalEvent:
    uid: str
    title: str
    start: datetime
    end: datetime
    location: str
    description: str


def fetch_ics(url: str) -> list[CalEvent]:
    """Download ICS from url, parse events, delete temp file, return events."""
    tmp = Path(tempfile.gettempdir()) / f"hwr_sync_{uuid.uuid4().hex}.ics"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        tmp.write_bytes(response.content)
        return _parse_ics(tmp)
    finally:
        if tmp.exists():
            tmp.unlink()


def _parse_ics(path: Path) -> list[CalEvent]:
    cal = Calendar.from_ical(path.read_bytes())
    events: list[CalEvent] = []

    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        uid = str(component.get("UID", ""))
        title = str(component.get("SUMMARY", ""))
        location = str(component.get("LOCATION", ""))
        description = str(component.get("DESCRIPTION", ""))

        dtstart = component.get("DTSTART")
        dtend = component.get("DTEND")
        if dtstart is None or dtend is None:
            continue

        start = _to_aware_utc(dtstart.dt)
        end = _to_aware_utc(dtend.dt)

        events.append(CalEvent(
            uid=uid,
            title=title,
            start=start,
            end=end,
            location=location,
            description=description,
        ))

    return events


def _to_aware_utc(dt: datetime | object) -> datetime:
    from datetime import date as date_type

    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    # date-only → treat as midnight UTC
    if isinstance(dt, date_type):
        return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)

    raise ValueError(f"Unexpected date type: {type(dt)}")
