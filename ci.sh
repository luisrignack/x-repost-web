#!/usr/bin/env bash
# CI local de xrepost. Ejecutar antes de cada commit (o desde un hook/CI remoto).
# Comprueba tests, sintaxis y que todo módulo local importado esté en git.
set -euo pipefail
cd "$(dirname "$0")"

echo "== pytest =="
python3 -m pytest -q

echo "== py_compile =="
python3 -m py_compile xrepost*.py web/app.py

echo "== bash -n =="
bash -n xrepost.sh
shopt -s nullglob
for s in xrepost-portable/*.sh; do
    bash -n "$s"
done
shopt -u nullglob

echo "== node --check =="
node --check web/static/app.js

echo "== imports locales trackeados =="
status=0
modules=$(grep -hoE '^import xrepost_[a-z_]+' xrepost*.py web/app.py | awk '{print $2}' | sort -u)
for m in $modules; do
    if git ls-files --error-unmatch "$m.py" >/dev/null 2>&1; then
        echo "  OK $m"
    else
        echo "  FALTA $m.py (no trackeado: el panel romperá en un clone fresco)"
        status=1
    fi
done

if [ "$status" -ne 0 ]; then
    echo "Fallo: añade los módulos faltantes con git add antes de commitear." >&2
    exit 1
fi

echo "CI OK"
