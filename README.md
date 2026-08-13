# HWR Calendar Synchronizer

Automatically syncs your HWR Berlin timetable into Apple Calendar, CalDAV (iCloud, Nextcloud, ...), or a subscribable ICS file — on macOS, Linux, and Windows.

Runs as a background job that checks for changes every few hours. Smart diff: only adds, updates, or deletes events that actually changed. Manual overrides are never overwritten.

---

## Quick Start

### For Techies

```bash
# 1. Clone and enter the project
git clone https://github.com/YOUR_USERNAME/hwr-calendar-synchronizer.git
cd hwr-calendar-synchronizer

# 2. Install uv (if you don't have it)
curl -LsSf https://astral.sh/uv/install.sh | sh   # macOS / Linux
# Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 3. Install hwr-sync as a global CLI tool
uv tool install -e .

# macOS only — for native Apple Calendar integration
uv tool install -e ".[apple]"

# 4. Create your config (must be run from the project directory)
cp config.example.yaml config.yaml
hwr-sync settings   # opens config.yaml in your editor

# 5. Run once to test
hwr-sync run

# 6. Start the background scheduler
hwr-sync start
```

---

### For Non-Techies (step by step)

Don't worry — you only need to do this once.

**Step 1 — Install Python**

- Go to [python.org/downloads](https://python.org/downloads) and download Python 3.11 or newer.
- During installation on Windows: check "Add Python to PATH".
- On macOS you can also use the Terminal app and run: `brew install python` (if you have Homebrew).

**Step 2 — Install uv (a package manager)**

Open your Terminal (macOS/Linux) or Command Prompt (Windows) and paste:

```
# macOS / Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (in PowerShell):
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Step 3 — Download this project**

```
git clone https://github.com/YOUR_USERNAME/hwr-calendar-synchronizer.git
cd hwr-calendar-synchronizer
```

No git? Download the ZIP from GitHub and unzip it, then open a terminal in that folder.

**Step 4 — Install the tool**

```
uv tool install -e .
```

On macOS, add this too for Apple Calendar support:
```
uv tool install -e ".[apple]"
```

This makes `hwr-sync` available as a command anywhere on your system.

**Step 5 — Configure**

```
cp config.example.yaml config.yaml
hwr-sync settings
```

A text file opens. Fill in:
- `faculty`: your degree program (e.g. `wi` for Wirtschaftsinformatik)
- `semesters`: your course group per semester (see the HWR timetable page), including end dates
- `calendar_name`: the name of the calendar in your app (create one called `University` first)

Save and close the file.

**Step 6 — Test it**

```
hwr-sync run
```

Open your calendar app — your timetable should appear.

**Step 7 — Make it automatic**

```
hwr-sync start
```

Done. The tool now syncs in the background every few hours.

---

## AI-Assisted Setup

Paste the following prompt directly into Claude, ChatGPT, or any other AI assistant. It will walk you through the complete setup interactively — cloning the repo, installing everything, and filling in your config together with you.

```
I want to set up hwr-calendar-synchronizer on my computer. Please help me through the complete setup.

Here is what I need you to do:
1. Check if git, Python 3.11+ and uv are installed on my system, and guide me through installing any that are missing.
2. Clone the repository: https://github.com/YOUR_USERNAME/hwr-calendar-synchronizer
3. cd into the project directory and run: uv tool install -e ".[apple]" (macOS) or uv tool install -e . (Linux/Windows)
4. Ask me the following questions one at a time, then write my config.yaml:
   - What is your faculty/degree program? (e.g. wi, informatik, IP, industrie)
   - For each semester: what is your course group? (kursa, kursb, kursc, or kurs) and when does it end?
   - Do you have elective modules (WPF)? If so, which ones are yours?
   - What should the calendar be called in your calendar app?
   - Which calendar app do you use? (Apple Calendar, iCloud CalDAV, Google Calendar, or just export a file)
5. Run `hwr-sync run` to test and confirm events appear.
6. Run `hwr-sync start` to enable automatic background sync.

Start by asking me what operating system I am on.
```

---

## Commands

| Command | What it does |
|---|---|
| `hwr-sync run` | Sync once right now |
| `hwr-sync start` | Register background scheduler + immediate sync |
| `hwr-sync stop` | Remove background scheduler |
| `hwr-sync status` | Show scheduler state, active semester, last sync |
| `hwr-sync settings` | Open `config.yaml` in your editor |
| `hwr-sync overrides` | Open `overrides.yaml` in your editor |
| `hwr-sync --help` | Show all commands |

> **Note:** `hwr-sync settings` and `hwr-sync overrides` open files in the directory where you run the command. Always run `hwr-sync` from the project directory, or set an absolute path in a shell alias.

---

## Filters

Edit `config.yaml` to control which courses appear in your calendar.

### Hard excludes

Always drop specific events, no exceptions:

```yaml
filters:
  exclude_title_contains:
    - "Wegezeit"
  exclude_by_regex:
    - "^Englisch.*B1$"
```

### Group filters (for elective modules / WPF)

Drop all events in a group, except the ones you actually chose. You can define multiple independent groups:

```yaml
filters:
  groups:
    - match_regex: "(?i)WPF"
      keep:
        - "Cross Cultural Management"
        - "Social Innovation"
    - match_regex: "(?i)Englisch"
      keep:
        - "Englisch C1"
```

### Per-semester filters

Each semester can have its own `filters` block that overrides the global one — useful when your electives change each semester:

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
  - number: 6
    course: "kursa"
    end_date: "2027-09-30"
    filters:
      groups:
        - match_regex: "(?i)WPF"
          keep:
            - "Design Thinking"
            - "Responsible Tech"
```

---

## Manual Overrides

If a professor cancels a class or changes the room via email, you can override that event without it being overwritten on the next sync.

Run `hwr-sync overrides` to open `overrides.yaml`. Add an entry like this:

```yaml
overrides:
  "YOUR-EVENT-UID-HERE":
    title: "FPM (fällt aus)"
    cancelled: true

  "ANOTHER-UID":
    location: "Zoom: https://hwr-berlin.zoom.us/j/123456"
    notes: "Link from Prof email, 02.11."
```

The UID of an event is the `UID:` field in the raw ICS — visible in the log when running `hwr-sync run`.

Overrides are **never overwritten** by the sync. If the ICS changes for an overridden event, you'll see a warning in the log — your override stays until you remove it manually.

---

## Scheduler Behavior

| Platform | Mechanism | Survives sleep? | Survives shutdown? |
|---|---|---|---|
| macOS | launchd (`RunAtLoad` + `StartInterval`) | Yes (catch-up on wake) | Runs on next login |
| Linux | systemd timer (`Persistent=true`) | Yes | Yes (runs on next boot) |
| Windows | Task Scheduler (interval + logon trigger) | Yes | Runs on next logon |

---

## Calendar Backends

| Backend | When to use |
|---|---|
| `apple` | macOS with Apple Calendar (auto-detected on macOS) |
| `caldav` | iCloud, Nextcloud, any CalDAV server — set `caldav_url` in config |
| `ics_file` | Generates a `hwr_schedule.ics` file you can subscribe to in any app |

`calendar_backend: auto` detects your OS on first run and writes the result to `config.yaml`.

---

## Project Structure

```
hwr-calendar-synchronizer/
├── hwr_sync/
│   ├── sync.py          # single sync pass (the core)
│   ├── fetcher.py       # ICS download + parse (uses temp file, auto-deleted)
│   ├── filter.py        # course filters
│   ├── diff.py          # change detection (all scenarios)
│   ├── state.py         # local state (state.json)
│   ├── config.py        # config + URL construction + semester detection
│   ├── notify.py        # OS-agnostic desktop notifications
│   ├── backends/        # apple | caldav | ics_file
│   └── scheduler/       # launchd | systemd | wintask
├── cli.py               # hwr-sync commands
├── config.example.yaml  # copy to config.yaml and fill in your details
├── overrides.example.yaml
└── pyproject.toml
```
