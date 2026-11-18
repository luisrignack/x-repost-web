# Pruebas

## 1. Resumen

| Métrica | Valor |
| --- | --- |
| Marco | `unittest` ejecutado con `pytest` |
| Pruebas recopiladas | **171** |
| Subpruebas | **18** |
| Resultado local | **171 passed, 18 subtests passed** |
| Cobertura (módulos de negocio) | **91 %** |
| Cobertura total (incluye CLI y panel) | **85 %** |
| Python | 3.14.4 |
| Duración aproximada | 39 s |
| Navegador necesario | No |
| Credenciales necesarias | No |

```bash
python3 -m pytest -q
# 171 passed, 18 subtests passed
```

## 2. Distribución

| Archivo | Pruebas | Ámbito |
| --- | --- | --- |
| `tests/test_core_modules.py` | 59 | Sistema de archivos, almacén JSON, seguridad, CDP, filtros, trabajos, exportaciones, grupos, bandeja, programación, estadísticas, historial y máquina de estados. |
| `web/test_app.py` | 55 | Contrato HTTP del panel: auth, CSRF, trabajos, perfiles, grupos, bandeja, programación, estadísticas, backups, exportaciones y UI. |
| `web/test_engine_selected.py` | 15 | Sondas y selectores del motor sin abrir Chrome. |
| `tests/test_history.py` | 12 | Estado compartido del historial. |
| `tests/test_network.py` | 10 | Preferencias de red y flags de Chrome. |
| `tests/test_hashtags.py` | 8 | Normalización y sugerencias de hashtags. |
| `tests/test_accounts.py` | 7 | Cuentas recordadas y sugerencias. |
| `tests/test_start_script.py` | 5 | Arranque y comprobaciones de `iniciar.sh`. |

## 3. Qué cubre cada bloque

### 3.1 Seguridad

- Token maestro demasiado corto.
- Comparación constante en el tiempo.
- Creación, rotación, revocación y caducidad de sesiones.
- CSRF correcto e incorrecto.
- Límite de fallos y bloqueo.
- Cookies `HttpOnly`/`SameSite`.
- `Host` y `Origin` permitidos y rechazados.
- CSRF obligatorio en escrituras del panel.
- Rotación de sesión y logout.
- Rechazo de `Origin` externo.

### 3.2 Sistema de archivos

- Escritura atómica y permisos 0600/0700.
- Lectura con límite de tamaño.
- Rechazo de symlinks.
- `safe_join` y `remove_tree` fuera de la base.
- JSON corrupto y cuarentena.

### 3.3 Estado

- Perfiles: crear, actualizar, duplicar, borrar, importar/exportar.
- Grupos: miembros, alias, duplicados, límites.
- Bandeja: alta, decisión, estados, importación.
- Programación: frecuencias, próxima ejecución, vencimiento.
- Trabajos: ciclo de vida, recuperación, poda, saneado de parámetros.

### 3.4 Motor

- Selectores y sondas JS (sin navegador).
- Validación de fechas, usuarios y límites.
- Resultados inciertos y bloqueos.
- Historial: repost, undo, `undo_failed`, `not_reposted`.
- Exportaciones CSV/Markdown/JSON/HTML/PDF.

### 3.5 Panel

- `/api/session`, `/api/session/rotate`, `/api/session/logout`.
- `/api/health`, `/api/stats`, `/api/diagnostics`, `/api/cdp`.
- `/api/jobs` y exportaciones por trabajo.
- Perfiles, grupos, bandeja, programación.
- Backup y restauración.
- Descargas y cabeceras.
- Estructura de la UI, pestañas, CSRF y temas.

## 4. Pruebas que no se ejecutan localmente

| Prueba | Motivo | Cómo se cubre |
| --- | --- | --- |
| Navegación real en X | Requiere cuenta y red | Verificación manual con una cuenta de prueba. |
| Repost real | Prohibido publicar sin autorización | Stub del motor y pruebas de estado. |
| Chrome/CDP real | Requiere sesión gráfica | `xrepost_cdp` se prueba con endpoints simulados y `--strict-cdp`. |
| Mypy estricto | Deuda de tipado en módulos históricos | Se ejecuta en CI como informativo (`continue-on-error`). |

## 5. Cobertura

Medida con `coverage 7.17.3` (rama activada) sobre los módulos de negocio:

