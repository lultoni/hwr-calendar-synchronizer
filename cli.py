from __future__ import annotations

import logging
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

from hwr_sync import scheduler
from hwr_sync.config import CONFIG_PATH, OVERRIDES_PATH, load_config
from hwr_sync.state import STATE_PATH, load_state
from hwr_sync.sync import sync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@click.group()
def main():
    """HWR Calendar Synchronizer — sync your university timetable automatically."""


@main.command()
def run():
    """Run a single sync pass right now."""
    active = sync()
    if not active:
        click.echo("Study period is over. Run `hwr-sync stop` to remove the scheduler.")
        sys.exit(0)


@main.command()
def start():
    """Register the OS scheduler and run an immediate sync."""
    config = load_config()
    scheduler.install(config.sync_interval_hours)
    click.echo(f"Scheduler started (every {config.sync_interval_hours}h).")
    click.echo("Running initial sync...")
    active = sync()
    if not active:
        click.echo("Study period is over. Run `hwr-sync stop` to remove the scheduler.")


@main.command()
def stop():
    """Remove the OS scheduler."""
    scheduler.uninstall()


@main.command()
def status():
    """Show sync status: scheduler, last sync, active semester."""
    try:
        config = load_config()
    except FileNotFoundError as e:
        click.echo(str(e))
        sys.exit(1)

    now = datetime.now(tz=timezone.utc)

    # Scheduler
    running = scheduler.is_installed()
    click.echo(f"Scheduler:      {'running' if running else 'stopped'}")
    click.echo(f"Interval:       every {config.sync_interval_hours}h")

    # Active semester
    from hwr_sync.config import get_current_semester
    sem = get_current_semester(config, now)
    if sem:
        click.echo(f"Active semester: {sem.number} ({config.faculty}/{sem.course}, ends {sem.end_date})")
    else:
        click.echo("Active semester: none (study period complete)")

    # State
    state = load_state()
    click.echo(f"Managed events: {len(state)}")

    # Log tail
    log_path = Path("hwr-sync.log")
    if log_path.exists():
        lines = log_path.read_text().splitlines()
        last = next(
            (l for l in reversed(lines) if "Sync complete" in l or "Syncing semester" in l),
            None,
        )
        if last:
            click.echo(f"Last sync:      {last.strip()}")


@main.command()
def settings():
    """Open config.yaml in your default editor."""
    if not CONFIG_PATH.exists():
        example = Path("config.example.yaml")
        if example.exists():
            import shutil
            shutil.copy(example, CONFIG_PATH)
            click.echo(f"Created {CONFIG_PATH} from example. Opening...")
        else:
            click.echo(f"{CONFIG_PATH} not found. Create it from config.example.yaml first.")
            sys.exit(1)
    _open_in_editor(CONFIG_PATH)


@main.command("overrides")
def overrides_cmd():
    """Open overrides.yaml in your default editor."""
    if not OVERRIDES_PATH.exists():
        example = Path("overrides.example.yaml")
        if example.exists():
            import shutil
            shutil.copy(example, OVERRIDES_PATH)
            click.echo(f"Created {OVERRIDES_PATH} from example. Opening...")
        else:
            OVERRIDES_PATH.write_text("overrides:\n")
            click.echo(f"Created empty {OVERRIDES_PATH}. Opening...")
    _open_in_editor(OVERRIDES_PATH)


def _open_in_editor(path: Path) -> None:
    system = platform.system()
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")

    if editor:
        subprocess.run([editor, str(path)])
    elif system == "Darwin":
        subprocess.run(["open", "-t", str(path)])
    elif system == "Windows":
        os.startfile(str(path))  # type: ignore
    else:
        # Try common editors
        for ed in ("xdg-open", "nano", "vim", "vi"):
            if subprocess.run(["which", ed], capture_output=True).returncode == 0:
                subprocess.run([ed, str(path)])
                return
        click.echo(f"Could not detect editor. Open manually: {path.resolve()}")


if __name__ == "__main__":
    main()
