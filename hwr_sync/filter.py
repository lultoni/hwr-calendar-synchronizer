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

        # 1. Hard excludes — always drop, no exceptions
        if any(ex.lower() in title_lower for ex in cfg.exclude_title_contains):
            continue
        if any(re.search(pattern, event.title) for pattern in cfg.exclude_by_regex):
            continue

        # 2. Group filters — each group is independent
        #    If the event matches a group's regex, drop it unless its title
        #    is listed in that group's keep list
        dropped = False
        for group in cfg.groups:
            if re.search(group.match_regex, event.title):
                if not any(k.lower() in title_lower for k in group.keep):
                    dropped = True
                    break
        if dropped:
            continue

        result.append(event)

    return result
