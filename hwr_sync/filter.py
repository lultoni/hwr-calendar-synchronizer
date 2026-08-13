from __future__ import annotations

import re

from hwr_sync.config import FilterConfig
from hwr_sync.fetcher import CalEvent


def filter_past(events: list[CalEvent], now) -> list[CalEvent]:
    # Keep events that haven't ended yet — avoids deleting currently-running events
    return [e for e in events if e.end >= now]


def apply_filters(events: list[CalEvent], cfg: FilterConfig) -> list[CalEvent]:
    result = []
    for event in events:
        title_lower = event.title.lower()

        if any(ex.lower() in title_lower for ex in cfg.exclude_title_contains):
            continue

        if any(re.search(pattern, event.title) for pattern in cfg.exclude_by_regex):
            continue

        if cfg.include_title_contains:
            if not any(inc.lower() in title_lower for inc in cfg.include_title_contains):
                continue

        result.append(event)

    return result
