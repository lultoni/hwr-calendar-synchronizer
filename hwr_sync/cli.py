from __future__ import annotations

import logging
import logging.handlers
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

from hwr_sync import scheduler
from hwr_sync.conflicts import Conflict, load_conflicts, remove_conflict
from hwr_sync.config import CONFIG_DIR, CONFIG_PATH, load_config
from hwr_sync.state import load_state
from hwr_sync.sync import sync

CONFIG_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = CONFIG_DIR / "hwr-sync.log"

# File handler: full timestamp format, rotates at 1 MB
_file_handler = logging.handlers.RotatingFileHandler(
    LOG_PATH, maxBytes=1_000_000, backupCount=3,
)
_file_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))

# Terminal handler: message only (clean, no timestamp clutter)
_stream_handler = logging.StreamHandler()
_stream_handler.setFormatter(logging.Formatter("%(message)s"))

logging.basicConfig(level=logging.INFO, handlers=[_file_handler, _stream_handler])


@click.group()
@click.option("--verbose", "-v", is_flag=True, default=False,
              help="Enable debug-level logging to the terminal.")
def main(verbose: bool):
    """HWR Calendar Synchronizer — sync your university timetable automatically."""
    if verbose:
        _stream_handler.setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        _stream_handler.setLevel(logging.INFO)


@main.command()
@click.option("--create-missing-calendar", is_flag=True, default=False,
              help="Create the calendar in Apple Calendar if it doesn't exist.")
def run(create_missing_calendar: bool):
    """Run a single sync pass right now."""
    try:
        active = sync(create_missing_calendar=create_missing_calendar)
    except KeyboardInterrupt:
        click.echo("\nAborted.")
        sys.exit(0)
    if not active:
        click.echo("Study period is over. Run `hwr-sync stop` to remove the scheduler.")
        sys.exit(0)


@main.command()
@click.option("--interval", default=None, type=int,
              help="Sync interval in hours (overrides config).")
@click.option("--create-missing-calendar", is_flag=True, default=False,
              help="Create the calendar in Apple Calendar if it doesn't exist.")
def start(interval: int | None, create_missing_calendar: bool):
    """Register the OS scheduler and run an immediate sync."""
    config = load_config()
    effective_interval = interval if interval is not None else config.sync_interval_hours
    scheduler.install(effective_interval)
    click.echo(f"Scheduler started (every {effective_interval}h).")
    if _stream_handler.level <= logging.DEBUG:
        click.echo(f"Logs: {LOG_PATH}")
    click.echo("Running initial sync...")
    try:
        active = sync(create_missing_calendar=create_missing_calendar)
    except KeyboardInterrupt:
        click.echo("\nAborted.")
        sys.exit(0)
    if not active:
        click.echo("Study period is over. Run `hwr-sync stop` to remove the scheduler.")
    else:
        click.echo(f"\n  Your timetable is up to date in '{config.calendar_name}'.")
        click.echo("  Open Apple Calendar to check.")


@main.command()
def stop():
    """Remove the OS scheduler."""
    scheduler.uninstall()


@main.command()
def status():
    """Show sync status: scheduler, last sync, active semester, open conflicts."""
    try:
        config = load_config()
    except FileNotFoundError as e:
        click.echo(str(e))
        sys.exit(1)

    now = datetime.now(tz=timezone.utc)

    running = scheduler.is_installed()
    click.echo(f"Scheduler:       {'running' if running else 'stopped'}")
    click.echo(f"Interval:        every {config.sync_interval_hours}h")

    if running:
        next_time = _next_fire_time(config.sync_interval_hours, now)
        click.echo(f"Next sync:       {next_time}")

    from hwr_sync.config import get_current_semester
    sem = get_current_semester(config, now)
    if sem:
        click.echo(f"Active semester: {sem.number} ({config.faculty}/{sem.course}, ends {sem.end_date})")
    else:
        click.echo("Active semester: none (study period complete)")

    state = load_state()
    click.echo(f"Events in sync:  {len(state)}")

    conflicts = load_conflicts()
    if conflicts:
        click.echo(f"Conflicts:       {len(conflicts)} open — run `hwr-sync conflicts` to review")
    else:
        click.echo("Conflicts:       none")

    if LOG_PATH.exists():
        lines = LOG_PATH.read_text().splitlines()
        last = next(
            (l for l in reversed(lines) if "Sync complete" in l),
            None,
        )
        if last:
            # Strip timestamp prefix for clean display
            parts = last.strip().split("] ", 1)
            summary = parts[-1] if len(parts) > 1 else last.strip()
            click.echo(f"Last sync:       {summary}")


