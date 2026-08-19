from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path.home() / ".config" / "hwr-sync"
CONFIG_PATH = CONFIG_DIR / "config.yaml"


@dataclass
class SemesterConfig:
    number: int
    course: str
    end_date: date
    filters: "FilterConfig | None" = None  # overrides global filters when set


@dataclass
class GroupFilter:
    match_regex: str   # identifies which events belong to this group
    keep: list[str]    # titles to keep from that group (case-insensitive substring)


@dataclass
class FilterConfig:
    # Always drop events whose title contains any of these (case-insensitive substring)
    exclude_title_contains: list[str] = field(default_factory=list)
    # Always drop events matching any of these regexes
    exclude_by_regex: list[str] = field(default_factory=list)
    # Per-group selection: drop everything in a group except explicitly kept titles
    groups: list[GroupFilter] = field(default_factory=list)


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
    microsoft_client_id: str | None = None
    microsoft_tenant_id: str | None = None


def load_config(path: Path = CONFIG_PATH) -> Config:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}\n"
            f"Run `hwr-sync settings` to create and open it.\n"
            f"See https://github.com/lultoni/hwr-calendar-synchronizer#configuration for the expected format."
        )
    raw = yaml.safe_load(path.read_text())

    semesters = [
        SemesterConfig(
            number=s["number"],
            course=s["course"],
            end_date=_parse_date(s["end_date"]),
            filters=_parse_filters(s["filters"]) if "filters" in s else None,
        )
        for s in raw.get("semesters", [])
    ]
    semesters.sort(key=lambda s: s.number)

    f = raw.get("filters", {})
    filters = _parse_filters(f)

    return Config(
        faculty=raw["faculty"],
        study_start_date=_parse_date(raw["study_start_date"]),
        semesters=semesters,
        calendar_name=raw["calendar_name"],
        calendar_backend=raw.get("calendar_backend", "auto"),
        sync_interval_hours=int(raw.get("sync_interval_hours", 6)),
        filters=filters,
        caldav_url=raw.get("caldav_url"),
        microsoft_client_id=raw.get("microsoft_client_id"),
        microsoft_tenant_id=raw.get("microsoft_tenant_id"),
    )


def save_backend(backend: str, path: Path = CONFIG_PATH) -> None:
    """Persist the detected backend into config.yaml (called once on first run)."""
    raw = yaml.safe_load(path.read_text())
    raw["calendar_backend"] = backend
    path.write_text(yaml.dump(raw, allow_unicode=True, sort_keys=False))


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


def _parse_filters(f: dict) -> "FilterConfig":
    groups = [
        GroupFilter(match_regex=g["match_regex"], keep=g.get("keep", []))
        for g in f.get("groups", [])
    ]
    return FilterConfig(
        exclude_title_contains=f.get("exclude_title_contains", []),
        exclude_by_regex=f.get("exclude_by_regex", []),
        groups=groups,
    )


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
