from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path("config.yaml")
OVERRIDES_PATH = Path("overrides.yaml")


@dataclass
class SemesterConfig:
    number: int
    course: str
    end_date: date


@dataclass
class FilterConfig:
    exclude_title_contains: list[str] = field(default_factory=list)
    include_title_contains: list[str] = field(default_factory=list)
    exclude_by_regex: list[str] = field(default_factory=list)


@dataclass
class Config:
    faculty: str
    study_start_date: date
    semesters: list[SemesterConfig]
    calendar_name: str
    calendar_backend: str
    sync_interval_hours: int
    filters: FilterConfig
    caldav_url: str | None = None


def load_config(path: Path = CONFIG_PATH) -> Config:
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}\n"
            "Copy config.example.yaml to config.yaml and fill in your details."
        )
    raw = yaml.safe_load(path.read_text())

    semesters = [
        SemesterConfig(
            number=s["number"],
            course=s["course"],
            end_date=_parse_date(s["end_date"]),
        )
        for s in raw.get("semesters", [])
    ]
    semesters.sort(key=lambda s: s.number)

    f = raw.get("filters", {})
    filters = FilterConfig(
        exclude_title_contains=f.get("exclude_title_contains", []),
        include_title_contains=f.get("include_title_contains", []),
        exclude_by_regex=f.get("exclude_by_regex", []),
    )

    return Config(
        faculty=raw["faculty"],
        study_start_date=_parse_date(raw["study_start_date"]),
        semesters=semesters,
        calendar_name=raw["calendar_name"],
        calendar_backend=raw.get("calendar_backend", "auto"),
        sync_interval_hours=int(raw.get("sync_interval_hours", 6)),
        filters=filters,
        caldav_url=raw.get("caldav_url"),
    )


def save_backend(backend: str, path: Path = CONFIG_PATH) -> None:
    """Persist the detected backend into config.yaml (called once on first run)."""
    raw = yaml.safe_load(path.read_text())
    raw["calendar_backend"] = backend
    path.write_text(yaml.dump(raw, allow_unicode=True, sort_keys=False))


def load_overrides(path: Path = OVERRIDES_PATH) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text()) or {}
    return raw.get("overrides", {}) or {}


def get_current_semester(config: Config, now: datetime) -> SemesterConfig | None:
    today = now.date() if isinstance(now, datetime) else now
    for sem in config.semesters:
        if today <= sem.end_date:
            return sem
    return None


BASE_URL = (
    "https://moodle.hwr-berlin.de/fb2-stundenplan/download.php"
    "?doctype=.ics&url=./fb2-stundenplaene/{faculty}/semester{number}/{course}"
)


def build_ics_url(faculty: str, semester_number: int, course: str) -> str:
    return BASE_URL.format(faculty=faculty, number=semester_number, course=course)


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
