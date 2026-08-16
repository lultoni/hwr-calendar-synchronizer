from __future__ import annotations

import subprocess


def notify(title: str, body: str) -> None:
    try:
        _notify_macos(title, body)
    except Exception:
        # Notifications are best-effort — never crash the sync
        pass


def _notify_macos(title: str, body: str) -> None:
    subprocess.run(
        [
            "osascript", "-e",
            "on run argv\n"
            "display notification (item 2 of argv) with title (item 1 of argv)\n"
            "end run",
            title, body,
        ],
        check=False, capture_output=True,
    )
