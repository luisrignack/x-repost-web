#!/usr/bin/env bash
# Instala X-Repost en este PC y crea el acceso directo del escritorio.
#
#   ./instalar.sh              comprueba/instala requisitos y crea el acceso
#   ./instalar.sh --no-deps    no toca los requisitos; solo prepara el acceso
#   ./instalar.sh --help       muestra esta ayuda
#
# El acceso queda ejecutable y marcado como de confianza para GNOME/DING, y
# también se registra en el menú de aplicaciones. No hace falta sudo: si faltan
# paquetes, install-deps.sh los instala pidiendo confirmación.

set -euo pipefail
umask 022
DIR="$(cd "$(dirname "$0")" && pwd)"
SELF="$DIR/$(basename "$0")"
cd "$DIR"

NO_DEPS=0
for arg in "$@"; do
    case "$arg" in
        --no-deps) NO_DEPS=1 ;;
        -h|--help) sed -n '2,10p' "$SELF"; exit 0 ;;
        *) echo "Opción desconocida: $arg" >&2; exit 2 ;;
    esac
done

say() { printf '· %s\n' "$*"; }
warn() { printf 'AVISO: %s\n' "$*" >&2; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -ne 0 ] || die "No ejecutes este instalador con sudo: el acceso debe pertenecer al usuario del escritorio."

for f in web/app.py iniciar.sh abrir-xrepost.sh xrepost-chrome.sh xrepost.sh install-deps.sh; do
    [ -f "$DIR/$f" ] || die "Falta $f: la carpeta portable está incompleta."
done

say "Preparando permisos de ejecución…"
chmod +x start.sh iniciar.sh abrir-xrepost.sh install-deps.sh xrepost.sh \
    xrepost-chrome.sh ci.sh web/run.sh 2>/dev/null || true

if [ "$NO_DEPS" -eq 0 ]; then
    if ./install-deps.sh --check >/dev/null 2>&1; then
        say "Requisitos presentes (Python 3.10+, browser-use y Chrome/Chromium)."
    else
        say "Faltan requisitos; se instalarán solo si los confirmas."
        ./install-deps.sh || die "No se pudieron instalar los requisitos. Ejecuta ./install-deps.sh y reintenta."
    fi
else
    warn "Se omite la comprobación de requisitos (--no-deps)."
fi

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/xrepost"
mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR" 2>/dev/null || true

DESKTOP_DIR=""
if command -v xdg-user-dir >/dev/null 2>&1; then
    DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
fi
if [ -z "$DESKTOP_DIR" ] || [ "$DESKTOP_DIR" = "$HOME" ]; then
    DESKTOP_DIR="$HOME/Desktop"
fi
mkdir -p "$DESKTOP_DIR" || die "No se pudo crear el escritorio en $DESKTOP_DIR"

APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$APPS_DIR"

# Icono propio si viaja con la carpeta; si no, el icono del tema.
ICON_FILE="$DIR/xrepost-icon.png"
if [ -f "$ICON_FILE" ]; then
    ICON_LINE="$ICON_FILE"
else
    ICON_LINE="applications-internet"
fi

# Exec se escribe entre comillas y con los caracteres reservados escapados,
# para que funcione aunque la carpeta tenga espacios.
EXEC_ESCAPED="$(printf '%s' "$DIR/abrir-xrepost.sh" | sed 's/[\\"`$]/\\&/g; s/%/%%/g')"
EXEC_LINE="\"$EXEC_ESCAPED\""

write_desktop() {
    local target="$1" mode="$2"
    cat >"$target" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=X-Repost
Name[es]=X-Repost
Comment=Repostear y gestionar X desde el panel local
Comment[es]=Repostear y gestionar X desde el panel local
Exec=$EXEC_LINE
Path=$DIR
Icon=$ICON_LINE
Terminal=false
Categories=Network;
StartupNotify=true
EOF
    chmod "$mode" "$target"
}

DESKTOP_FILE="$DESKTOP_DIR/x-repost.desktop"
APP_FILE="$APPS_DIR/x-repost.desktop"

say "Creando el acceso del escritorio…"
write_desktop "$DESKTOP_FILE" 755
write_desktop "$APP_FILE" 644

# DING (escritorio de Ubuntu/GNOME) lee metadata::trusted como cadena y exige
# exactamente "true". GIO no admite booleanos en esta clave, así que se escribe
# como texto; además el archivo ya es ejecutable (755) para el resto de shells.
if command -v gio >/dev/null 2>&1; then
    if gio set "$DESKTOP_FILE" metadata::trusted true 2>/dev/null; then
        TRUSTED="$(gio info -a metadata::trusted "$DESKTOP_FILE" 2>/dev/null \
            | sed -n 's/^[[:space:]]*metadata::trusted:[[:space:]]*//p' | head -1)"
        if [ "$TRUSTED" = "true" ]; then
            say "Acceso marcado como de confianza."
        else
            warn "No se pudo verificar metadata::trusted; si GNOME abre un editor, usa clic derecho → Permitir lanzar."
        fi
    else
        warn "No se pudo marcar la confianza con gio; usa clic derecho → Permitir lanzar."
    fi
else
    warn "gio no está disponible; el acceso es ejecutable, pero GNOME puede pedir confirmación."
fi

if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate "$DESKTOP_FILE" || warn "desktop-file-validate reportó avisos en $DESKTOP_FILE"
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
fi

echo
say "Acceso del escritorio: $DESKTOP_FILE"
say "Menú de aplicaciones:  $APP_FILE"
say "Lanzador:              $DIR/abrir-xrepost.sh"
echo
echo "Doble clic en el icono «X-Repost» del escritorio."
echo "También puedes abrirlo desde Actividades → X-Repost."
echo "La primera vez, inicia sesión en X en la pestaña que se abre."
echo "Si el escritorio abre un editor, clic derecho → «Permitir lanzar»."
