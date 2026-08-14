# HWR Calendar Synchronizer

Syncs your HWR Berlin timetable into Apple Calendar automatically. Runs as a background job, diffs every change against what HWR last published, and respects edits you make in your calendar app — without ever silently overwriting them.

**Platform:** macOS only (Apple Calendar via EventKit). Linux and Windows support is planned.

---

## How it works

Each sync pass:
1. Fetches the ICS from HWR and applies your course filters
2. Reads your calendar to check which managed events are still there
3. Diffs ICS (what HWR says now) vs state (what HWR said last time) vs calendar (what you have)
4. Applies clean changes — adds new events, updates changed ones, deletes removed ones
5. Records divergences (things you changed or deleted) as conflicts for you to review

You are the source of truth. If you delete or modify an event, the sync never silently overwrites it — it flags a conflict and waits for your decision via `hwr-sync conflicts`.

---

## Setup

### AI-assisted (recommended)

Paste this into Claude, ChatGPT, or any AI assistant:

```
Set up hwr-calendar-synchronizer for me.

Read the README at https://github.com/lultoni/hwr-calendar-synchronizer and follow the manual setup steps. For anything that isn't clear from the README — faculty slug, semester dates, course group names, calendar name — ask me one question at a time. Do the full install and config yourself; only stop before the first `hwr-sync run` and tell me exactly what command to run and what to expect.
```

### Manual

```bash
git clone https://github.com/lultoni/hwr-calendar-synchronizer.git
cd hwr-calendar-synchronizer

# Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install (includes Apple Calendar support)
uv tool install -e ".[apple]"

# Configure
hwr-sync settings

# Test, then enable background sync
hwr-sync run
hwr-sync start
```

### Step by step

**1 — Install Python 3.11+**

Download from [python.org/downloads](https://python.org/downloads).

**2 — Install uv**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**3 — Download and install**

```bash
git clone https://github.com/lultoni/hwr-calendar-synchronizer.git
cd hwr-calendar-synchronizer
uv tool install -e ".[apple]"
```

**4 — Configure**

```bash
hwr-sync settings
```

This creates `~/.config/hwr-sync/config.yaml` if it doesn't exist yet, then opens it in your editor. Fill in your faculty, semester dates, course groups, and the name of the calendar to sync into. The file is documented with examples.

**5 — Run and start**

```bash
hwr-sync run    # test — check your calendar app after this
hwr-sync start  # enable automatic background sync
```

If the calendar named in your config doesn't exist in Apple Calendar yet, `hwr-sync run` will ask you whether to create it. To skip the prompt (e.g. in automated setups), pass `--create-missing-calendar`.

---

## Updating

```bash
cd hwr-calendar-synchronizer
git pull
uv tool install -e ".[apple]" --reinstall
```

---

## Commands

| Command | What it does |
|---|---|
| `hwr-sync run` | Run one sync pass now |
| `hwr-sync start` | Register background scheduler + sync immediately |
| `hwr-sync stop` | Remove background scheduler |
| `hwr-sync status` | Show scheduler state, active semester, last sync |
| `hwr-sync conflicts` | Check for new conflicts and resolve existing ones |
| `hwr-sync settings` | Open config.yaml in your editor (creates it if missing) |
| `hwr-sync config` | Same as `settings` |
| `hwr-sync --help` | Show all commands |

---

## Configuration

Config lives at `~/.config/hwr-sync/config.yaml`. Run `hwr-sync settings` to open it.
Logs are written to `~/.config/hwr-sync/hwr-sync.log`.

### Semesters

```yaml
faculty: "wi"
study_start_date: "2024-10-01"

semesters:
  - number: 5
    course: "kursa"          # kursa / kursb / kursc / kurs (if no a/b/c split)
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

**Group filter** — drop all events matching a pattern, except the ones you actually chose. Use this for elective modules (WPF):

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

---

## Conflicts

When you edit or delete an event in your calendar, the next sync detects the divergence and records it — it never silently overwrites your change.

Run `hwr-sync conflicts` to review them. It first runs a fresh sync to catch any new changes, then steps through each conflict:

```
1/2 ───────────────────────────────
  Event:  FPM — Führung und Personalmanagement
  Status: You deleted this — HWR still has it

  HWR version:
    Start:    Mi, 03. Sep 2026, 10:00
    Location: CL: 6B.353

Choice (k, r, s):
  k — keep deleted
  r — restore from HWR
  s — skip, decide later
```

After each item you can skip the rest and come back later. Conflicts stay open until you explicitly resolve them.

---

## Scheduler

`hwr-sync start` registers a launchd job that runs `hwr-sync run` automatically.

| Mechanism | After sleep | After shutdown |
|---|---|---|
| launchd (`StartInterval` + `RunAtLoad`) | Catches up on wake | Runs on next login |

`hwr-sync stop` removes the job. Check `~/.config/hwr-sync/hwr-sync.log` for sync history.

---

## Open items

Contributions welcome. These are the known gaps:

- **Google Calendar backend** — requires OAuth2, not yet implemented
- **Linux support** — no native calendar backend yet; launchd-equivalent scheduler needed
- **Windows support** — no native calendar backend yet; Task Scheduler integration needed

---

## Project structure

```
hwr_sync/
  cli.py           # hwr-sync commands
  sync.py          # single sync pass
  fetcher.py       # ICS download + parse
  filter.py        # course filters
  diff.py          # ICS vs state vs calendar — all change scenarios
  conflicts.py     # conflict storage and resolution
  state.py         # persists last-known ICS state
  config.py        # config loading, URL construction, semester detection
  notify.py        # macOS desktop notifications
  backends/        # apple (EventKit)
  scheduler/       # launchd
  config.example.yaml
```
