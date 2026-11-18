#!/usr/bin/env bash
# Arranque de xrepost en UN comando: Chrome con CDP + panel web + URL.
#
#   ./iniciar.sh                  -> arranca todo y abre el panel
#   ./iniciar.sh --no-open        -> arranca todo, no abre el navegador
#   ./iniciar.sh --status         -> estado de las dos piezas y de la red
#   ./iniciar.sh --stop           -> detiene el panel y el Chrome del perfil
#   ./iniciar.sh --check          -> comprueba requisitos sin arrancar nada
#
# Es idempotente: si el panel o Chrome ya están arriba, los reutiliza.

set -euo pipefail
umask 077
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
export PATH="$HOME/.local/bin:$PATH"

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/xrepost"
mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR" 2>/dev/null || true
PANEL_LOG="${XREPOST_PANEL_LOG:-$STATE_DIR/panel.log}"
TOKEN_FILE="${XREPOST_TOKEN_FILE:-$STATE_DIR/panel-token}"
BOOTSTRAP_FILE="${XREPOST_BOOTSTRAP_FILE:-$STATE_DIR/panel-url}"
CDP_URL="${BU_CDP_URL:-http://127.0.0.1:9222}"
PORT="${XREPOST_PORT:-8765}"
BASE="http://127.0.0.1:$PORT"

ACTION=start
NO_OPEN=0
for arg in "$@"; do
    case "$arg" in
        --status) ACTION=status ;;
        --stop) ACTION=stop ;;
        --check) ACTION=check ;;
        --no-open) NO_OPEN=1 ;;
        -h|--help) ACTION=help ;;
        *) echo "Opción desconocida: $arg" >&2; echo "Usa --help" >&2; exit 2 ;;
    esac
done

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

panel_up() {
    # Sin token el panel responde 401: eso también significa que está vivo.
    local code
    code="$(curl -s --max-time 2 -o /dev/null -w '%{http_code}' "$BASE/api/health" 2>/dev/null || true)"
    [ "$code" = "200" ] || [ "$code" = "401" ]
}

check_deps() {
    local fallo=0
    printf 'Python:        '
    if command -v python3 >/dev/null 2>&1; then python3 --version; else echo FALTA; fallo=1; fi
    printf 'browser-use:   '
    if command -v browser-use >/dev/null 2>&1; then browser-use --version | head -1; else
        echo "FALTA (uv tool install --python 3.12 browser-use)"; fallo=1
    fi
    printf 'curl:          '
    if command -v curl >/dev/null 2>&1; then echo OK; else echo FALTA; fallo=1; fi
    printf 'Lanzador CDP:  '
    if [ -x "$DIR/xrepost-chrome.sh" ]; then echo OK; else echo FALTA; fallo=1; fi
    printf 'Panel:         '
    if [ -f "$DIR/web/app.py" ]; then echo OK; else echo FALTA; fallo=1; fi
    return "$fallo"
}

show_status() {
    if panel_up; then echo "Panel:      ARRIBA  $BASE/"; else echo "Panel:      PARADO"; fi
    if cdp_up; then echo "Chrome CDP: ARRIBA  $CDP_URL"; else echo "Chrome CDP: PARADO"; fi
    echo "Red:        $(python3 xrepost_network.py get 2>/dev/null || echo 'sin preferencia')"
}

case "$ACTION" in
    help)
        sed -n '2,12p' "$0"
        exit 0
        ;;
    check)
        echo "== Requisitos =="
        check_deps || exit 1
        echo "== Estado =="
        show_status
        exit 0
        ;;
    status)
        show_status
        exit 0
        ;;
    stop)
        echo "· Deteniendo panel…"
        PID="$(ss -ltnp 2>/dev/null | grep ":$PORT" | grep -oP 'pid=\K[0-9]+' | head -1 || true)"
        if [ -n "$PID" ]; then kill "$PID" 2>/dev/null || true; echo "  panel detenido"; else echo "  no había panel"; fi
        echo "· Deteniendo Chrome del perfil…"
        bash "$DIR/xrepost-chrome.sh" --stop || true
        exit 0
        ;;
esac

echo "== 1/3 Requisitos =="
check_deps || { echo "Instala lo que falta y vuelve a ejecutar ./iniciar.sh" >&2; exit 1; }

echo "== 2/3 Chrome con CDP =="
if cdp_up; then
    echo "  ya estaba arriba en $CDP_URL"
else
    bash "$DIR/xrepost-chrome.sh"
fi

echo "== 3/3 Panel web =="
if panel_up; then
    echo "  ya estaba arriba en $BASE/"
else
    rm -f "$BOOTSTRAP_FILE"
    nohup python3 -u "$DIR/web/app.py" --no-open --port "$PORT" \
        --token-file "$TOKEN_FILE" --bootstrap-file "$BOOTSTRAP_FILE" \
        >"$PANEL_LOG" 2>&1 &
    listo=0
    for _ in $(seq 1 40); do
        panel_up && { listo=1; break; }
        sleep 0.5
    done
    if [ "$listo" -ne 1 ]; then
        echo "El panel no arrancó. Log:" >&2
        tail -20 "$PANEL_LOG" >&2 || true
        exit 1
    fi
    echo "  arrancado en $BASE/"
fi

URL="$BASE/"
if [ -f "$BOOTSTRAP_FILE" ]; then
    URL="$(cat "$BOOTSTRAP_FILE")"
fi
echo
echo "Listo. Abre: $URL"
echo "(El enlace de arranque está en $BOOTSTRAP_FILE, solo para tu usuario.)"
if [ "$NO_OPEN" -eq 0 ]; then
    python3 -m webbrowser -t "$URL" >/dev/null 2>&1 || true
fi
