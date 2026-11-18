#!/usr/bin/env bash
# Asegura Chrome con CDP y la configuración de proxy vigente.
#
#   ./xrepost-chrome.sh            -> reutiliza Chrome si ya escucha CDP
#   ./xrepost-chrome.sh --force    -> cierra el Chrome del perfil y lo relanza
#
# El proxy se fija al arrancar el proceso: no se puede cambiar en caliente.
# Los flags salen de xrepost_network.py (preferencia guardada por el panel).

set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

export PATH="$HOME/.local/bin:$PATH"
PROFILE="${XREPOST_CHROME_PROFILE:-$HOME/.local/state/xrepost/chrome-profile}"
CDP_URL="${BU_CDP_URL:-http://127.0.0.1:9222}"
PORT="${CDP_URL##*:}"
LOG="${XREPOST_CHROME_LOG:-/var/tmp/xrepost-chrome.log}"
FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

cdp_up() {
    python3 - "$CDP_URL" <<'PY'
import sys, urllib.request
try:
    with urllib.request.urlopen(sys.argv[1].rstrip("/") + "/json/version", timeout=1) as r:
        sys.exit(0 if r.status == 200 else 1)
except Exception:
    sys.exit(1)
PY
}

# PIDs de Chrome que usan EXACTAMENTE este perfil (nunca others).
profile_pids() {
    python3 - "$PROFILE" <<'PY'
import os, pathlib, sys
needle = "--user-data-dir=" + os.path.abspath(os.path.expanduser(sys.argv[1]))
for entry in pathlib.Path("/proc").iterdir():
    if not entry.name.isdigit():
        continue
    try:
        cmd = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
    except OSError:
        continue
    if needle in cmd:
        print(entry.name)
PY
}

if [ "$FORCE" -eq 1 ]; then
    PIDS="$(profile_pids)"
    if [ -n "$PIDS" ]; then
        echo "· Cerrando Chrome del perfil (PIDs: $PIDS)…"
        # shellcheck disable=SC2086
        kill $PIDS 2>/dev/null || true
        for _ in $(seq 1 20); do
            [ -z "$(profile_pids)" ] && break
            sleep 0.25
        done
    fi
elif cdp_up; then
    echo "· Chrome ya escucha en $CDP_URL; se reutiliza."
    exit 0
fi

# Flags de proxy según la preferencia guardada.
FLAGS=()
while IFS= read -r flag; do
    [ -n "$flag" ] && FLAGS+=("$flag")
done < <(python3 xrepost_network.py flags)

CHROME=""
for name in google-chrome google-chrome-stable chromium chromium-browser; do
    if command -v "$name" >/dev/null 2>&1; then CHROME="$name"; break; fi
done
[ -n "$CHROME" ] || { echo "No se encontró Chrome/Chromium" >&2; exit 1; }

mkdir -p "$PROFILE"
echo "· Arrancando Chrome en $CDP_URL con: ${FLAGS[*]:-sin flags}"
nohup "$CHROME" --user-data-dir="$PROFILE" \
                 --remote-debugging-port="$PORT" \
                 --no-first-run --no-default-browser-check \
                 "${FLAGS[@]}" https://x.com/ >"$LOG" 2>&1 &

for _ in $(seq 1 40); do
    cdp_up && break
    sleep 0.5
done
if ! cdp_up; then
    echo "Chrome no abrió el puerto CDP ($CDP_URL). Log:" >&2
    tail -20 "$LOG" >&2 || true
    echo "Si dice 'Opening in existing browser session.', cierra TODAS las ventanas" >&2
    echo "de Chrome y vuelve a intentarlo (el perfil dedicado no puede abrirse en paralelo)." >&2
    exit 1
fi
echo "· Chrome listo en $CDP_URL"
