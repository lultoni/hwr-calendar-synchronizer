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
from hwr_sync.conflicts import Conflict, load_conflicts, remove_conflict, clear_conflicts
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


@main.command("conflicts")
def conflicts_cmd():
    """Check for new conflicts and resolve existing ones interactively."""
    # Always do a fresh check first so we see current state
    click.echo("Checking for conflicts...")
    from hwr_sync.sync import sync
    sync()

    conflicts = load_conflicts()
    if not conflicts:
        click.echo("No conflicts. Everything is in sync.")
        return

    click.echo(f"\n{len(conflicts)} conflict(s) to review.\n")
    click.echo("Options per item:  [k] keep yours  [r] restore from HWR  [s] skip (decide later)\n")

    backend = None  # lazy init
    resolved = []
    skipped = []

    for i, c in enumerate(conflicts):
        click.echo(f"─── {i+1}/{len(conflicts)} ───────────────────────────────")
        _print_conflict(c)

        options = _conflict_options(c)
        choice = None
        while choice not in options:
            choice = click.prompt(
                "Choice",
                default="s",
                show_choices=True,
                type=click.Choice(list(options.keys()) + ["s"]),
            )

        if choice == "s":
            skipped.append(c)
            click.echo("Skipped — will show again next time.\n")
        else:
            if backend is None:
                from hwr_sync.backends import get_backend
                backend = get_backend(load_config())
            _execute_resolution(c, choice, backend)
            resolved.append(c.uid)
            click.echo()

        # Offer to skip remaining after first resolution
        remaining = len(conflicts) - i - 1
        if remaining > 0 and (resolved or skipped):
            if click.confirm(f"  {remaining} item(s) left — skip the rest for now?", default=False):
                skipped.extend(conflicts[i+1:])
                break

    for uid in resolved:
        remove_conflict(uid)

    click.echo(f"\nDone. {len(resolved)} resolved, {len(skipped)} left open.")


def _print_conflict(c: Conflict) -> None:
    KIND_LABELS = {
        "user_deleted":            "You deleted this — HWR still has it",
        "user_modified":           "You modified this — HWR hasn't changed it",
        "both_changed":            "Both you and HWR changed this",
        "hwr_changed_user_deleted": "You deleted this AND HWR changed it",
    }
    click.echo(f"  Event:  {c.title}")
    click.echo(f"  Status: {KIND_LABELS.get(c.kind, c.kind)}")
    click.echo()

    if c.ics_title:
        click.echo(f"  HWR version:")
        click.echo(f"    Title:    {c.ics_title}")
        click.echo(f"    Start:    {c.ics_start}")
        click.echo(f"    End:      {c.ics_end}")
        if c.ics_location:
            click.echo(f"    Location: {c.ics_location}")

    if c.cal_title:
        click.echo(f"  Your version:")
        click.echo(f"    Title:    {c.cal_title}")
        click.echo(f"    Start:    {c.cal_start}")
        click.echo(f"    End:      {c.cal_end}")
        if c.cal_location:
            click.echo(f"    Location: {c.cal_location}")
    click.echo()


def _conflict_options(c: Conflict) -> dict[str, str]:
    if c.kind == "user_deleted":
        return {"k": "keep deleted", "r": "restore from HWR"}
    if c.kind == "user_modified":
        return {"k": "keep your version", "r": "restore HWR version"}
    if c.kind == "both_changed":
        return {"k": "keep your version", "r": "use HWR version"}
    if c.kind == "hwr_changed_user_deleted":
        return {"k": "keep deleted", "r": "restore HWR's new version"}
    return {"k": "keep", "r": "restore"}


def _execute_resolution(c: Conflict, choice: str, backend) -> None:
    from hwr_sync.fetcher import CalEvent
    from hwr_sync.state import load_state, save_state
    from datetime import datetime, timezone

    if choice == "k":
        # Keep user's version — update state hash to match current calendar
        # so next sync doesn't flag it again
        state = load_state()
        if c.uid in state:
            managed = state[c.uid]
            if c.cal_title:
                # User modified: store calendar version as new ICS baseline
                from hwr_sync.state import ManagedEvent, make_hash
                cal_event = CalEvent(
                    uid=c.uid,
                    title=c.cal_title,
                    start=datetime.fromisoformat(c.cal_start),
                    end=datetime.fromisoformat(c.cal_end),
                    location=c.cal_location,
                    description="",
                )
                managed.event_hash = make_hash(cal_event)
            else:
                # User deleted: remove from state entirely
                del state[c.uid]
            _save_state_dict(state)
        click.echo("Kept your version.")

    elif choice == "r":
        # Restore HWR version into calendar
        ics_event = CalEvent(
            uid=c.uid,
            title=c.ics_title,
            start=datetime.fromisoformat(c.ics_start),
            end=datetime.fromisoformat(c.ics_end),
            location=c.ics_location,
            description="",
        )
        if c.cal_title:
            backend.update([ics_event])
            click.echo("Restored HWR version in calendar.")
        else:
            new_ids = backend.insert([ics_event])
            # Update cal_id in state
            state = load_state()
            if c.uid in state:
                state[c.uid].cal_id = new_ids.get(c.uid, "")
                _save_state_dict(state)
            click.echo("Restored HWR version in calendar.")


def _save_state_dict(state) -> None:
    from hwr_sync.state import STATE_PATH
    import json
    from dataclasses import asdict
    data = {uid: asdict(m) for uid, m in state.items()}
    STATE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))



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
