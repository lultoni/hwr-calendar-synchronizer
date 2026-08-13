from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TASK_NAME = "hwr-sync"


def install(interval_hours: int) -> None:
    executable = sys.executable
    script_dir = Path.cwd()
    log_path = script_dir / "hwr-sync.log"

    # schtasks XML for a task that runs every N hours + at logon (shutdown fallback)
    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <TimeTrigger>
      <Repetition>
        <Interval>PT{interval_hours}H</Interval>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
      <StartBoundary>2024-01-01T00:00:00</StartBoundary>
      <Enabled>true</Enabled>
    </TimeTrigger>
    <LogonTrigger>
      <Enabled>true</Enabled>
    </LogonTrigger>
  </Triggers>
  <Actions Context="Author">
    <Exec>
      <Command>{executable}</Command>
      <Arguments>-m cli run</Arguments>
      <WorkingDirectory>{script_dir}</WorkingDirectory>
    </Exec>
  </Actions>
  <Settings>
    <ExecutionTimeLimit>PT30M</ExecutionTimeLimit>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <StartWhenAvailable>true</StartWhenAvailable>
    <WakeToRun>false</WakeToRun>
  </Settings>
</Task>"""

    xml_path = script_dir / "hwr-sync-task.xml"
    xml_path.write_text(xml, encoding="utf-16")

    subprocess.run(
        ["schtasks", "/create", "/tn", TASK_NAME, "/xml", str(xml_path), "/f"],
        check=True,
    )
    xml_path.unlink()
    print(f"[hwr-sync] Windows Task Scheduler job installed.")


def uninstall() -> None:
    subprocess.run(
        ["schtasks", "/delete", "/tn", TASK_NAME, "/f"],
        check=False,
        capture_output=True,
    )
    print("[hwr-sync] Windows task removed.")


def is_installed() -> bool:
    result = subprocess.run(
        ["schtasks", "/query", "/tn", TASK_NAME],
        capture_output=True,
    )
    return result.returncode == 0
