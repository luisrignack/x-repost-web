# Changelog técnico

Registro de cambios de la modernización integral. Cada entrada indica archivos,
motivo, impacto y verificación.

## Fase 0 — Línea base

**Archivos**: ninguno.

**Motivo**: fijar el estado de partida.

**Resultado**:

- 96 pruebas y 18 subpruebas.
- Python 3.14.4.
- Sin `docs/`, sin sesiones/CSRF, sin trabajos persistentes.

**Verificación**: `python3 -m pytest -q`.

## Fase 1 — Seguridad

### Archivos nuevos

- `xrepost_security.py`: token, sesiones, CSRF, fuerza bruta, cookies,
  `Host`/`Origin`.
- `xrepost_fs.py`: permisos, escritura atómica, bloqueos, rutas seguras.
- `xrepost_cdp.py`: validación del endpoint CDP.

### Archivos modificados

- `web/app.py`: autenticación por sesión, CSRF en escrituras, cabeceras de
  seguridad, CSP, `Host`/`Origin`, `--token-file`, `--bootstrap-file`,
  subprocesos sin shell y entorno con lista blanca.
- `iniciar.sh`: token en archivo 0600, enlace de arranque 0600, sin token en el
  log, `umask 077`.
- `xrepost.sh`: `umask 077`, `--strict-cdp`, validación del endpoint.
- `.github/workflows/ci.yml`: rama `modernizacion-integral`, `ruff`,
  `shellcheck`, cobertura.

### Motivo

El token viajaba en la URL, no había CSRF y los subprocesos heredaban el
entorno. Eran los riesgos críticos de la auditoría.

### Impacto

- Los clientes con `X-Token` siguen funcionando.
- El navegador usa cookie `HttpOnly` + CSRF.
- Los enlaces antiguos `/?token=…` siguen siendo válidos una vez.
- Un `POST` sin CSRF ahora devuelve `403`.

### Verificación

`SecurityTest` (token, sesiones, CSRF, bloqueo, cookies, Host/Origin),
`CdpTest` y las pruebas de `web/test_app.py` de sesión y CSRF.

## Fase 2 — Integridad del historial

### Archivos modificados

- `xrepost_history.py`: esquema, validación, lectura tolerante, rotación,
  diagnóstico, backup/restore con checksum.
- `xrepost.py`: escritura atómica, `history_state` compartido, deduplicación,
  no reintento de inciertos.
- `xrepost_labels.py`: etiquetas de bloqueo e inciertos.
- `xrepost.sh`: `--stats`, `--diagnose`, `--backup`, `--restore`.

### Motivo

El historial no era atómico y no había forma de diagnosticarlo o restaurarlo.

### Impacto

- Un corte durante la escritura no deja el archivo a medias.
- `--diagnose` informa de líneas corruptas sin borrarlas.
- `--restore` conserva el historial anterior.

### Verificación

`HistoryStateTest`, `HistoryTest` y las pruebas de diagnóstico/backup del
panel.

## Fase 3 — Motor verificable

### Archivos nuevos

- `xrepost_selectors.py`: selectores y sondas centralizadas.

### Archivos modificados

- `xrepost.py`:
  - `_validate_run()` valida usuarios, fechas, límites y CDP antes de actuar.
  - `PAGE_PROBLEM_JS` y `page_guard()` detectan bloqueos.
  - `FATAL_RESULTS` detiene la tanda.
  - `repost()` y `quote_repost()` verifican el estado real.
  - `undo_one()` no marca como deshecho si no puede confirmar.
  - `_filter_history()` omite ya hechos e inciertos.
  - Exportación CSV neutraliza fórmulas.
  - Filtros ampliados (`post_ok`).

### Motivo

El motor asumía el éxito tras pulsar el botón y podía reintentar acciones
desconocidas, con riesgo de duplicar publicaciones.

### Impacto

- `reposted`/`quoted` solo se registran con verificación.
- Un resultado desconocido queda como `unconfirmed`.
- Captcha, sesión caducada, límite o suspensión detienen la tanda.

