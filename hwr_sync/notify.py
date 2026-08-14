from __future__ import annotations

import subprocess


def notify(title: str, body: str) -> None:
    try:
        _notify_macos(title, body)
    except Exception:
        # Notifications are best-effort — never crash the sync
        pass


def _notify_macos(title: str, body: str) -> None:
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')
    script = f'display notification "{esc(body)}" with title "{esc(title)}"'
    subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
