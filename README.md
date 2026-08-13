# HWR Calendar Synchronizer

Syncs your HWR Berlin timetable into your calendar automatically. Runs as a background job, diffs every change against what HWR last published, and respects edits you make in your calendar app — without ever silently overwriting them.

Works on macOS, Linux, and Windows. Supports Apple Calendar, CalDAV (iCloud, Nextcloud, ...), and static ICS export.

---

## How it works

Each sync pass:
1. Fetches the ICS from HWR and applies your course filters
2. Reads your calendar to check which managed events are still there and how they look
3. Diffs ICS (what HWR says) vs state (what HWR said last time) vs calendar (what you have now)
4. Applies clean changes — new events added, changed events updated, removed events deleted
5. Records divergences (things you changed or deleted) as conflicts for you to review

You are the source of truth. If you delete or modify an event, the sync never silently overwrites it — it flags a conflict and waits for your decision.

---

## Setup

### Quick (for developers)

```bash
git clone https://github.com/YOUR_USERNAME/hwr-calendar-synchronizer.git
cd hwr-calendar-synchronizer

# Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install (macOS — includes Apple Calendar support)
uv tool install -e ".[apple]"

# Linux / Windows
uv tool install -e .

# Configure
cp config.example.yaml ~/.config/hwr-sync/config.yaml
hwr-sync settings

# Test
hwr-sync run

# Enable background sync
hwr-sync start
```

### Step by step (for everyone)

**1 — Install Python 3.11+**

Download from [python.org/downloads](https://python.org/downloads). On Windows, check "Add Python to PATH" during install.

**2 — Install uv**

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**3 — Download and install**

```bash
git clone https://github.com/YOUR_USERNAME/hwr-calendar-synchronizer.git
cd hwr-calendar-synchronizer
uv tool install -e .          # Linux / Windows
uv tool install -e ".[apple]" # macOS
```

**4 — Configure**

```bash
cp config.example.yaml ~/.config/hwr-sync/config.yaml
hwr-sync settings
```

Fill in your faculty, semester dates, course groups, and which calendar to sync into. The file is documented with examples.

**5 — Run and start**

```bash
hwr-sync run    # test — check your calendar app after this
hwr-sync start  # enable automatic background sync
```

### AI-assisted setup

Paste this into Claude, ChatGPT, or any AI assistant — it will install everything and fill in your config interactively:

```
I want to set up hwr-calendar-synchronizer. Please guide me through the full setup.

1. Check if git, Python 3.11+ and uv are installed; help me install anything missing.
2. Clone https://github.com/YOUR_USERNAME/hwr-calendar-synchronizer and install it.
3. Ask me one at a time: faculty, semester dates and course groups, which calendar app I use, what to name the calendar.
4. Write my config.yaml based on my answers.
5. Run `hwr-sync run` to test, then `hwr-sync start` to enable background sync.

Start by asking what OS I'm on.
```

---

## Commands

| Command | What it does |
|---|---|
| `hwr-sync run` | Run one sync pass now |
| `hwr-sync start` | Register background scheduler + sync immediately |
| `hwr-sync stop` | Remove background scheduler |
| `hwr-sync status` | Show scheduler state, active semester, last sync |
| `hwr-sync conflicts` | Review and resolve calendar conflicts interactively |
| `hwr-sync settings` | Open config.yaml in your editor |
| `hwr-sync overrides` | Open overrides.yaml in your editor |
| `hwr-sync --help` | Show all commands |

---

## Configuration

Config lives at `~/.config/hwr-sync/config.yaml`. Run `hwr-sync settings` to open it.

### Semesters

```yaml
faculty: "wi"
study_start_date: "2024-10-01"

semesters:
  - number: 5
    course: "kursa"          # kursa / kursb / kursc / kurs (if no split)
    end_date: "2027-01-31"   # include Praxisphase
  - number: 6
    course: "kursa"
    end_date: "2027-09-30"
```

The tool auto-detects the active semester from today's date and stops syncing after the last `end_date`.

### Filters

Each semester can define its own filters. Leave the global `filters` block empty to keep all events by default.

**Hard exclude** — always drop these, no exceptions:

```yaml
filters:
  exclude_title_contains:
    - "Wegezeit"
  exclude_by_regex:
    - "^Englisch.*B1$"
```

**Group filter** — drop all events matching a pattern, except the ones you actually chose. Use this for elective modules (WPF). Multiple independent groups are supported:

```yaml
semesters:
  - number: 5
    course: "kursa"
    end_date: "2027-01-31"
    filters:
      groups:
        - match_regex: "(?i)WPF"
          keep:
            - "Cross Cultural Management"
            - "Social Innovation"
```

### Calendar backend

```yaml
calendar_name: "University"
calendar_backend: "auto"   # detected on first run and saved
```

| Backend | Use when |
|---|---|
| `apple` | macOS with Apple Calendar (auto-detected) |
| `caldav` | iCloud, Nextcloud, any CalDAV — also set `caldav_url` |
| `ics_file` | Export a static `.ics` file to subscribe to from any app |

---

## Conflicts

When you edit or delete an event in your calendar, the next sync detects the divergence and records it — it never silently overwrites your change.

Run `hwr-sync conflicts` to review them interactively:

```
1/2 ───────────────────────────────
  Event:  FPM — Führung und Personalmanagement
  Status: You deleted this — HWR still has it

  HWR version:
    Start:    2026-09-03T08:00:00+00:00
    Location: CL: 6B.353

Choice (k, r, s):
  k — keep deleted
  r — restore from HWR
  s — skip, decide later
```

You can skip any item and come back to it later. The tool only considers a conflict resolved once you explicitly choose.

---

## Manual overrides

For one-off changes like a cancelled class or a room swap communicated by email, use `hwr-sync overrides` to open `overrides.yaml`:

```yaml
overrides:
  "sked.de1234567":
    title: "FPM (fällt aus)"
    cancelled: true

  "sked.de7654321":
    location: "Zoom: https://hwr-berlin.zoom.us/j/123456"
    notes: "Link from Prof email, 02.11."
```

Overridden events are never touched by the sync. If HWR changes an overridden event, you'll see a conflict notification.

---

## Scheduler

`hwr-sync start` registers a native OS scheduler. `hwr-sync stop` removes it.

| Platform | Mechanism | After sleep | After shutdown |
|---|---|---|---|
| macOS | launchd (`StartInterval` + `RunAtLoad`) | Catches up on wake | Runs on next login |
| Linux | systemd timer (`Persistent=true`) | Catches up on wake | Runs on next boot |
| Windows | Task Scheduler (interval + logon trigger) | Catches up on wake | Runs on next logon |

---

## Project structure

```
hwr_sync/
  sync.py        # single sync pass
  fetcher.py     # ICS download + parse (temp file, auto-deleted)
  filter.py      # course filters
  diff.py        # ICS vs state vs calendar — all change scenarios
  conflicts.py   # conflict storage and resolution
  state.py       # persists last-known ICS state
  config.py      # config loading, URL construction, semester detection
  notify.py      # OS-agnostic desktop notifications
  backends/      # apple | caldav | ics_file
  scheduler/     # launchd | systemd | wintask
cli.py           # hwr-sync commands
config.example.yaml
overrides.example.yaml
```
