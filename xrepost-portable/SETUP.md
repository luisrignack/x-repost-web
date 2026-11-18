# xrepost — setup on a new PC

This folder is a self-contained copy of xrepost: engine, web panel, tests and
the installers/launchers. Follow the steps below once; after that, run the
program by double-clicking **X-Repost** (or with `./abrir-xrepost.sh`).

## What is in this folder

```
xrepost-portable/
├── instalar.sh              # one-step install + executable desktop shortcut
├── abrir-xrepost.sh         # launcher used by the shortcut: X + panel in tabs
├── iniciar.sh               # Chrome (CDP) + background panel + one-use URL
├── start.sh                 # terminal launcher: panel in its own window
├── install-deps.sh          # requirements check + consent-based installation
├── xrepost-icon.png         # application icon used by the shortcut
├── requirements.txt         # explicit audit/SBOM entry point (no packages)
├── SETUP.md                 # this guide
├── README.md                # full project documentation (Spanish)
├── xrepost.sh               # CLI entry point
├── xrepost.py               # engine (runs inside the browser-use harness)
├── xrepost_accounts.py      # remembered accounts + interactive prompt
├── xrepost_hashtags.py      # remembered hashtags + quote normalization
├── xrepost_labels.py        # shared result labels
├── xrepost_history.py       # shared history state (engine + panel)
├── pytest.ini               # test collection: tests/ + web/
├── web/
│   ├── app.py               # local web panel (stdlib only)
│   ├── run.sh               # panel-only launcher
│   ├── static/              # panel UI (HTML/JS/CSS)
│   └── test_*.py            # panel + engine tests
└── tests/                   # accounts/hashtags/history tests
```

## Requirements

| Requirement | Notes |
|---|---|
| Linux with a desktop session | The tool drives a real Chrome window. Locking (`flock`/`fcntl`) and date validation use GNU/Linux utilities; macOS/Windows are not supported. |
| Python **3.10+** | Standard library only — no pip packages needed for the app itself. |
| Google Chrome or Chromium | Must be launchable with `--remote-debugging-port`. |
| `browser-use` CLI | The harness that executes the engine against Chrome. Install below. |
| `pytest` (optional) | Only to run the test suite. |

## Step 1 — copy the folder

Copy `xrepost-portable/` anywhere on the target PC, e.g. `~/xrepost-portable`.
Any medium works (USB, scp, git). Then make the scripts executable:

```bash
cd ~/xrepost-portable
chmod +x instalar.sh
./instalar.sh
```

`instalar.sh` does the rest (see Step 2). If you prefer to prepare everything
by hand, make the scripts executable with
`chmod +x start.sh abrir-xrepost.sh iniciar.sh xrepost.sh web/run.sh`.

## Step 2 — install and create the desktop shortcut (recommended)

```bash
./instalar.sh              # checks/installs requirements, then creates the shortcut
./instalar.sh --no-deps    # only re/create the shortcut, leave requirements alone
```

The installer:

1. makes the launchers executable;
2. checks Python ≥ 3.10, `browser-use` and Chrome/Chromium (delegating any
   installation to `install-deps.sh`, which asks for confirmation);
3. creates **X-Repost** in your desktop folder **and** in the applications
   menu, pointing at `abrir-xrepost.sh` in this same folder;
4. marks the desktop file executable (`755`) and trusted
   (`metadata::trusted=true`, the value DING reads), so a double click
   launches it instead of opening a text editor.

Then double-click **X-Repost** on the desktop (or open it from Activities).
If the desktop still opens a text editor, right-click the icon and choose
**Allow Launching**.

## Step 3 — install the browser-use CLI (optional)

**You can skip this step:** on first launch `start.sh` checks every
requirement (Python ≥ 3.10, `browser-use`, Chrome/Chromium), runs
`browser-use --doctor`, and — if anything is missing — **asks your
permission** and installs it (system package manager for Python/Chrome,
`uv tool install --python 3.12 browser-use` for the harness). Nothing is
installed without an explicit `s`/`y` answer; declining prints the manual
commands. You can also run the checker alone:

```bash
./install-deps.sh           # check + ask to install what is missing
./install-deps.sh --check   # check only (exit 1 if something is missing)
```

To install manually instead:

```bash
# install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

uv tool install --python 3.12 browser-use
```

Alternative with pipx: `pipx install browser-use`.

Make sure the binary is on your PATH (uv puts it in `~/.local/bin`):

```bash
command -v browser-use    # must print a path
```

If it is missing, add `export PATH="$HOME/.local/bin:$PATH"` to your
`~/.bashrc` and open a new terminal.

## Step 4 — verify the copy (optional but recommended)

```bash
python3 -m pip install pytest   # or: uv tool install pytest / apt install python3-pytest
cd ~/xrepost-portable
python3 -m pytest -q            # expected: 180 passed + 32 subtests
```

All tests run offline with a simulated browser — no Chrome or X account
needed.

## Step 5 — run

Double-click **X-Repost** (desktop or applications menu), or run the
launcher from a terminal:

```bash
./abrir-xrepost.sh
```

`abrir-xrepost.sh` opens X and the panel in two tabs of the dedicated Chrome
window. The classic terminal mode with the panel in its own window is still
available:

