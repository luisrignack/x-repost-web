# xrepost — Issue audit (2026-11-17)

Full review of the working tree on branch `web-ui` (including uncommitted changes).
Scope: `xrepost.py`, `xrepost.sh`, `xrepost_accounts.py`, `xrepost_hashtags.py`,
`xrepost_labels.py`, `web/app.py`, `web/static/app.js`, `web/run.sh`, tests.

## Fix status (2026-11-17, same day)

| Item | Status |
|---|---|
| B1 keep-alive desync | **Fixed** — body drained on `_read_json` rejections; early POST rejections close the connection with `Connection: close`. Regression tests: `test_keep_alive_survives_rejected_post`, `test_early_rejection_closes_connection`. Live probe re-run: OK. |
| B2 undo retry hidden | **Fixed** — new shared module `xrepost_history.py` (`history_state`) used by both engine and panel; `undoable` now follows the engine's state. Tests: `tests/test_history.py`, `test_undoable_survives_failed_undo`. Live probe re-run: OK. |
| B3 untracked labels module | **Pending commit** — `xrepost_labels.py` exists and works; must be `git add`-ed together with the new `xrepost_history.py` and `tests/test_history.py` (commit not made; awaiting user). |
| B4 quote heuristic | **Fixed** — `quoted` now requires X's confirmation toast (link to the new post); otherwise `quote_unverified` (new label), which does not block retries. Tests: `test_quote_requires_confirmation_toast`, `test_quote_without_toast_is_not_marked_done`. Note: the toast selector is best-effort against X's DOM; verify once against the real site. |
| B5 limit counts only successes | **Fixed** — circuit breaker stops the batch after 3 consecutive failures. Test: `test_circuit_breaker_stops_after_three_failures`. |
| B6 malformed env crash | **Fixed** — `X_LIMIT`/`X_DELAY` parsed with a clear message and exit code 2. Test: `test_invalid_limit_exits_with_clear_message`. |
| B7 env leakage | **Fixed** — job env clears `X_ONLY_URLS_FILE`, `X_UNDO_TARGET`, `X_UNDO_N`, `X_QUOTE` (repost jobs set `X_QUOTE` from validated params). Test: `test_server_env_does_not_leak_into_jobs`. |
| B8 weak token note | **Mitigated** — `panel-url.txt` added to `.gitignore`. The running panel should be restarted without `--token xrepost-local` (use the default random token). |
| M1 poll abandonment | **Fixed** — 3 consecutive poll failures tolerated before giving up. |
| M2 delay validation | **Fixed** — UI allows 0–300 for preview, enforces ≥5 at apply (re-validated in `confirmApply`). |
| M3 mixed `posted_at` | **Fixed** — `iso_timestamp` normalizes DD/MM/YYYY → ISO at write time. Test: `test_posted_at_normalized_to_iso`. |
| M4 apply summary | **Fixed** — shows "X de Y publicaciones procesadas", excluding unprocessed rows. |
| M5 quote on undo events | **Fixed** — `quote` recorded only for repost actions (engine + panel env). |
| M6 Linux-only assumptions | Open (documented here; intended platform is Linux). |
| M7 500 echoes exception text | Open (low risk, local-only tool). |
| Improvements 2–4, 7 (pruning, collect tests, CI, shared module) | Shared module done (B2); pruning, `collect()` tests and CI still open. |

Suite after fixes: **63 passed + 14 subtests** (was 42); `node --check`,
`py_compile` and the engine's standalone fallback (no shared modules
available) verified.

---

## Verification performed

| Check | Result |
|---|---|
| `python3 -m pytest` from repo root | 42 passed + 14 subtests (15 accounts/hashtags, 23 web API, 4 engine) |
| `python3 -m py_compile` (all Python files) | OK |
| `bash -n xrepost.sh` | OK |
| `node --check web/static/app.js` | OK |
| Live probe: HTTP keep-alive after rejected POST | **Bug confirmed** (see B1) |
| Live probe: `undoable` flag after failed undo | **Bug confirmed** (see B2) |

