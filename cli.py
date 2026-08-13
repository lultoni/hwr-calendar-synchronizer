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
from hwr_sync.config import CONFIG_DIR, CONFIG_PATH, OVERRIDES_PATH, load_config
from hwr_sync.state import load_state
from hwr_sync.sync import sync

CONFIG_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = CONFIG_DIR / "hwr-sync.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_PATH),
    ],
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

    running = scheduler.is_installed()
    click.echo(f"Scheduler:      {'running' if running else 'stopped'}")
    click.echo(f"Interval:       every {config.sync_interval_hours}h")

    from hwr_sync.config import get_current_semester
    sem = get_current_semester(config, now)
    if sem:
        click.echo(f"Active semester: {sem.number} ({config.faculty}/{sem.course}, ends {sem.end_date})")
    else:
        click.echo("Active semester: none (study period complete)")

    state = load_state()
    click.echo(f"Managed events: {len(state)}")

    if LOG_PATH.exists():
        lines = LOG_PATH.read_text().splitlines()
        last = next(
            (l for l in reversed(lines) if "Sync complete" in l or "Syncing semester" in l),
            None,
        )
        if last:
            click.echo(f"Last sync:      {last.strip()}")


@main.command()
def settings():
    """Open config.yaml in your default editor (~/.config/hwr-sync/config.yaml)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        _copy_example("config.example.yaml", CONFIG_PATH)
    _open_in_editor(CONFIG_PATH)


@main.command("overrides")
def overrides_cmd():
    """Open overrides.yaml in your default editor (~/.config/hwr-sync/overrides.yaml)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not OVERRIDES_PATH.exists():
        _copy_example("overrides.example.yaml", OVERRIDES_PATH, fallback="overrides:\n")
    _open_in_editor(OVERRIDES_PATH)


def _copy_example(filename: str, dest: Path, fallback: str | None = None) -> None:
    import importlib.resources
    import shutil

    # Try installed package data first
    try:
        ref = importlib.resources.files("hwr_sync") / ".." / filename
        src = Path(str(ref))
        if src.exists():
            shutil.copy(src, dest)
            click.echo(f"Created {dest}. Opening...")
            return
    except Exception:
        pass

    # Fall back to file next to the package (dev install)
    local = Path(__file__).parent / filename
    if local.exists():
        shutil.copy(local, dest)
        click.echo(f"Created {dest}. Opening...")
        return

    if fallback:
        dest.write_text(fallback)
        click.echo(f"Created {dest}. Opening...")
    else:
        click.echo(f"Could not find {filename}. Create {dest} manually.")
        sys.exit(1)


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
        for ed in ("xdg-open", "nano", "vim", "vi"):
            if subprocess.run(["which", ed], capture_output=True).returncode == 0:
                subprocess.run([ed, str(path)])
                return
        click.echo(f"Could not detect editor. Open manually: {path.resolve()}")


if __name__ == "__main__":
    main()
