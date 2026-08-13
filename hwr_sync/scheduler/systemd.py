from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SYSTEMD_DIR = Path.home() / ".config" / "systemd" / "user"
SERVICE_NAME = "hwr-sync"


def install(interval_hours: int) -> None:
    SYSTEMD_DIR.mkdir(parents=True, exist_ok=True)
    executable = sys.executable
    script_dir = Path.cwd()

    service = f"""[Unit]
Description=HWR Calendar Synchronizer

[Service]
Type=oneshot
ExecStart={executable} -m cli run
WorkingDirectory={script_dir}
StandardOutput=append:{script_dir}/hwr-sync.log
StandardError=append:{script_dir}/hwr-sync.log
"""

    timer = f"""[Unit]
Description=HWR Calendar Synchronizer timer

[Timer]
OnBootSec=1min
OnUnitActiveSec={interval_hours}h
Persistent=true

[Install]
WantedBy=timers.target
"""

    (SYSTEMD_DIR / f"{SERVICE_NAME}.service").write_text(service)
    (SYSTEMD_DIR / f"{SERVICE_NAME}.timer").write_text(timer)

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", f"{SERVICE_NAME}.timer"], check=True)
    print(f"[hwr-sync] systemd timer installed and started.")


def uninstall() -> None:
    subprocess.run(
        ["systemctl", "--user", "disable", "--now", f"{SERVICE_NAME}.timer"],
        check=False,
    )
    for suffix in (".service", ".timer"):
        path = SYSTEMD_DIR / f"{SERVICE_NAME}{suffix}"
        if path.exists():
            path.unlink()
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    print("[hwr-sync] systemd timer removed.")


def is_installed() -> bool:
    return (SYSTEMD_DIR / f"{SERVICE_NAME}.timer").exists()
