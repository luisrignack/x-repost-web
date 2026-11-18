# Arquitectura

## 1. Vista general

xrepost tiene tres capas y dos interfaces:

```
┌─────────────────────────────────────────────────────────────┐
│ Navegador (usuario)                                         │
│  web/static/index.html + app.js + styles.css                │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP loopback + sesión/CSRF
┌───────────────────────────▼─────────────────────────────────┐
│ Panel: web/app.py (http.server)                             │
│  · autenticación, sesiones, CSRF                            │
│  · API JSON y recursos estáticos                            │
│  · trabajos persistentes y cola de una ejecución            │
│  · perfiles, grupos, bandeja, programación, estadísticas    │
└───────────────────────────┬─────────────────────────────────┘
                            │ subproceso sin shell
┌───────────────────────────▼─────────────────────────────────┐
│ Motor: xrepost.sh → xrepost.py (browser-use sobre Chrome)   │
│  · búsqueda, filtros, repost/cita, verificación, undo       │
│  · historial JSONL, exportaciones, diagnóstico              │
└───────────────────────────┬─────────────────────────────────┘
                            │ CDP loopback
┌───────────────────────────▼─────────────────────────────────┐
│ Chrome con el perfil de xrepost y la sesión de X del usuario│
└─────────────────────────────────────────────────────────────┘
```

El CLI es la interfaz original y el panel no la sustituye: el panel invoca
`xrepost.sh` como subproceso y comparte los mismos archivos de estado.

## 2. Componentes

### 2.1 Entrada

| Archivo | Responsabilidad |
| --- | --- |
| `xrepost.sh` | Análisis de argumentos, modo interactivo, validación de entorno, invocación del motor, `--stats`, `--diagnose`, `--backup`, `--restore`, `--strict-cdp`. |
| `iniciar.sh` | Arranque idempotente: Chrome con CDP, panel web, token y enlace de arranque. |
| `xrepost-chrome.sh` | Lanzador de Chrome con el perfil aislado y el puerto de depuración. |
| `web/app.py` | Servidor HTTP y API. |

### 2.2 Dominio y estado

| Módulo | Responsabilidad |
| --- | --- |
| `xrepost_history.py` | Esquema de eventos, lectura tolerante, estado repost/undo, diagnóstico, backup, restore, rotación. |
| `xrepost_jobs.py` | Registro persistente de trabajos, estados canónicos, recuperación tras reinicio, poda. |
| `xrepost_inbox.py` | Bandeja de revisión persistente, decisiones y reconciliación con el motor. |
| `xrepost_state.py` | Máquina de estados canónica por publicación y validación de transiciones. |
| `xrepost_filters.py` | Normalización y validación de filtros, perfiles guardables, import/export. |
| `xrepost_groups.py` | Grupos de cuentas, alias, favoritos y estadísticas por cuenta. |
| `xrepost_schedule.py` | Programaciones (solo previsualización), próxima ejecución, vencimientos. |
| `xrepost_stats.py` | Métricas reales desde historial, trabajos, bandeja y programación. |
| `xrepost_exports.py` | CSV, Markdown, JSON, HTML, PDF y bundles de backup. |
| `xrepost_store.py` | Almacén JSON concurrente y tolerante a corrupción. |

### 2.3 Infraestructura

| Módulo | Responsabilidad |
| --- | --- |
| `xrepost_fs.py` | Permisos, escritura atómica, bloqueos, rutas seguras, symlinks. |
| `xrepost_security.py` | Token, sesiones, CSRF, fuerza bruta, Host/Origin, cookies. |
| `xrepost_cdp.py` | Validación y sonda del endpoint CDP, procesos de Chrome, perfil. |
| `xrepost_selectors.py` | Selectores y sondas JS de X centralizados. |
| `xrepost_labels.py` | Etiquetas de resultados compartidas por motor y CLI. |
| `xrepost_network.py` | Preferencias de red/proxy y flags de Chrome. |
| `xrepost_accounts.py`, `xrepost_hashtags.py` | Persistencia y sugerencias de cuentas y hashtags. |

### 2.4 Interfaz

| Archivo | Responsabilidad |
| --- | --- |
| `web/static/index.html` | Estructura semántica: cabecera, 8 pestañas, diálogos, regiones ARIA. |
| `web/static/app.js` | Estado de la vista, llamadas a la API, CSRF, renderizado seguro, temas. |
| `web/static/styles.css` | Paleta, temas claro/oscuro, responsive, foco visible, reduced motion. |

## 3. Flujo de una previsualización

1. El usuario rellena usuarios, fechas y filtros.
2. `POST /api/preview` valida los parámetros y los filtros, registra cuentas y
   hashtags, y crea un trabajo `preview`.
