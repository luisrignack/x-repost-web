# Desarrollo

## 1. Entorno

- Python 3.12+ (probado en 3.14.4).
- Linux con Bash 4+.
- Chrome/Chromium para pruebas manuales del motor.
- `node` opcional para validar `app.js`.
- `pytest`, `ruff`, `shellcheck`, `coverage` opcionales para CI.

No hay gestor de paquetes ni dependencias de terceros para la aplicación. Todo
el panel usa la biblioteca estándar.

## 2. Estructura

```
.
├── xrepost.sh                 CLI
├── xrepost.py                 motor (stdin en browser-use)
├── xrepost_*.py               módulos de dominio e infraestructura
├── iniciar.sh                 arranque completo
├── xrepost-chrome.sh          lanzador de Chrome
├── ci.sh                      CI local
├── sync_portable.sh           copia portable
├── web/
│   ├── app.py                 servidor y API
│   ├── static/                HTML, CSS y JS
│   └── test_*.py              pruebas del panel
├── tests/                     pruebas de módulos y CLI
└── docs/                      esta documentación
```

## 3. Convenciones

- **Sin dependencias nuevas** sin justificarlo en `CHANGELOG_TECNICO.md`.
- **Sin `shell=True`** en subprocesos.
- **Sin `innerHTML`** con datos externos en la interfaz.
- **Sin éxito supuesto**: si no se puede verificar, se registra el estado
  incierto.
- **Errores visibles**: no se capturan excepciones para ocultarlas; se traducen
  a mensajes y se registran.
- **Permisos**: todo archivo nuevo pasa por `xrepost_fs`.
- **Nombres**: `snake_case` en Python, `camelCase` en JS, `kebab-case` en CSS.
- **Idioma**: comentarios y mensajes de usuario en español; identificadores en
  inglés cuando son técnicos.

## 4. Flujo de trabajo

1. Crea una rama o usa `modernizacion-integral`.
2. Implementa el cambio en el módulo correspondiente.
3. Añade o actualiza pruebas.
4. Ejecuta:
   ```bash
   python3 -m pytest -q
   bash ./ci.sh
   node --check web/static/app.js
   ```
5. Actualiza la documentación afectada.
6. Revisa `git diff` y deja el cambio sin commit si así se pidió.

## 5. Añadir una funcionalidad

### 5.1 Dominio

- Crea el módulo `xrepost_<nombre>.py` si la lógica es reutilizable.
- Usa `xrepost_store.JsonStore` para estado JSON.
- Usa `xrepost_fs` para cualquier archivo.
- Valida toda entrada y define límites.

### 5.2 API

1. Añade la ruta en `_api_get` o `_api_post`.
2. Valida el cuerpo con una función propia.
3. Devuelve JSON y códigos HTTP coherentes.
4. Añade la prueba en `web/test_app.py`.

### 5.3 Interfaz

1. Añade la región en `index.html` con `aria-labelledby`.
2. Añade el estado y el renderizado en `app.js` usando `textContent`.
3. Añade los estilos en `styles.css` con variables de tema.
4. Verifica teclado, foco y responsive.

### 5.4 Documentación

Actualiza `API.md`, `USUARIO.md` y `CHANGELOG_TECNICO.md`.

## 6. Pruebas

La suite usa `unittest` ejecutado por `pytest`:

```bash
python3 -m pytest -q
python3 -m pytest -q tests/test_core_modules.py
python3 -m pytest -q web/test_app.py -k csrf
```

No se necesitan Chrome ni credenciales: los tests usan un motor doble
(`web/test_app.py:STUB`) y archivos temporales.

Para el motor real:

```bash
./iniciar.sh
# abrir el panel y hacer una previsualización de prueba
```

## 7. Depuración

### Panel

```bash
python3 web/app.py --port 8765 --verbose --no-scheduler
```

`--verbose` registra método, ruta y estado, nunca cabeceras ni cuerpos.

### Motor

```bash
X_APPLY=0 X_LIMIT=1 ./xrepost.sh "@foo" 01/11/2026 02/11/2026
```

Revisa la salida y el historial. Para un fallo de selector, inspecciona
`xrepost_selectors.py` y reproduce la página.

### Logs

```
~/.local/state/xrepost/panel.log
web/.runs/<id>/engine.log
```

## 8. Copia portable

`xrepost-portable/` se genera con:

```bash
./sync_portable.sh
./sync_portable.sh --check
```

Si añades un archivo que debe viajar en la copia, edita `sync_portable.sh`.
`ci.sh` falla si la copia está desincronizada.

## 9. CI

`ci.sh` ejecuta:

1. `pytest`.
2. `py_compile` de todos los módulos.
3. `bash -n` de los scripts.
4. `node --check` del JS.
5. Comprobación de la copia portable.
6. Comprobación de que los módulos importados existen (avisa si aún no están
   en git).

`.github/workflows/ci.yml` añade `ruff` (solo errores), `shellcheck` (solo
errores), cobertura informativa y la suite.

## 10. Estilo y análisis

```bash
ruff check --select E9,F63,F7,F82 .
shellcheck -S error xrepost.sh iniciar.sh web/run.sh ci.sh sync_portable.sh xrepost-chrome.sh
```

El estilo legacy no se reformatea para no generar ruido. Las reglas
seleccionadas detectan errores reales (nombres indefinidos, sintaxis).

## 11. Git

- No se hace `push` ni release sin autorización.
- No se usa `git reset --hard` ni se borran datos de usuario.
- Los cambios se revisan con `git diff` antes de commitear.
- Los módulos nuevos deben añadirse a git; `ci.sh` lo recuerda.

## 12. Seguridad en el desarrollo

- No uses tokens reales en pruebas ni en capturas.
- No ejecutes `apply` contra cuentas reales sin autorización.
- Los stubs deben usar `X_APPLY=0`.
- No desactives pruebas para que pasen: corrige el código o documenta el
  límite.

## 13. Publicación

1. `python3 -m pytest -q`
2. `bash ./ci.sh`
3. Revisar `git diff`.
4. Actualizar `CHANGELOG_TECNICO.md` e `INFORME_FINAL.md`.
5. Commit (sin push) cuando el usuario lo autorice.
