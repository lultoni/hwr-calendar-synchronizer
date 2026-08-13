from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PLIST_NAME = "com.hwr-sync.plist"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"


def install(interval_hours: int) -> None:
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    plist_path = LAUNCH_AGENTS_DIR / PLIST_NAME
    executable = sys.executable
    script_dir = Path.cwd()

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
        <string>{executable}</string>
        <string>-m</string>
        <string>cli</string>
        <string>run</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{script_dir}</string>
    <key>StartInterval</key>
    <integer>{interval_seconds}</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{script_dir}/hwr-sync.log</string>
    <key>StandardErrorPath</key>
    <string>{script_dir}/hwr-sync.log</string>
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