3. El panel lanza `xrepost.sh` con `X_MODE=preview`, `X_APPLY=0` y un entorno
   mínimo.
4. El motor busca cada cuenta, filtra y escribe una línea por publicación en
   la salida; el panel la convierte en filas de la tabla.
5. Al terminar, el trabajo pasa a `COMPLETED` (o `FAILED`/`TIMED_OUT`) y sus
   publicaciones se incorporan a la bandeja como `pending`.
6. La previsualización queda disponible para ejecutar mientras no cambien los
   parámetros: se compara `preview.params["key"]`.

## 4. Flujo de una ejecución

1. El usuario revisa y confirma en el diálogo (checkbox explícito).
2. `POST /api/apply` exige `preview_id`, comprueba que la previsualización
   terminó y que la clave de parámetros coincide.
3. El panel crea un trabajo `apply` y lanza el motor con `X_APPLY=1`.
4. El motor verifica cada repost/cita contra la interfaz y escribe eventos en
   el historial.
5. Al terminar, `_sync_inbox()` reconcilia la bandeja:
   - confirmado → `verified`
   - incierto/`skipped_uncertain` → `unconfirmed`
   - resto de fallos → `failed`
6. Las estadísticas se recalculan desde el historial; no hay contadores
   paralelos.

## 5. Estados

### 5.1 Trabajos

```
CREATED → QUEUED → RUNNING → COMPLETED
                            → FAILED
                            → CANCELLED
                            → TIMED_OUT
(reinicio) RUNNING/QUEUED → INTERRUPTED
```

`status` conserva el contrato anterior (`running`, `done`, `error`,
`cancelled`, `interrupted`) para no romper clientes.

### 5.2 Bandeja

```
pending → approved → queued → executed → verified
                                      → unconfirmed
                                      → failed
pending → rejected
```

Una decisión humana no puede mover un elemento ya ejecutado o incierto; se
conserva la decisión y el motivo para auditoría.

### 5.3 Resultados del motor

- Éxito confirmado: `reposted`, `quoted`.
- Sin cambios: `already`, `not_reposted`.
- Inciertos: `unconfirmed`, `quote_unverified`.
- Bloqueos: `session_expired`, `captcha`, `rate_limited`, `suspended`.
- Fallos: `no_button`, `no_menu`, `quote_failed`, etc.
- Filtros: `filtered_lang`, `filtered_media`, `filtered_length`,
  `filtered_regex`.
- Historial: `skipped_history`, `skipped_uncertain`.

## 6. Persistencia

Por defecto, todo el estado vive en `~/.local/state/xrepost/`:

```
history.jsonl                 historial de eventos
history-archivo-*.jsonl       rotaciones
history-backups/              backups con checksum
profiles.json                 perfiles de filtros
groups.json                   grupos de cuentas
account-meta.json             alias y favoritos
inbox.json                    bandeja
schedules.json                programación
chrome-profile/               perfil de Chrome
```

`web/.runs/<job-id>/` guarda la salida del motor y las exportaciones.

## 7. Concurrencia

- El servidor es `ThreadingHTTPServer`: cada petición tiene su hilo.
- Solo se ejecuta un trabajo a la vez (`App.running()`), porque Chrome es una
  única sesión. Las peticiones concurrentes reciben `409` cuando intentan
  lanzar otro.
- `JsonStore` usa un bloqueo de archivo (`fcntl`) para lectura-modificación-
  escritura entre procesos.
- Las sesiones y el estado de trabajos en memoria usan `threading.RLock`.

## 8. Dependencias

Obligatorias:

- Python 3.12+ (probado en 3.14.4).
- Chrome/Chromium con CDP.
- `browser-use` y sus dependencias para el motor.
- Bash 4+.

Opcionales:

- `pytest` para pruebas.
- `ruff`, `shellcheck`, `coverage` en CI.
- `node` solo para validar la sintaxis del JavaScript.

No hay frameworks web, bases de datos, colas ni contenedores.

## 9. Decisiones de diseño

1. **Biblioteca estándar para el panel**: menos dependencias, menos superficie
   de ataque y arranque inmediato.
2. **El panel no reimplementa el motor**: comparte el mismo CLI, el mismo
   historial y las mismas etiquetas.
3. **Estado en archivos JSON/JSONL**: legible, respaldable y sin servidor.
4. **Una ejecución a la vez**: refleja la realidad de una sola sesión de
   Chrome y evita condiciones de carrera difíciles de auditar.
5. **La UI no inventa estados**: muestra lo que el motor y el historial
   registran; un resultado desconocido se muestra como desconocido.
6. **Programación sin `apply`**: la automatización prepara trabajo, pero el
   repost siempre requiere confirmación humana.
