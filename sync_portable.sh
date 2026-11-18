#!/usr/bin/env bash
# Sincroniza xrepost-portable/ desde el repo (o verifica que esté al día).
# Uso: ./sync_portable.sh          -> copia los archivos
#      ./sync_portable.sh --check  -> solo comprueba, exit 1 si hay diferencias
set -euo pipefail
cd "$(dirname "$0")"

DST=xrepost-portable
FILES=(
    README.md pytest.ini
    xrepost.py xrepost.sh xrepost_accounts.py xrepost_hashtags.py
    xrepost_history.py xrepost_labels.py
    web/app.py web/run.sh web/README.md web/test_app.py web/test_engine_selected.py
    web/static/app.js web/static/index.html web/static/styles.css
    tests/test_accounts.py tests/test_hashtags.py tests/test_history.py
)

if [ "${1:-}" = "--check" ]; then
    rc=0
    for f in "${FILES[@]}"; do
        if [ ! -f "$DST/$f" ]; then
            echo "FALTA $DST/$f"
            rc=1
        elif ! cmp -s "$f" "$DST/$f"; then
            echo "DESINCRONIZADO $f"
            rc=1
        fi
    done
    if [ "$rc" -eq 0 ]; then
        echo "portable sincronizado (${#FILES[@]} archivos)"
    else
        echo "Ejecuta ./sync_portable.sh para actualizar la copia portable." >&2
    fi
    exit "$rc"
fi

for f in "${FILES[@]}"; do
    mkdir -p "$DST/$(dirname "$f")"
    cp -p "$f" "$DST/$f"
done
echo "portable actualizado (${#FILES[@]} archivos)"
