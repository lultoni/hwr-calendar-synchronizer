from __future__ import annotations

import sys

from hwr_sync.backends.base import CalendarBackend


def get_backend(config, create_missing_calendar: bool = False) -> CalendarBackend:
    from hwr_sync.config import save_backend

    backend_name = config.calendar_backend

    if backend_name == "auto":
        backend_name = "apple"
        save_backend(backend_name)
        print(f"[hwr-sync] Calendar backend: {backend_name} (saved to config.yaml)")

    if backend_name != "apple":
        print(
            f"[hwr-sync] Backend '{backend_name}' is not supported in this release.\n"
            "Only 'apple' (Apple Calendar on macOS) is currently supported.\n"
            "Set calendar_backend: apple in your config.yaml."
        )
        sys.exit(1)

    from hwr_sync.backends.apple import AppleCalendarBackend
    return AppleCalendarBackend(config.calendar_name, create_missing_calendar=create_missing_calendar)
