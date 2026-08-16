from __future__ import annotations

import logging
import os
import plistlib
import shutil
import subprocess
from pathlib import Path

from hwr_sync.config import CONFIG_DIR

logger = logging.getLogger("hwr_sync")

PLIST_NAME = "com.hwr-sync.plist"
LABEL = "com.hwr-sync"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"


def _uid() -> str:
    return str(os.getuid())


def _bootstrap(plist_path: Path) -> None:
    r = subprocess.run(
        ["launchctl", "bootstrap", f"gui/{_uid()}", str(plist_path)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"launchctl bootstrap failed: {r.stderr.strip()}")


def _bootout(plist_path: Path) -> None:
    r = subprocess.run(
        ["launchctl", "bootout", f"gui/{_uid()}", str(plist_path)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        # bootout exits non-zero if the job wasn't loaded — that's fine
        stderr = r.stderr.strip()
        if stderr:
            logger.warning("launchctl bootout: %s", stderr)


def _calendar_intervals(interval_hours: int) -> list[dict]:
    """Return StartCalendarInterval dicts spaced interval_hours apart from midnight.

    For clean divisors of 24 (1,2,3,4,6,8,12,24) all gaps are equal.
    For other values (e.g. 5h → 00,05,10,15,20) the overnight gap is shorter
    than the interval, but all daytime gaps are exact.
    """
    times = []
    hour = 0
    while hour < 24:
        times.append({"Hour": hour, "Minute": 0})
        hour += interval_hours
    return times


def _resolve_binary() -> str:
    """Return the hwr-sync binary path, preferring PATH resolution over sys.executable sibling."""
    found = shutil.which("hwr-sync")
    if found:
        return found
    # Fallback: sibling of the Python interpreter (works for uv tool installs)
    import sys
    fallback = str(Path(sys.executable).parent / "hwr-sync")
    if Path(fallback).exists():
        return fallback
    raise FileNotFoundError(
        f"Cannot find the hwr-sync binary.\n"
        f"Tried: PATH lookup and {fallback}\n"
        "Make sure hwr-sync is installed: pip install hwr-calendar-synchronizer"
    )


def install(interval_hours: int) -> None:
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    plist_path = LAUNCH_AGENTS_DIR / PLIST_NAME

    hwr_sync_bin = _resolve_binary()
    log_path = str(CONFIG_DIR / "hwr-sync.log")

    plist_data = {
        "Label": LABEL,
        "ProgramArguments": [hwr_sync_bin, "run"],
        "StartCalendarInterval": _calendar_intervals(interval_hours),
        "WorkingDirectory": str(Path.home()),
        "StandardOutPath": log_path,
        "StandardErrorPath": log_path,
    }
    plist_path.write_bytes(plistlib.dumps(plist_data))

    # Unload first so reinstall works cleanly (idempotent if not loaded)
    if is_installed():
        _bootout(plist_path)

    _bootstrap(plist_path)
    logger.info("Scheduler registered: %s", plist_path)


def uninstall() -> None:
    plist_path = LAUNCH_AGENTS_DIR / PLIST_NAME
    if plist_path.exists():
        _bootout(plist_path)
        plist_path.unlink()
        logger.info("Scheduler removed.")
    else:
        logger.info("No scheduler found.")


def is_installed() -> bool:
    r = subprocess.run(
        ["launchctl", "list", LABEL],
        capture_output=True,
    )
    return r.returncode == 0
