# Contribuir a xrepost

## Entorno

- Linux con Python 3.10 o superior.
- Chrome/Chromium para probar el motor (no necesario para la suite de pruebas).
- `node` solo para validar la sintaxis del JavaScript.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
```

**Regla de oro:** si el índice configurado (`nexus.etecsa.cu`) no responde,
reintenta directo contra PyPI antes de dar la instalación por fallida:

```bash
pip install --index-url https://pypi.org/simple -r requirements-dev.txt
```

ShellCheck y Gitleaks se instalan desde sus releases oficiales de GitHub. Si
`/tmp` no tiene cuota, exporta `TMPDIR` a una carpeta del proyecto. Los detalles
y los comandos exactos están en [`docs/TESTING.md`](docs/TESTING.md#6-instalación-de-las-herramientas-de-calidad).

## Antes de enviar cambios

```bash
bash ./ci.sh          # pytest, py_compile, bash -n, node --check, portable
ruff check --select E9,F63,F7,F82 .
bandit -q -r . -x ./xrepost-portable,./tests -ll
```

`ci.sh` es la misma guarda que ejecuta GitHub Actions. No se aceptan cambios con
pruebas desactivadas, marcadas como `skip` sin motivo o aserciones vacías.

## Estilo

- Python con anotaciones de tipos cuando el módulo ya las usa.
- Sin dependencias nuevas de ejecución salvo justificación en el PR (la
  aplicación funciona solo con la biblioteca estándar).
- Mensajes y documentación en español, identificadores en inglés.
- Los comandos externos se ejecutan con listas de argumentos, nunca con
  `shell=True`.

## Pruebas

- Añade pruebas para cada comportamiento nuevo o corregido.
- Las pruebas del motor usan el `browser-use` simulado de
  `web/test_engine_selected.py`; nunca se publica en X durante CI.
- Para cambios de interfaz, adjunta captura o descripción de la verificación
  manual en 1280×900 y 390×844.

## Commits y ramas

- Una rama por cambio relevante; `main` se mantiene funcional.
- Commits en imperativo y con prefijo (`feat:`, `fix:`, `docs:`, `test:`,
  `chore:`).
- No se hace `push --force` sobre ramas compartidas.

## Seguridad

Lee `SECURITY.md` antes de tocar autenticación, CSRF, CDP o sistema de archivos.
Cualquier cambio en esas áreas debe incluir pruebas de regresión.
