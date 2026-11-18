#!/usr/bin/env bash
# xrepost launcher — arranca Chrome (con CDP) y el panel web de una vez.
#
#   ./start.sh
#
# Abre Chrome con su perfil de CDP (https://x.com/ para iniciar sesión la
# primera vez) y arranca el panel local en una instancia de Chrome APARTE, con
# perfil propio y sin CDP, para que el motor no pueda navegar su ventana.
#
# Variables opcionales:
#   XREPOST_PORT          puerto del panel (por defecto 8765, con respaldo 8766-8769)
#   BU_CDP_URL            endpoint CDP (por defecto http://127.0.0.1:9222)
#   XREPOST_CHROME_PROFILE  perfil de Chrome (por defecto ~/.local/state/xrepost/chrome-profile)
#
# Al salir (Ctrl-C) se detiene el panel; Chrome queda abierto con tu sesión.

set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"

CDP_URL="${BU_CDP_URL:-http://127.0.0.1:9222}"
PROFILE="${XREPOST_CHROME_PROFILE:-$HOME/.local/state/xrepost/chrome-profile}"
STATE_DIR="$HOME/.local/state/xrepost"
LOG="$STATE_DIR/panel.log"

fail() { echo "Error: $*" >&2; exit 1; }

# --- requisitos (primer arranque: comprueba y, con permiso, instala) --------
export PATH="$HOME/.local/bin:$PATH"
if ! "$DIR/install-deps.sh" --check; then
  "$DIR/install-deps.sh" || fail "faltan requisitos; instálalos y vuelve a ejecutar."
fi

mkdir -p "$STATE_DIR" "$PROFILE"

# --- Chrome con CDP ---------------------------------------------------------
# Lanzador compartido: usa el binario real (no el wrapper), aplica el proxy
# guardado y limpia locks de arranques fallidos. No hace falta cerrar otros
# Chrome: el perfil es independiente.
export BU_CDP_URL="$CDP_URL"
export XREPOST_CHROME_PROFILE="$PROFILE"
echo "· Asegurando Chrome con CDP en $CDP_URL…"
bash "$DIR/xrepost-chrome.sh" || fail "no se pudo abrir Chrome con CDP"

# --- panel web --------------------------------------------------------------
TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')"
PORT_ARGS=()
[ -n "${XREPOST_PORT:-}" ] && PORT_ARGS=(--port "$XREPOST_PORT")

echo "· Arrancando el panel web…"
python3 "$DIR/web/app.py" --no-open --token "$TOKEN" "${PORT_ARGS[@]}" >"$LOG" 2>&1 &
PANEL_PID=$!
trap 'kill "$PANEL_PID" 2>/dev/null || true' EXIT

URL=""
for _ in $(seq 1 50); do
  URL="$(grep -oE 'http://127\.0\.0\.1:[0-9]+/\?token=[A-Za-z0-9_-]+' "$LOG" | head -n1 || true)"
  [ -n "$URL" ] && break
  kill -0 "$PANEL_PID" 2>/dev/null || { cat "$LOG" >&2; fail "el panel no arrancó (registro arriba)"; }
  sleep 0.2
done
[ -n "$URL" ] || { cat "$LOG" >&2; fail "el panel no mostró su URL a tiempo"; }

# El panel se abre con el mismo código que usa el servidor: una instancia de
# Chrome aparte (perfil ~/.cache/xrepost-web/panel-profile, sin CDP), de modo
# que una ejecución del motor nunca puede navegar ni traer al frente su ventana.
python3 - "$DIR" "$URL" <<'PY'
import sys
sys.path.insert(0, sys.argv[1] + "/web")
import app
app.open_panel(sys.argv[2])
PY

echo
echo "  Listo."
echo "  1) Inicia sesión en X en la pestaña https://x.com/ (solo la primera vez)."
echo "  2) Usa el panel en su ventana aparte. URL por si la necesitas de nuevo:"
echo "     $URL"
echo
echo "  Ctrl-C detiene el panel (Chrome sigue abierto con tu sesión)."
wait "$PANEL_PID"