Security posture is overall good: loopback-only bind, Host/Origin checks
(DNS-rebinding safe), constant-time token comparison, CSP, path-traversal
guards, `textContent`-only DOM rendering (no XSS), atomic writes with
`flock`, dry-run by default, explicit confirmation + minimum 5 s delay for
apply.

---

## Confirmed bugs

### B1. HTTP keep-alive desync on rejected POST — `web/app.py`

- **Where**: `Handler._read_json` (web/app.py:669) and the early error paths
  of `do_POST` (web/app.py:723).
- **What**: when a POST is rejected *before* the request body is read
  (415 wrong Content-Type, 413 body too large, 400 bad Content-Length,
  403 Host/Origin, 401 token), the server sends the error response but
  never drains the body. With `protocol_version = "HTTP/1.1"` the
  connection stays open, so the leftover body bytes are parsed as the
  next request line.
- **Reproduction** (confirmed live): on a single socket, send
  `POST /api/preview` with `Content-Type: text/plain` and a 50-byte body,
  immediately followed by a valid `GET /api/health`. Only the 415 response
  is returned; the GET is swallowed. Browsers reuse connections, so one
  rejected request can break the next request on the same connection.
- **Fix**: read/drain up to `MAX_BODY` bytes before responding, or send
  `Connection: close` (and close) on every error path that has not
  consumed the body.

### B2. Undo retry button disappears after a failed undo — `web/app.py` vs `xrepost.py`

- **Where**: `read_history` (web/app.py:228) vs `history_state`
  (xrepost.py:336-363).
- **What**: the panel marks a history row `undoable` only when the *last*
  event for the post is `repost/reposted`. The engine, however, keeps a
  repost active until an undo succeeds (`undone` or `not_reposted`);
  `undo_failed` does not remove it. After a failed undo the repost is
  still live on X and still undoable via `--undo-last`, but the panel
  hides the "Deshacer" button for that row.
- **Reproduction** (confirmed live): history with
  `repost/reposted` followed by `undo/undo_failed` for the same id →
  `read_history(...)["undoable"] == False`.
- **Fix**: derive `undoable` from the same state machine as the engine.
  Best: extract `history_state` into a shared module (same pattern as
  `xrepost_labels.py`) and use it in both places so they cannot drift.

---

## Other bugs / risks

### B3. `xrepost_labels.py` is untracked in git

- `git status` shows `?? xrepost_labels.py`, while `web/app.py:48` imports
  it unconditionally and `xrepost.sh --history` needs it
  (xrepost.sh:274-303). Committing the current diff without
  `git add xrepost_labels.py` breaks the panel (ImportError at startup)
  and `--history` on a fresh clone. The engine itself degrades gracefully
  (`_load_labels` falls back to raw codes), the panel does not.
- **Fix**: add the file to the next commit.

### B4. Quote success is a heuristic — `xrepost.py:507-511`

- `quote_repost` returns `quoted` as soon as the composer dialog closes.
  If the modal closes for any other reason (navigation, X error, focus
  loss), the post is recorded as `quoted` forever: quotes cannot be
  undone from the DOM and history skips them in every later run
  (xrepost.py:352-355). A false positive permanently blocks retrying.
- **Fix**: verify publication before recording `quoted` — e.g. check the
  success toast/link X shows after posting, or the profile page.

### B5. `X_LIMIT` counts only successes — `xrepost.py:714-725`

- `done` increments only on `reposted`/`quoted`. If every attempt fails
  (`no_button`, `no_menu`, `unconfirmed`, …), the loop keeps trying *all*
  found posts (up to 40 per user). The safety cap does not bound the
  number of browser actions, which matters for rate limiting.
- **Fix**: count attempts toward the limit, or add a consecutive-failure
  circuit breaker (e.g. stop after 3 failures in a row).

### B6. Engine crashes on malformed env vars — `xrepost.py:40-41`

- `LIMIT = int(os.environ.get("X_LIMIT", "10"))` and
  `DELAY = float(os.environ.get("X_DELAY", "20"))` raise a raw traceback
  at load time for values like `X_LIMIT=abc`. The web panel validates
  these, but CLI users get an unhandled crash.
- **Fix**: parse with try/except and exit with a clear message.

### B7. Server environment leaks into jobs — `web/app.py:444-483`