```bash
python -m coverage run --branch -m pytest -q
python -m coverage report \
  --include='xrepost_fs.py,xrepost_store.py,xrepost_filters.py,xrepost_cdp.py,xrepost_security.py,xrepost_jobs.py,xrepost_exports.py,xrepost_groups.py,xrepost_inbox.py,xrepost_schedule.py,xrepost_stats.py,xrepost_history.py,xrepost_selectors.py,xrepost_state.py'
```

| Módulo | Cobertura |
| --- | --- |
| `xrepost_schedule.py` | 99 % |
| `xrepost_security.py` | 96 % |
| `xrepost_groups.py` | 95 % |
| `xrepost_filters.py` | 94 % |
| `xrepost_history.py` | 94 % |
| `xrepost_state.py` | 94 % |
| `xrepost_store.py` | 90 % |
| `xrepost_exports.py` | 89 % |
| `xrepost_jobs.py` | 87 % |
| `xrepost_inbox.py` | 86 % |
| `xrepost_cdp.py` | 85 % |
| `xrepost_fs.py` | 83 % |
| `xrepost_stats.py` | 82 % |
| **Total de negocio** | **91 %** |
| **Total del proyecto** | **85 %** |

CI exige `--fail-under=90` para ese conjunto. La cobertura total es menor por
`xrepost_accounts.py` (CLI interactivo) y `web/app.py`; sus caminos críticos
están cubiertos por `web/test_app.py` (55 pruebas).

## 6. Pruebas del panel con motor doble

`web/test_app.py` define `STUB`, un script Python que imita la salida del
motor sin abrir Chrome. El servidor lo ejecuta como si fuera `xrepost.sh`.
Esto permite probar:

- Previsualización y ejecución completas.
- Parseo de líneas de progreso.
- Reconciliación de la bandeja.
- Cancelación y timeout.
- Exportaciones.

El stub nunca publica nada.

## 7. Pruebas de la interfaz

Se comprueba que:

- Existen las 8 pestañas y los paneles correspondientes.
- Los IDs usados por `app.js` existen en `index.html`.
- Las escrituras incluyen `X-CSRF-Token`.
- El tema se aplica con `data-theme`.
- El diálogo de confirmación exige la casilla.
- No hay HTML desbalanceado.

La validación de sintaxis:

```bash
node --check web/static/app.js
```

## 8. Pruebas del CLI

`tests/test_start_script.py` y `web/test_engine_selected.py` verifican:

- `iniciar.sh --check` no instala nada sin consentimiento.
- El token no se imprime en el log.
- Las fechas y los límites se validan.
- Los modos `undo`, `undo_last` y `history` se reconocen.
- Los selectores contienen alternativas en español e inglés.

## 9. Ejecución selectiva

```bash
python3 -m pytest -q tests/test_core_modules.py
python3 -m pytest -q web/test_app.py -k "csrf or session"
python3 -m pytest -q -k "backup or restore"
python3 -m pytest -q --maxfail=1
```

## 10. CI

`ci.sh`:

```bash
python3 -m pytest -q
python3 -m py_compile xrepost*.py web/app.py
bash -n xrepost.sh
node --check web/static/app.js
./sync_portable.sh --check
# comprueba que los módulos importados existen
```

`.github/workflows/ci.yml` añade:

- `ruff check --select E9,F63,F7,F82 .` (bloqueante, sin hallazgos).
- `shellcheck -S error …` (bloqueante).
- `bandit -ll` (bloqueante; 0 hallazgos medium/high).
- `pip-audit -r requirements.txt` (sin dependencias de ejecución).
- `gitleaks detect --no-git` (bloqueante; sin fugas en el árbol actual).
- `mypy` informativo sobre los módulos nuevos.
- Cobertura con umbral del 90 %.
- SBOM CycloneDX, paquete `tar.gz`, `SHA256SUMS` y artefactos.
- La suite completa de `ci.sh`.

## 11. Criterios para añadir una prueba

1. Debe fallar sin el cambio y pasar con él.
2. No debe depender del orden de ejecución.
3. Debe usar un directorio temporal.
4. No debe tocar el estado real del usuario.
5. No debe publicar en X.
6. Debe probar el camino de error relevante, no solo el feliz.

## 12. Limitaciones

- No hay pruebas end-to-end contra X por las restricciones de la tarea.
- La cobertura no se midió localmente.
- Las pruebas de la UI no sustituyen una auditoría de accesibilidad con lector
  de pantalla; se verifican estructura, foco y contraste de forma manual.
