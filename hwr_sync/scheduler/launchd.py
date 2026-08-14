from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from hwr_sync.config import CONFIG_DIR

PLIST_NAME = "com.hwr-sync.plist"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"


def install(interval_hours: int) -> None:
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    plist_path = LAUNCH_AGENTS_DIR / PLIST_NAME

    hwr_sync_bin = str(Path(sys.executable).parent / "hwr-sync")
    log_path = str(CONFIG_DIR / "hwr-sync.log")
    interval_seconds = interval_hours * 3600

    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.hwr-sync</string>
    <key>ProgramArguments</key>
    <array>
        <string>{hwr_sync_bin}</string>
        <string>run</string>
    </array>
    <key>StartInterval</key>
    <integer>{interval_seconds}</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log_path}</string>
    <key>StandardErrorPath</key>
    <string>{log_path}</string>
</dict>
</plist>
"""
    plist_path.write_text(plist)
    subprocess.run(["launchctl", "load", str(plist_path)], check=True)
    print(f"[hwr-sync] launchd job installed: {plist_path}")


def uninstall() -> None:
    plist_path = LAUNCH_AGENTS_DIR / PLIST_NAME
    if plist_path.exists():
        subprocess.run(["launchctl", "unload", str(plist_path)], check=False)
        plist_path.unlink()
        print("[hwr-sync] launchd job removed.")
    else:
        print("[hwr-sync] No launchd job found.")


def is_installed() -> bool:
    return (LAUNCH_AGENTS_DIR / PLIST_NAME).exists()