- `_environment` starts from `os.environ.copy()`. A stray
  `X_ONLY_URLS_FILE` in the server's environment would silently redirect
  *preview* jobs to a stale selected list (it is only overridden for
  apply jobs). `X_QUOTE` present in the server environment gets stamped
  onto undo events' history records (`save_event`, xrepost.py:324-325).
  `X_SKIP_REPLIES` is inherited but never exposed in the UI.
- **Fix**: explicitly clear `X_ONLY_URLS_FILE`, `X_UNDO_TARGET`,
  `X_UNDO_N` and `X_QUOTE` for job kinds that don't use them; set
  `X_SKIP_REPLIES` explicitly.

### B8. Weak fixed token documented in `panel-url.txt`

- The (untracked) note file records a panel started with
  `--token xrepost-local`. A guessable token lets any local web page set
  the auth cookie by navigating to `/?token=xrepost-local`. Cross-site
  POSTs are still blocked by the Origin check, but the token is the
  primary defense and should not be guessable.
- **Fix**: use the default random token (`secrets.token_urlsafe(18)`);
  keep `panel-url.txt` out of git (add to `.gitignore`).

---

## Minor issues

### M1. Frontend abandons job monitoring on one failed poll — `web/static/app.js:648-658`

A single transient fetch error in `watchJob` clears the interval and
sets `busy=false` while the job keeps running server-side. The UI then
allows starting another job (server answers 409). Tolerate 2–3
consecutive poll failures before giving up.

### M2. Delay validation inconsistent between UI and API

`validateParams` requires `delay >= 5` even for preview
(web/static/app.js:590); the backend allows 0–300 for preview and only
enforces ≥5 for apply (web/app.py:164-167). Harmless but inconsistent.

### M3. `posted_at` format mixed in history

Search path stores ISO timestamps; the selected-list path stores
`DD/MM/YYYY HH:MM` (whatever the preview CSV had) via
`load_selected_posts` → `save_event` (xrepost.py:278, 322). Normalize to
ISO at write time.

### M4. Misleading apply summary — `web/static/app.js:893`

"N publicaciones procesadas" counts all rows of the result CSV,
including `no procesado` ones beyond the limit.

### M5. Undo events carry a `quote` field when `X_QUOTE` is set

`save_event` adds `rec["quote"]` from the global `QUOTE_TEXT` regardless
of action (xrepost.py:324-325). Cosmetic; related to B7.

### M6. Linux-only assumptions

`valid_date` uses GNU `date -d` (xrepost.sh:74); locking uses
`flock`/`fcntl` (xrepost.sh:419, xrepost_accounts.py:233). On macOS the
date check fails and the lock is silently skipped. Fine for the intended
platform, but worth documenting.

### M7. 500 responses echo internal exception text

`do_GET`/`do_POST` return `f"Error interno: {exc}"` (web/app.py:721,
751). Local-only tool, so low risk, but paths/stack details leak to any
local client.

---

## Improvements (prioritized)

1. **Fix B1–B3** (desync, undoable logic, track `xrepost_labels.py`) —
   small changes, highest value.
2. **Prune state**: `App.jobs` dict and `web/.runs/` grow without bound
   (16 run directories already present). Keep the last ~20 jobs/runs.
3. **Test gaps**: the fake-browser harness only covers the selected-URL
   repost path. Add cases for:
   - `collect()` filtering: replies, retweets, keyword match/exclude,
     date-range edges, cross-user dedup;
   - `quote_repost`: missing quote menu, composer timeout, post button
     never enabled;
   - `undo_one` / `--undo-last` / `--undo URL`, including `undo_failed`
     retry (would have caught B2).
4. **CI + linters**: no CI exists. Add a workflow running `pytest`,
   `ruff` and `shellcheck`; it would catch the B3 class of bug
   (untracked import) automatically.
5. **Quote verification** (B4) before trusting history for quotes.
6. **Action cap / circuit breaker** (B5) to bound browser actions per run.
7. **Shared history state module**: one implementation of
   `history_state` used by engine, `--history` and panel, so labels and
   undoability never drift again (extends the `xrepost_labels.py`
   pattern).