### Verificación

`web/test_engine_selected.py` y las pruebas de estado del historial.

## Fase 4 — Trabajos persistentes

### Archivos nuevos

- `xrepost_jobs.py`: estados, registro, recuperación, poda, saneado.
- `xrepost_store.py`: almacén JSON concurrente.

### Archivos modificados

- `web/app.py`: trabajos persistentes, `INTERRUPTED` al arrancar, snapshots,
  exportaciones por trabajo, cancelación por grupo de procesos, timeout.

### Motivo

Reiniciar el panel perdía el estado y podía dejar procesos huérfanos.

### Impacto

- Los trabajos sobreviven al reinicio y se muestran como interrumpidos.
- Los parámetros persistidos no incluyen secretos.
- La cola impide dos ejecuciones simultáneas.

### Verificación

`JobsTest` y las pruebas de `/api/jobs` del panel.

## Fase 5 — Funcionalidades nuevas

### Archivos nuevos

- `xrepost_filters.py`: perfiles y validación de filtros.
- `xrepost_groups.py`: grupos, alias, favoritos, actividad.
- `xrepost_inbox.py`: bandeja con estados y decisiones.
- `xrepost_schedule.py`: programación solo de previsualización.
- `xrepost_stats.py`: estadísticas reales.
- `xrepost_exports.py`: CSV, Markdown, JSON, HTML, PDF y bundles.

### Archivos modificados

- `web/app.py`: endpoints y lógica de las cinco áreas.
- `xrepost_inbox.py`: nuevo estado `unconfirmed`.
- `web/static/*`: interfaz de las nuevas pestañas.

### Motivo

Faltaban revisión previa persistente, perfiles, grupos, programación,
estadísticas y exportaciones completas.

### Impacto

- La previsualización alimenta la bandeja.
- `apply` reconcilia estados: verificado, incierto o fallido.
- La programación nunca publica.
- Las estadísticas separan desconocidos y fallos.

### Verificación

`FiltersTest`, `GroupsTest`, `InboxTest`, `ScheduleTest`, `StatsTest`,
`ExportsTest` y las pruebas del panel de cada área.

## Fase 6 — UX/UI

### Archivos modificados

- `web/static/index.html`: 8 pestañas, regiones ARIA, diálogos, skip-link,
  formularios completos.
- `web/static/app.js`: estado de vista, CSRF, renderizado seguro, temas,
  reconciliación de bandeja, programación, estadísticas.
- `web/static/styles.css`: paleta, temas claro/oscuro, responsive, foco,
  reduced motion.

### Motivo

La interfaz era una sola vista sin navegación, temas ni accesibilidad.

### Impacto

- Navegación por pestañas con teclado.
- Temas persistidos.
- Tablas y diálogos accesibles.
- Sin desbordamiento horizontal en móvil (verificado a 390 px).

### Verificación

Pruebas de estructura de la UI y comprobación manual con el navegador:
pestañas, tema, diálogo de confirmación, bandeja, estadísticas, grupos,
perfiles, programación y responsive.

## Fase 7 — Pruebas y CI

### Archivos nuevos

- `tests/test_core_modules.py` (24 pruebas).

### Archivos modificados

- `web/test_app.py`: +16 pruebas (sesión, CSRF, UI, cuentas, grupos, perfiles,
  bandeja, programación, estadísticas, backups, exportaciones).
- `ci.sh`: aviso de módulos no trackeados, `bash -n` de todos los scripts,
  `node --check`, copia portable.
- `.github/workflows/ci.yml`: cobertura, `ruff`, `shellcheck`, rama nueva.
- `sync_portable.sh`: 12 módulos nuevos, `ci.sh` y
  `tests/test_core_modules.py`.

### Motivo

La lógica nueva no tenía pruebas y la CI no cubría la copia portable ni los
módulos.

### Resultado

