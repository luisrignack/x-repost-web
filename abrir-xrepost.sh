#!/usr/bin/env bash
# Acceso directo de escritorio para X-Repost.
#
# 1. Arranca (o reutiliza) Chrome con CDP y el perfil dedicado.
# 2. Arranca (o reinicia) el panel si no hay un enlace de arranque sin usar.
# 3. Abre X y el panel en dos pestañas del mismo Chrome.
#
# Es idempotente: si ya está todo arriba, solo abre las pestañas.
# El enlace de arranque es de un solo uso: tras abrirlo se retira, y la
# siguiente pulsación renueva el panel (los datos de la bandeja e historial
# están en disco y no se pierden).

set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/xrepost"
PORT="${XREPOST_PORT:-8765}"
BASE="http://127.0.0.1:$PORT"
BOOT="${XREPOST_BOOTSTRAP_FILE:-$STATE_DIR/panel-url}"
CDP_URL="${BU_CDP_URL:-http://127.0.0.1:9222}"
LOG="$STATE_DIR/acceso-directo.log"
X_URL="${XREPOST_X_URL:-https://x.com/home}"

mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR" 2>/dev/null || true
: >>"$LOG"
chmod 600 "$LOG" 2>/dev/null || true

say() { printf '%s\n' "$*" | tee -a "$LOG"; }
fail() {
    say "ERROR: $*"
    notify-send -u critical "X-Repost" "$*" 2>/dev/null || true
    exit 1
}

panel_up() {
    local code
    code="$(curl -s --max-time 2 -o /dev/null -w '%{http_code}' "$BASE/api/health" 2>/dev/null || true)"
    [ "$code" = "200" ] || [ "$code" = "401" ]
}

cdp_up() {
    local code
    code="$(curl -s --max-time 2 -o /dev/null -w '%{http_code}' "$CDP_URL/json/version" 2>/dev/null || true)"
    [ "$code" = "200" ]
}

stop_panel() {
    local pid
    pid="$(ss -ltnp 2>/dev/null | grep -E ":$PORT([[:space:]]|$)" | grep -oP 'pid=\K[0-9]+' | head -1 || true)"
    if [ -z "$pid" ]; then
        return 0
    fi
    say "· Deteniendo el panel anterior (PID $pid)…"
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 20); do
        panel_up || return 0
        sleep 0.25
    done
    return 0
}

say "== X-Repost $(date -Iseconds) =="
notify-send "X-Repost" "Iniciando Chrome y el panel…" 2>/dev/null || true

CDP_WAS_UP=0
cdp_up && CDP_WAS_UP=1

# Chrome con CDP y el perfil dedicado (nunca el perfil personal).
bash "$DIR/xrepost-chrome.sh" >>"$LOG" 2>&1 || fail "No se pudo arrancar Chrome. Revisa $LOG"

# Enlace de arranque: solo hay uno válido si el panel se inició con
# --bootstrap-file y aún no se ha canjeado.
if panel_up; then
    if [ -s "$BOOT" ]; then
        say "· Panel ya activo; se reutiliza su enlace de arranque."
    else
        say "· Panel activo sin enlace utilizable; reiniciando solo el panel…"
        stop_panel
        rm -f "$BOOT"
        bash "$DIR/iniciar.sh" --no-open >>"$LOG" 2>&1 || fail "El panel no arrancó. Revisa $LOG"
    fi
else
    rm -f "$BOOT"
    bash "$DIR/iniciar.sh" --no-open >>"$LOG" 2>&1 || fail "El panel no arrancó. Revisa $LOG"
fi

URL="$(cat "$BOOT" 2>/dev/null || true)"
[ -n "$URL" ] || fail "No se encontró el enlace de arranque en $BOOT"

# Pestañas: X primero y el panel al final, para que quede activo.
TARGETS=()
[ "$CDP_WAS_UP" -eq 1 ] && TARGETS+=("$X_URL")
TARGETS+=("$URL")

if python3 - "$CDP_URL" "${TARGETS[@]}" <<'PY'
import sys
import urllib.parse
import urllib.request

base = sys.argv[1].rstrip("/")
targets = sys.argv[2:]
for target in targets:
    request = urllib.request.Request(
        base + "/json/new?" + urllib.parse.quote(target, safe=""),
        method="PUT",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        if response.status not in (200, 201):
            raise SystemExit(1)
PY
then
    say "· Pestañas abiertas en Chrome: X y panel."
else
    say "· CDP no aceptó nuevas pestañas; usando el navegador por defecto."
    python3 -m webbrowser -t "$X_URL" >/dev/null 2>&1 || true
    sleep 0.5
    python3 -m webbrowser -t "$URL" >/dev/null 2>&1 || true
fi

# El token de arranque ya se canjeó: no dejarlo para una reutilización fallida.
rm -f "$BOOT"
notify-send "X-Repost" "Aplicación lista: panel y X abiertos." 2>/dev/null || true
say "· Listo."