def _next_fire_time(interval_hours: int, now: datetime) -> str:
    """Return a human-readable string for the next scheduled fire time."""
    from datetime import timedelta
    now_local = now.astimezone()
    current_hour = now_local.hour
    count = max(1, 24 // interval_hours)
    fire_hours = [i * interval_hours for i in range(count)]
    upcoming = [h for h in fire_hours if h > current_hour]
    if upcoming:
        next_hour = upcoming[0]
        next_dt = now_local.replace(hour=next_hour, minute=0, second=0, microsecond=0)
    else:
        next_hour = fire_hours[0]
        next_dt = (now_local + timedelta(days=1)).replace(
            hour=next_hour, minute=0, second=0, microsecond=0
        )
    label = "today" if next_dt.date() == now_local.date() else "tomorrow"
    return next_dt.strftime(f"%H:%M {label}")


@main.command("conflicts")
def conflicts_cmd():
    """Check for new conflicts and resolve existing ones interactively."""
    click.echo("Checking for conflicts...")
    try:
        sync(emit_notifications=False)
    except KeyboardInterrupt:
        click.echo("\nAborted.")
        sys.exit(0)

    conflicts = load_conflicts()
    if not conflicts:
        click.echo("No conflicts. Everything is in sync.")
        return

    click.echo(f"\n{len(conflicts)} conflict(s) to review.\n")
    click.echo("Options per item:  [k] keep yours  [r] restore from HWR  [s] skip (decide later)\n")

    backend = None  # lazy init
    resolved = []
    skipped = []

    try:
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

            remaining = len(conflicts) - i - 1
            if remaining > 0 and (resolved or skipped):
                if click.confirm(f"  {remaining} item(s) left — skip the rest for now?", default=False):
                    skipped.extend(conflicts[i+1:])
                    break

    except KeyboardInterrupt:
        # Count remaining unvisited as skipped
        visited = len(resolved) + len(skipped)
        skipped.extend(conflicts[visited:])
        click.echo("\n\nInterrupted — saving progress so far.")

    for uid in resolved:
        remove_conflict(uid)

    click.echo(f"\nDone. {len(resolved)} resolved, {len(skipped)} left open.")


@main.command("settings")
def settings_cmd():
    """Open config.yaml in your editor (~/.config/hwr-sync/config.yaml). Creates it if missing."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        _copy_example("config.example.yaml", CONFIG_PATH)
        click.echo("Fill in your faculty, semesters, and calendar_name, then save and close.")
    else:
        click.echo(f"Opening {CONFIG_PATH} ...")
    _open_in_editor(CONFIG_PATH)
    click.echo("\nRun `hwr-sync start` when you're done.")


@main.command("config")
def config_cmd():
    """Alias for `hwr-sync settings`."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        _copy_example("config.example.yaml", CONFIG_PATH)
        click.echo("Fill in your faculty, semesters, and calendar_name, then save and close.")
    else:
        click.echo(f"Opening {CONFIG_PATH} ...")
    _open_in_editor(CONFIG_PATH)
    click.echo("\nRun `hwr-sync start` when you're done.")


def _fmt_dt(iso: str) -> str:
    """Convert an ISO datetime string to a human-readable local time string."""
    if not iso:
        return ""
    dt = datetime.fromisoformat(iso).astimezone()
    return dt.strftime("%a, %d. %b %Y, %H:%M")


def _print_conflict(c: Conflict) -> None:
    KIND_LABELS = {
        "user_deleted":             "You deleted this — HWR still has it",
        "user_modified":            "You modified this — HWR hasn't changed it",
        "both_changed":             "Both you and HWR changed this",
        "hwr_changed_user_deleted": "You deleted this AND HWR changed it",
    }
    click.echo(f"  Event:  {c.title}")
    click.echo(f"  Status: {KIND_LABELS.get(c.kind, c.kind)}")
    click.echo()

    if c.ics_title:
        click.echo(f"  HWR version:")
        click.echo(f"    Title:    {c.ics_title}")
        click.echo(f"    Start:    {_fmt_dt(c.ics_start)}")
        click.echo(f"    End:      {_fmt_dt(c.ics_end)}")
        if c.ics_location:
            click.echo(f"    Location: {c.ics_location}")

    if c.cal_title:
        click.echo(f"  Your version:")
        click.echo(f"    Title:    {c.cal_title}")
        click.echo(f"    Start:    {_fmt_dt(c.cal_start)}")
        click.echo(f"    End:      {_fmt_dt(c.cal_end)}")
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

    if choice == "k":
        state = load_state()
        if c.uid in state:
            managed = state[c.uid]
            if c.cal_title:
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
                del state[c.uid]
            _save_state_dict(state)
        click.echo("Kept your version.")

    elif choice == "r":
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


def _copy_example(filename: str, dest: Path, fallback: str | None = None) -> None:
    import importlib.resources
    import shutil

    try:
        ref = importlib.resources.files("hwr_sync") / filename
        src = Path(str(ref))
        if src.exists():
            shutil.copy(src, dest)
            return
    except Exception:
        pass

    # Dev-install fallback: file lives next to this module
    local = Path(__file__).parent / filename
    if local.exists():
        shutil.copy(local, dest)
        return

    if fallback:
        dest.write_text(fallback)
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
    else:
        for ed in ("xdg-open", "nano", "vim", "vi"):
            if subprocess.run(["which", ed], capture_output=True).returncode == 0:
                subprocess.run([ed, str(path)])
                return
        click.echo(f"Could not detect editor. Open manually: {path.resolve()}")


if __name__ == "__main__":
    main()