- **192 pruebas y 32 subpruebas**, todas aprobadas.
- `ci.sh` en verde.
- Copia portable sincronizada (41 archivos).

## Fase 8 — Documentación

### Archivos nuevos

- `docs/ESTADO_TECNICO_INICIAL.md`
- `docs/SEGURIDAD.md`
- `docs/MODELO_DE_AMENAZAS.md`
- `docs/ARQUITECTURA.md`
- `docs/INSTALACION.md`
- `docs/CONFIGURACION.md`
- `docs/USUARIO.md`
- `docs/CLI.md`
- `docs/API.md`
- `docs/MOTOR_X.md`
- `docs/PERSISTENCIA.md`
- `docs/BACKUP_RESTORE.md`
- `docs/DESARROLLO.md`
- `docs/TESTING.md`
- `docs/CHANGELOG_TECNICO.md`
- `docs/INFORME_FINAL.md`
- `docs/AUTENTICACION.md`
- `docs/CHROME_CDP.md`
- `docs/GESTION_DE_JOBS.md`
- `docs/RECUPERACION.md`
- `docs/CONFIGURACION_RED.md`
- `docs/DIAGNOSTICO.md`

### Motivo

La documentación existente era un único `README.md` sin separación por
audiencia.

### Impacto

- Cada audiencia tiene su documento.
- Los límites y riesgos están explícitos.
- No se declaran métricas no medidas.

## Cambios de comportamiento visibles

| Antes | Ahora |
| --- | --- |
| `POST` con cookie funcionaba sin CSRF | Devuelve `403` sin `X-CSRF-Token`. |
| El token quedaba en la URL | Se cambia por cookie y redirección. |
| Un repost se marcaba como hecho al pulsar | Se verifica el estado real. |
| Un resultado dudoso se reintentaba | Queda `unconfirmed` y no se reintenta sin `--force`. |
| Reiniciar el panel perdía trabajos | Se recuperan como `INTERRUPTED`. |
| Programar ejecutaba directamente | Solo previsualiza. |
| Estadísticas sin denominador | Tasa con denominador visible. |
| Exportación solo CSV/MD | CSV, MD, JSON, HTML, PDF y bundles. |

## Compatibilidad

Se conservan:

- Opciones del CLI y variables `X_*`.
- Endpoints antiguos y campos `status`, `lines`, `posts`, `progress`.
- Formato del historial (`fecha,autor,usuario,texto,url,estado` en CSV).
- `X-Token` para clientes de línea de comandos.
- Estructura de `accounts.json` y `hashtags.json`.

## Verificación de la rama (2026-11-18)

La primera ejecución de CI en GitHub reveló dos fallos reales que el informe
anterior no había detectado porque solo se había ejecutado el CI local:

1. `ruff` fallaba con 43 `F821` en `xrepost.py`: las funciones que inyecta
   `browser-use` (`js`, `goto_url`, `wait_for_load`…) no estaban declaradas.
   Se añadió un bloque `_injected(...)` documentado que las resuelve del espacio
   de nombres y falla con un mensaje claro si el harness cambia.
2. `xrepost_exports.py` usaba una f-string con escapes y comillas anidadas que
   solo es válida en Python 3.12; se reescribió para 3.10+.

Además se corrigió un token de ejemplo real en `ABRIR_LA_APLICACION.md`, se
excluyó la copia portable del análisis de Ruff y se añadió `ruff.toml`.

La revisión posterior añadió:

- **Token de arranque de un solo uso**, independiente del maestro. El segundo
  canje devuelve `401` y la cookie heredada `xrepost_token` deja de emitirse.
- **Transiciones de estado de trabajos** validadas con `TRANSITIONS` y
  `JobStateError`; un estado terminal ya no vuelve a `RUNNING`.
- **Duración y bandera de cancelación** persistidas en el registro del trabajo.
- **Validación de proxy y bypass** en `xrepost_network.py`, también al
  recalcular los flags de Chrome.
