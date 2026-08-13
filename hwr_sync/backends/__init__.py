from __future__ import annotations

import platform
import sys

from hwr_sync.backends.base import CalendarBackend


def get_backend(config) -> CalendarBackend:
    from hwr_sync.config import save_backend

    backend_name = config.calendar_backend

    if backend_name == "auto":
        backend_name = _detect()
        save_backend(backend_name)
        print(f"[hwr-sync] Detected calendar backend: {backend_name} (saved to config.yaml)")

    return _build(backend_name, config)


def _detect() -> str:
    system = platform.system()
    if system == "Darwin":
        return "apple"
    if system == "Windows":
        return "caldav"
    return "caldav"


def _build(name: str, config) -> CalendarBackend:
    if name == "apple":
        from hwr_sync.backends.apple import AppleCalendarBackend
        return AppleCalendarBackend(config.calendar_name)

    if name == "caldav":
        from hwr_sync.backends.caldav import CalDAVBackend
        url = config.caldav_url
        if not url:
            print(
                "[hwr-sync] CalDAV backend requires caldav_url in config.yaml.\n"
                "Example: caldav_url: \"https://caldav.icloud.com/\"\n"
                "Run `hwr-sync settings` to edit your config."
            )
            sys.exit(1)
        return CalDAVBackend(url, config.calendar_name)

    if name == "ics_file":
        from hwr_sync.backends.ics_file import ICSFileBackend
        return ICSFileBackend()

    raise ValueError(
        f"Unknown calendar backend: '{name}'\n"
        "Supported: auto | apple | caldav | ics_file"
    )
