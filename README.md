# HWR Calendar Synchronizer

Syncs your HWR Berlin timetable into Apple Calendar or Outlook/Teams automatically. Runs as a background job, diffs every change against what HWR last published, and respects edits you make in your calendar app — without ever silently overwriting them.

**Platform:** macOS only. Linux and Windows support is planned.

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

**Apple Calendar:**

```bash
git clone https://github.com/lultoni/hwr-calendar-synchronizer.git
cd hwr-calendar-synchronizer

# Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

uv tool install -e ".[apple]"
hwr-sync settings
hwr-sync run
hwr-sync start
```

**Outlook / Teams (work & university accounts):**

```bash
git clone https://github.com/lultoni/hwr-calendar-synchronizer.git
cd hwr-calendar-synchronizer

curl -LsSf https://astral.sh/uv/install.sh | sh

uv tool install -e ".[outlook]"
hwr-sync settings   # set calendar_backend: outlook and calendar_name
hwr-sync run        # opens a one-time browser login, then syncs
hwr-sync start
```

On first run you'll be shown a URL and a short code. Open the URL in any browser, sign in with your work or university Microsoft account, and enter the code. That's it — all future syncs run silently in the background without any further interaction.

> **Personal Microsoft accounts** work the same way. See the Configuration section for the optional `microsoft_client_id` / `microsoft_tenant_id` keys if you need to point the tool at a specific Azure app registration.

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

# Apple Calendar
uv tool install -e ".[apple]"

# Outlook / Teams
uv tool install -e ".[outlook]"
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

If the calendar named in your config doesn't exist yet, pass `--create-missing-calendar` to have it created automatically.

> **Switching backends?** Just change `calendar_backend` in your config and reinstall with the correct extras flag (e.g. `uv tool install -e '.[outlook]' --reinstall`). Each backend keeps its own state file — conflicts and overrides carry over automatically.

---

## Updating

```bash
cd hwr-calendar-synchronizer
git pull

# Apple Calendar
uv tool install -e ".[apple]" --reinstall

# Outlook / Teams
uv tool install -e ".[outlook]" --reinstall

hwr-sync stop && hwr-sync start
```

---

## Commands

| Command | What it does |
|---|---|
| `hwr-sync run` | Run one sync pass now |
| `hwr-sync start [--interval N]` | Register background scheduler + sync immediately |
| `hwr-sync stop` | Remove background scheduler |
| `hwr-sync status` | Scheduler state, next sync time, active semester, open conflicts |
| `hwr-sync conflicts` | Resolve open conflicts interactively |
| `hwr-sync conflicts --sync` | Scan for new conflicts first, then resolve |
| `hwr-sync settings` | Open config.yaml in your editor (creates it if missing) |
| `hwr-sync config` | Same as `settings` |
| `hwr-sync --verbose` | Show debug-level output on the terminal |
| `hwr-sync --help` | Show all commands and options |

---

## Configuration

Config lives at `~/.config/hwr-sync/config.yaml`. Run `hwr-sync settings` to open it.
Logs are written to `~/.config/hwr-sync/hwr-sync.log` (rotates at 1 MB, keeps 3 files).

The tool also maintains two internal files you don't normally need to touch:
- `~/.config/hwr-sync/state.json` — last-known ICS snapshot, used to detect what HWR changed
- `~/.config/hwr-sync/conflicts.json` — open conflicts waiting for your resolution

### Calendar backend

```yaml
calendar_backend: "apple"    # Apple Calendar (macOS, default)
calendar_backend: "outlook"  # Outlook / Teams (work & university accounts)
```

For the Outlook backend, two additional keys are needed:

```yaml
microsoft_client_id: "14d82eec-204b-4c2f-b7e8-296a70dab67e"
microsoft_tenant_id: "common"
```

**Most users don't need to change these.** The defaults above use Microsoft's own Graph Explorer app registration, which works for any work or university Microsoft account with no Azure setup required. The one-time browser login handles everything.

The only reason to change them is if your organisation has disabled user consent for third-party apps — in that case your IT admin needs to register a dedicated Azure AD app (public client, `Calendars.ReadWrite` delegated permission, device code flow enabled) and give you its client ID and tenant ID to put here.

### Semesters

```yaml
faculty: "wi"              # from the HWR calendar page (see below)
study_start_date: "2024-10-01"

semesters:
  - number: 5
    course: "kursa"          # kursa / kursb / kursc / kurs (if no a/b/c split)
    end_date: "2027-01-31"   # include Praxisphase
  - number: 6
    course: "kursa"
    end_date: "2027-09-30"
```

Find your `faculty` and `course` values in your timetable URL on the [HWR calendar page](https://moodle.hwr-berlin.de/fb2-stundenplan/). The URL pattern is `.../fb2-stundenplaene/{faculty}/semester{N}/{course}`.

The tool auto-detects the active semester from today's date and stops syncing after the last `end_date`.

### Filters

Each semester can define its own filters. Leave the global `filters` block empty to keep all events.

**Hard exclude** — always drop these:

```yaml
filters:
  exclude_title_contains:
    - "Wegezeit"
  exclude_by_regex:
    - "^Englisch.*B1$"
```

**Group filter** — drop all events matching a pattern, except the ones you actually chose. Useful for elective modules (WPF):

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

When you edit or delete a managed event, the sync records it as a conflict instead of overwriting your change. Room changes and renames from HWR are applied automatically — a conflict only fires when both sides diverged.

Run `hwr-sync conflicts` to step through them:

```
1 conflict(s) to review.

Options per item:  [k] keep yours  [r] restore from HWR  [s] skip (decide later)

─── 1/1 ───────────────────────────────
  Event:  FPM — Führung und Personalmanagement
  Status: You deleted this — HWR still has it

  HWR version:
    Title:    FPM — Führung und Personalmanagement
    Start:    Wed, 03. Sep 2026, 10:00
    End:      Wed, 03. Sep 2026, 12:00
    Location: CL: 6B.353

Choice (k, r, s) [s]:
```

After each item you can skip the rest and come back later. Conflicts stay open until you explicitly resolve them. Pass `--sync` to run a fresh sync pass before the review session if you want to pick up anything new first.

---

## Scheduler

`hwr-sync start` registers a launchd job that fires at fixed clock times throughout the day. For the default 6h interval that's 00:00, 06:00, 12:00, 18:00. Clock-based scheduling means it catches up correctly after sleep or reboot — if the Mac was asleep at a scheduled time, the job runs on the next wake.

Use `--interval N` to set a different interval. For clean divisors of 24 (1, 2, 3, 4, 6, 8, 12) all gaps are equal. For other values the fire times are still evenly spaced from midnight but the overnight gap may be shorter (e.g. `--interval 5` fires at 00, 05, 10, 15, 20 — the 20→00 gap is 4h).

`hwr-sync stop` removes the job. `hwr-sync status` shows the next scheduled fire time.

---

## Open items

- **Google Calendar backend** — requires OAuth2, not yet implemented
- **Linux / Windows support** — no scheduler integration yet

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
  backends/        # apple (EventKit), outlook (Microsoft Graph)
  scheduler/       # launchd
  config.example.yaml
```
