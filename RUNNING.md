# Running xrepost

Quick guide to run the program on this machine. Full reference: `README.md`
(Spanish, CLI in depth) and `web/README.md` (panel options). To set up on
**another PC**, use the self-contained `xrepost-portable/` folder and its
`SETUP.md`.

## Requirements

- Linux desktop, Python 3.10+ (standard library only).
- `browser-use` CLI on PATH — install once:
  `uv tool install --python 3.12 browser-use`
- Google Chrome / Chromium.

## 1. Start Chrome with the control port (CDP)

The engine drives your real Chrome session through CDP. Chrome 136+ blocks
remote debugging on the default profile, so use a dedicated one:

```bash
google-chrome --user-data-dir="$HOME/.local/state/xrepost/chrome-profile" \
              --remote-debugging-port=9222 https://x.com/ &
```

Log in to X in that window **once**; the session persists in the profile.
Verify the port: `curl -s http://127.0.0.1:9222/json/version`.

Each run opens its own tab in that window (it starts at `about:blank`), navigates
only there and closes it when the run ends or is cancelled, so tabs you keep
open in that Chrome are not moved. The panel runs in a **second** Chrome window
with its own profile, so an engine run can never take it away — see
`web/README.md`.

## 2a. Run the web panel (recommended)

```bash
./web/run.sh            # or: python3 web/app.py
```

The terminal prints a URL like `http://127.0.0.1:8765/?token=…` and opens it
in a separate Chrome window. Flow: enter accounts + dates → **Previsualizar**
→ review the list, tick the posts you want (filter/sort available) →
**Repostear** (confirmation dialog shows the exact count and estimated
duration). A live progress bar and per-row status pills follow the run; the
form survives a reload and the panel reconnects to a job still running.
History tab shows every action (including the quote comment) and lets you
undo reposts — one by one or the last batch, optionally only the last N.

Useful flags: `--no-open`, `--port 9000`, `--verbose`. The panel listens only
on 127.0.0.1 and generates a random token per run.

## 2b. Run the CLI

```bash
./xrepost.sh                        # interactive: accounts, dates, scope
./xrepost.sh user1,user2 01/11/2026 15/11/2026    # dry-run (lists only)
X_APPLY=1 ./xrepost.sh user1 01/11/2026           # repost for real
X_APPLY=1 X_LIMIT=5 X_DELAY=30 ./xrepost.sh user1 01/11/2026 --quote "#ETECSA"
./xrepost.sh --history 20           # recent events
./xrepost.sh --undo-last            # undo last batch
./xrepost.sh --undo URL_OR_ID       # undo one repost
```

Nothing is posted without `X_APPLY=1` (CLI) or the confirmation dialog
(panel). Only one run at a time (file lock); history prevents repeating
posts across runs (`--force` overrides).

## Tests

```bash
python3 -m pytest -q        # from the repo root: 67 passed + 18 subtests
```

Offline: the engine tests inject a fake `browser-use`; no Chrome needed.
`pytest.ini` limits collection to `tests/` and `web/` so the portable copy
is not collected twice.

## Data locations

`~/.local/state/xrepost/`: `history.jsonl`, `accounts.json`, `hashtags.json`
(override with `X_HISTORY`, `X_ACCOUNTS`, `X_HASHTAGS`). Panel exports land
in `web/.runs/<job-id>/`.

## One-command alternative

`xrepost-portable/start.sh` does steps 1 + 2a together (Chrome with CDP and
an x.com tab, then the panel in a second window). On first launch it checks
all requirements, runs `browser-use --doctor`, and offers to install anything
missing **only after you confirm** (`install-deps.sh`). It works from this
repo copy too — see `xrepost-portable/SETUP.md`.