- **Cobertura de `xrepost_cdp.py`** elevada al 89 % con pruebas de
  `/proc/net/tcp`, procesos y perfiles simulados.
- **Prueba de arranque aislada** de `browser-use` mediante un ejecutable de
  doble en el `PATH`.
- **Anotación de cobertura en CI** cuando no se alcanza el umbral, para poder
  diagnosticar sin acceso a los logs.

## Cobertura y pruebas

- 192 pruebas + 32 subpruebas.
- 91 % en los módulos de negocio (umbral de CI: 90 %); 86 % total.
- 38 pruebas nuevas para `fs`, `filters`, `cdp`, `schedule`, `security`,
  `groups`, `history` y `state`.
- `bandit -ll`: 0 hallazgos medium/high (12 low de `try/except pass`
  justificados).
- `gitleaks` sobre el árbol actual: sin fugas.

## Fase final — carrera de `apply`, encuadre HTTP y citas

**Archivos**: `web/app.py`, `xrepost_jobs.py`, `xrepost.py`,
`xrepost_labels.py`, `xrepost_history.py`, `xrepost_network.py`,
`xrepost_cdp.py`, `web/test_app.py`, `web/test_engine_selected.py`,
`tests/test_core_modules.py`, documentación.

**Motivo**:

- Corregir la condición de carrera de `_api_apply()`: la selección se escribía
  en el directorio de la previsualización antes de reservar el turno.
- Cerrar ambigüedades de encuadre HTTP y limitar el tiempo de una conexión.
- Hacer observable el avance de una cita y no reintentar un envío incierto.
- Revertir automáticamente un cambio de red que deje a Chrome sin CDP.

**Resultado**:

- `App.reserve_job()` / `launch_job()` / `abort_job()`: reserva bajo el mismo
  bloqueo que comprueba `running()`, directorio y `selected.json` exclusivos,
  liberación y borrado del registro si la preparación falla.
- `JobStore.delete()` para reservas abortadas.
- `_content_length()`: rechaza `Content-Length` negativo, no numérico,
  duplicado y `Transfer-Encoding`; exige el cuerpo completo; `timeout = 30` en
  el handler.
- Citas: eventos `quote_pending` y `quote_submitted`; `uncertain_ids()` mira
  solo el último evento, de modo que un `quote_failed` sí se puede reintentar.
- `wait_until`, `wait_post_ready`, `wait_quote_closed` y `wait_quote_enabled`
  sustituyen pausas fijas por sondeos acotados.
- La búsqueda avisa al alcanzar 40 resultados por cuenta y resume vistas,
  disponibles, retuits omitidos y descartes.
- Red: `save_config()` guarda `.bak`, `wait_available()` espera CDP y el panel
  restaura la configuración anterior si el reinicio no vuelve.
- Pruebas: dos y diez `apply` simultáneos (una sola escritura), reserva
  liberada ante error, encuadre con socket crudo, cita fallida reintentable,
  último evento de cita (un envío sin confirmar bloquea; un fallo posterior
  permite reintentar), reversión de red, `JobStore.delete`, 100 GET
  concurrentes, 20 POST inválidos, 10 000 eventos y 200 cuentas.

**Verificación**:

```text
192 passed, 32 subtests passed
ruff (E9,F63,F7,F82): sin hallazgos
bandit -ll: 0 medium/high
ci.sh: CI OK
```

## Deuda pendiente

- Retirar la cookie heredada `xrepost_token` (hoy solo permite lectura).
- Purificar el token de ejemplo del historial de git (`17258ce4`); requiere
  reescribir la rama y `push --force`.
- Resolver los errores de `mypy` de los módulos históricos (hoy informativo).
- Añadir pruebas end-to-end contra una cuenta de prueba cuando esté
  autorizado.
- Valorar TLS si el panel dejara de ser local.
- Interfaz: paginación, copiar enlace, importación de cuentas y navegación
  lateral (ver `INFORME_FINAL.md`, secciones 16 y 18).