```bash
./start.sh
```

The classic `./start.sh` mode:

1. checks requirements (Python ≥ 3.10, `browser-use`, Chrome); on the very
   first launch it also runs `browser-use --doctor`. If anything is missing
   it asks your permission and installs it (see Step 2);
2. opens Chrome with a **dedicated profile**
   (`~/.local/state/xrepost/chrome-profile`) and the CDP port `9222`, with a
   tab at **https://x.com/**;
3. starts the web panel on `127.0.0.1:8765` (random token each run);
4. opens the panel in a **separate Chrome instance** with its own profile
   (`~/.cache/xrepost-web/panel-profile`, no CDP), so a run can never
   navigate that window. Each engine run also opens its own tab in the CDP
   Chrome and closes it when it ends or is cancelled.

**First run only:** log in to X in the x.com tab. The session is stored in
the dedicated profile and survives restarts — you never log in again unless
you delete that profile or X expires the session.

Then use the panel: enter accounts and dates → **Previsualizar** → review the
list → **Repostear** (asks for explicit confirmation). Nothing is posted
without that confirmation; the CLI defaults to dry-run.

`Ctrl-C` in the terminal stops the panel; Chrome stays open.

`./abrir-xrepost.sh` — what the **X-Repost** shortcut runs — leaves the panel
running in the background and opens X and the panel in two tabs of the CDP
Chrome window; it returns immediately. If the panel is already up but has no
fresh one-use link, it renews it automatically (history and settings are kept
on disk).

### Manual alternative (without start.sh)

```bash
# terminal 1 — Chrome with CDP (Chrome 136+ blocks debugging on the default
# profile, so a dedicated --user-data-dir is mandatory)
google-chrome --user-data-dir="$HOME/.local/state/xrepost/chrome-profile" \
              --remote-debugging-port=9222 https://x.com/

# terminal 2 — panel (prints the full URL with token; opens its own window)
./web/run.sh
```

### CLI quick reference

```bash
./xrepost.sh                                   # interactive (accounts, dates, scope)
./xrepost.sh usuario1,usuario2 01/11/2026 15/11/2026   # dry-run list
X_APPLY=1 ./xrepost.sh usuario1 01/11/2026     # really repost (max 10, 20s pauses)
X_APPLY=1 ./xrepost.sh usuario1 01/11/2026 --quote "#ETECSA #Cuba"   # quote-repost
./xrepost.sh --history 20                      # last 20 history events
./xrepost.sh --undo-last                       # undo the last batch
./xrepost.sh --undo https://x.com/user/status/123   # undo one repost
```

## Where your data lives

| Path | Content |
|---|---|
| `~/.local/state/xrepost/history.jsonl` | every repost/undo event (append-only) |
| `~/.local/state/xrepost/accounts.json` | remembered accounts for autocomplete |
| `~/.local/state/xrepost/hashtags.json` | remembered hashtags |
| `~/.local/state/xrepost/chrome-profile/` | Chrome profile with your X session |
| `~/.local/state/xrepost/panel.log` | panel output from `start.sh` |
| `~/.cache/xrepost-web/panel-profile/` | Chrome profile of the panel window (separate from the CDP one) |
| `<folder>/web/.runs/` | per-run CSV/Markdown exports |

To move your history to the new PC, copy the `~/.local/state/xrepost/`
directory (the Chrome profile is optional — you can just log in again).
`X_HISTORY`, `X_ACCOUNTS`, `X_HASHTAGS` override the file locations.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `falta el CLI browser-use` | Step 2; check `~/.local/bin` is on PATH. |
| Chrome opens but CDP never responds | Another Chrome instance holds that profile. Close it (or pick another profile with `XREPOST_CHROME_PROFILE=/path`) and retry. Never use your default profile: Chrome 136+ blocks remote debugging there. |
| Panel says "Chrome no detectado" | Chrome must be running with `--remote-debugging-port=9222` (start.sh does this). Check: `curl -s http://127.0.0.1:9222/json/version`. |
| Browser shows "Panel bloqueado" / 401 | Open the exact URL printed in the terminal (it carries the token). Tokens change on every start. |
| Port 8765 busy | The panel tries 8766–8769 automatically; or set `XREPOST_PORT=9000 ./start.sh`. |
| `no encontré el botón de repost` on every post | You are not logged in to X in the CDP Chrome window, or X changed its DOM. Log in first; re-run. |
| A run navigated one of your tabs | The engine opens its own tab (`about:blank`) and closes it at the end, so this only happens with an old copy: replace `xrepost.py`. If it already happened, reopen the panel URL printed in the terminal. |
| Tests fail on `browser-use` | Tests never call the real binary — they inject a fake one. If they fail, the copy is incomplete: re-copy the whole folder. |

## Security notes

- The panel listens **only on 127.0.0.1**; it refuses other interfaces.
- Each start generates a random token; keep the printed URL private. Do not
  use a fixed guessable `--token` outside of tests.
- Reposting requires explicit confirmation in the panel (or `X_APPLY=1` in
  the CLI), enforces a minimum 5 s pause, and stops after 3 consecutive
  failures. Respect X's automation rules and keep volumes modest.