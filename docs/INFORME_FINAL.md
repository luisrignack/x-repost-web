# Informe final de la modernización

Rama: `modernizacion-integral` · Versión: 2.0.0 · Fecha: 2026-11-18
Documento de partida: [`ESTADO_TECNICO_INICIAL.md`](ESTADO_TECNICO_INICIAL.md)

## 1. Resumen ejecutivo

xrepost conserva su arquitectura local (Python estándar, Bash, HTML/CSS/JS,
Chrome/CDP, JSON/JSONL) y su contrato de CLI, pero pasa de un panel con un
token permanente en la URL a una aplicación con sesión, CSRF, validación de
CDP, escritura atómica, máquina de estados por publicación y por trabajo,
verificación real de cada acción y recuperación conservadora tras un reinicio.

La suite creció de 96 a **180 pruebas + 32 subpruebas**. La cobertura de los
módulos de negocio es **91 %** (total del proyecto: 86 %). El CI ejecuta Ruff,
ShellCheck, Bandit, pip-audit, Gitleaks, cobertura, SBOM y empaquetado.

El trabajo **no se declara terminado al 100 %**: faltan pruebas end-to-end
contra X, la accesibilidad no se ha auditado con lector de pantalla, `mypy`
sigue informativo y hay elementos de interfaz pendientes. Todo ello se detalla
en las secciones 16 y 17.

## 2. Estado inicial

El inventario completo, la metodología y los 28 hallazgos con prioridad,
evidencia y prueba necesaria están en
[`ESTADO_TECNICO_INICIAL.md`](ESTADO_TECNICO_INICIAL.md). En resumen:

- Autenticación por token permanente embebido en la URL y en el log.
- Sin CSRF ni validación estricta de `Origin`/`Host`.
- CDP aceptado sin comprobar loopback, proceso ni perfil.
- Historial sin escritura atómica, diagnóstico ni backup verificable.
- Éxito asumido tras pulsar el botón de repost/cita/undo.
- Trabajos solo en memoria; un reinicio los perdía.
- Interfaz de una sola vista, sin estados reales por publicación.
- 96 pruebas, sin cobertura ni análisis de seguridad en CI.

## 3. Cambios implementados

### Seguridad

- Token de arranque de un solo uso canjeado por cookie de sesión `HttpOnly`,
  `SameSite=Strict`, con caducidad absoluta y por inactividad, rotación y
  revocación.
- Token maestro de 32 bytes generado con `secrets`, comparado con
  `hmac.compare_digest`, guardado en archivo `0600` y nunca escrito en logs.
- CSRF por sesión (`X-CSRF-Token`), validación exacta de `Host`/`Origin`,
  `Sec-Fetch-Site`, `Content-Type` y límite de cuerpo.
- Bloqueo progresivo por IP tras fallos de autenticación.
- CSP estricta, `X-Content-Type-Options`, `Referrer-Policy`, `no-store`,
  `X-Frame-Options: DENY`, COOP/CORP.
- Validación del endpoint CDP: `http`, loopback literal, puerto explícito, sin
  credenciales ni ruta, `/json/version` de Chrome, proceso con
  `--remote-debugging-port` y `--user-data-dir` esperados, y perfil distinto
  del personal.
- Subprocesos sin shell, con entorno de lista blanca, grupo propio, `SIGTERM`
  y `SIGKILL` como último recurso.

### Fiabilidad

- `xrepost_fs.py`: escritura atómica, `fsync`, `flock`, permisos `0700/0600`,
  rechazo de symlinks y validación de propietario.
- `xrepost_store.py`: JSON concurrente con validación y recuperación ante
  corrupción.
- `xrepost_jobs.py`: registro persistente, estados `CREATED`…`INTERRUPTED`,
  **transiciones validadas**, recuperación conservadora y poda.
- `xrepost_state.py`: máquina de estados por publicación (`DISCOVERED`…
  `UNDONE`) integrada en la bandeja.
- Resultados inciertos (`UNCERTAIN_RESULTS`) no se reintentan sin `--force`.
- Backup de historial con SHA-256, verificación y restauración forzada.

### Funcionalidad

- Trabajos persistentes, cancelación, timeout y recuperación como
  `INTERRUPTED`.
- Bandeja de revisión por ID con decisiones y reconciliación con el motor;
  un undo confirmado la actualiza a `UNDONE`.
- Perfiles de filtros, grupos de cuentas con alias/favoritos, importación y
  exportación CSV.
- Programación de **solo previsualización**; nunca repost automático.
- Estadísticas con denominador explícito.
- Exportaciones CSV (con neutralización de fórmulas), Markdown, JSON, HTML y
  PDF.
- Comandos `--stats`, `--diagnose`, `--backup`, `--restore`, `--strict-cdp` y
  `--version`.

### Interfaz

- Ocho secciones: Buscar, Bandeja, Cuentas, Filtros, Programación, Historial,
  Estadísticas y Sistema.
- Paleta solicitada, temas claro/oscuro persistidos, tablas ordenables,
  «Ver en X», diálogos de confirmación destructiva, progreso y estados vacíos.
- Skip-link, roles `tablist/tab/tabpanel`, `aria-live`, foco visible,
  `prefers-reduced-motion` y responsive a 1280×900 y 390×844.

## 4. Problemas encontrados durante la verificación

| ID | Problema | Causa | Corrección |
| --- | --- | --- | --- |
| V-01 | El primer CI remoto falló en Ruff con 43 `F821`. | Las funciones que inyecta `browser-use` (`js`, `goto_url`, `wait_for_load`…) no existen como nombres estáticos. | Bloque `_injected()` documentado que las resuelve del espacio de nombres y falla con un mensaje claro si el harness cambia. |
| V-02 | `xrepost_exports.py` no parseaba en Python 3.10/3.11. | F-string con escapes y comillas anidadas válida solo desde 3.12. | Reescritura compatible con 3.10+. |
| V-03 | Gitleaks encontró un token de ejemplo real en la documentación. | Se copió una URL de una ejecución local. | Redactado como `<token-aleatorio>`; el árbol actual queda limpio. |
| V-04 | El segundo CI remoto falló en el paso de cobertura. | La prueba de `iniciar.sh --check` exigía `browser-use` en el PATH, que no existe en el runner; pytest devolvía 1 antes del informe. | La prueba inyecta un `browser-use` de prueba en el PATH del subproceso. Reproducido con `HOME` vacío y Python 3.12. |
| V-05 | Las transiciones de estado de los trabajos no se validaban. | `JobStore.update` solo comprobaba que el estado existiera. | Tabla `TRANSITIONS`, `JobStateError`, `can_transition`/`require_transition` y pruebas de estados terminales. |
| V-06 | Un undo confirmado no actualizaba la bandeja. | `_sync_inbox()` solo se invocaba para `preview`/`apply`, `xrepost_state` no estaba importado en `web/app.py` y `job.started` incluía `+00:00` frente a un `ts` normalizado a minutos. | Se sincroniza también en `undo`, se importa `xrepost_state` y se compara con el mismo formato; la prueba `test_undo_confirmado_actualiza_la_bandeja` la cubre. |
| V-07 | `Sec-Fetch-Site` y el rechazo de escrituras con cookie sin `Origin` estaban documentados pero no implementados. | `_origin_ok()` devolvía `True` sin `Origin` y nadie miraba `Sec-Fetch-Site`. | `_require_local_provenance()` rechaza `cross-site` y exige `Origin` o `Sec-Fetch-Site` en escrituras con cookie; los clientes `X-Token` siguen exentos. |

## 5. Vulnerabilidades corregidas

| ID inicial | Vulnerabilidad | Corrección | Evidencia |
| --- | --- | --- | --- |
| S-01 | Token permanente en URL y log. | Sesión + cookie `HttpOnly`; token de arranque de un solo uso; secreto en `0600`. | `xrepost_security.py`, `web/test_app.py` |
| S-02 | CSRF ausente. | Token por sesión, `Origin`/`Host`, `Sec-Fetch-Site` y tipo de contenido. | `xrepost_security.py`, pruebas de CSRF |
| S-04 | Fuerza bruta sin límite. | Bloqueo progresivo por IP. | `xrepost_security.AuthManager` |
| S-05 | Cabeceras ausentes. | CSP y cabeceras en todas las respuestas. | `web/app.py`, pruebas de cabeceras |
| S-06 | CDP sin identidad verificada. | Loopback, puerto, proceso y perfil dedicados. | `xrepost_cdp.py`, 4 pruebas |
| S-07 | `shell=True` y entorno completo. | Listas de argumentos y entorno mínimo. | `web/app.py` |
| S-08/S-09 | Permisos laxos y symlinks. | `umask`, `0700/0600`, `O_NOFOLLOW`, `safe_join`. | `xrepost_fs.py` |
| R-02 | Resultado incierto reintentado. | `UNCERTAIN_RESULTS` y estado `unconfirmed`. | `xrepost_labels.py`, bandeja |
| R-03 | Éxito asumido tras el clic. | Verificación del DOM en repost, cita y undo. | `xrepost.py`, pruebas del motor |

No quedan vulnerabilidades críticas conocidas **en el modelo de despliegue
soportado** (loopback, un usuario, sin TLS). Los riesgos fuera de ese modelo
se listan en la sección 17.

## 6. Cambios arquitectónicos

La arquitectura sigue siendo un núcleo Python compartido por CLI y panel, sin
frameworks, servicios externos ni dependencias de ejecución.

```text
xrepost.sh ──► xrepost.py (motor, ejecutado por browser-use)
     │              │
     │              ├── xrepost_history.py ──► JSONL
     │              ├── xrepost_filters.py
     │              ├── xrepost_labels.py
     │              └── xrepost_selectors.py
     │
     └── web/app.py (HTTP 127.0.0.1)
             ├── xrepost_security.py   (sesiones/CSRF)
             ├── xrepost_cdp.py        (validación CDP)
             ├── xrepost_jobs.py       (trabajos persistentes)
             ├── xrepost_inbox.py      (bandeja)
             ├── xrepost_state.py      (máquina de estados)
             ├── xrepost_groups.py     (grupos/alias)
             ├── xrepost_filters.py    (perfiles)
             ├── xrepost_schedule.py   (programación)
             ├── xrepost_stats.py      (estadísticas)
             ├── xrepost_exports.py    (CSV/MD/JSON/HTML/PDF)
             ├── xrepost_fs.py         (E/S segura)
             └── xrepost_store.py      (JSON concurrente)
```

`web/app.py` sigue concentrando el servidor HTTP y los handlers. La lógica de
dominio se extrajo a los módulos `xrepost_*`; **no se creó** la estructura
`web/services/` propuesta porque habría añadido capas sin reducir complejidad
real. Es una decisión consciente, no un olvido (ver sección 16).

## 7. Cambios en persistencia

- Escritura atómica con temporal en el mismo directorio, `fsync` y
  `os.replace`; bloqueo con `flock`.
- Directorios `0700` y archivos `0600`; rechazo de symlinks y de archivos de
  otro propietario.
- JSON validado al leer; un archivo corrupto no se sobrescribe en silencio.
- Historial JSONL con rotación por tamaño, diagnóstico, backup SHA-256 y
  restauración verificada.
- Trabajos en `jobs.json` con estados canónicos, parámetros saneados (sin
  secretos ni rutas internas), duración y bandera de cancelación.
- Bandeja, perfiles, grupos, metadatos, programación y preferencias de red en
  archivos separados para no romper `accounts.json` ni `hashtags.json`.

## 8. Cambios en el motor

- Selectores centralizados en `xrepost_selectors.py` con alternativas y
  validación.
- Esperas condicionadas con timeout; no hay bucles infinitos.
- Detección de sesión expirada, captcha, restricciones y límites de X; la
  ejecución se detiene y pide intervención humana.
- Verificación del DOM tras repost, cita y undo. Un clic sin evidencia queda
  como incierto, no como éxito.
- Deduplicación por identificador/URL e historial; una publicación ya
  confirmada no se repite.
- Modo diagnóstico de solo lectura (`--diagnose`, `--strict-cdp`) que no
  publica nada.

## 9. Pruebas incorporadas

- 38 pruebas nuevas respecto a la línea base en `tests/test_core_modules.py`
  (hoy 62 en ese archivo), más las ampliaciones de `web/test_app.py`.
- Cobertura directa de: sistema de archivos seguro, almacén JSON, filtros,
  CDP, sesiones, fuerza bruta, CSRF, trabajos y transiciones, exportaciones,
  grupos, bandeja, programación, estadísticas, historial, backups y máquina de
  estados.
- Simulación del motor y de `browser-use` en `web/test_engine_selected.py`;
  ninguna prueba publica en X ni abre Chrome.
- Prueba de arranque con un `browser-use` de doble para que el CI no dependa
  de herramientas instaladas en el runner.

## 10. Resultados de las pruebas

| Comprobación | Resultado |
| --- | --- |
| `pytest` | **180 passed, 32 subtests passed** (~42 s) |
| Python 3.12 (CI) | Misma suite, mismos resultados |
| Python 3.10+ | Sintaxis compatible (se corrigió la f-string de `xrepost_exports.py`) |
| Ruff (`E9,F63,F7,F82`) | Sin hallazgos (re-verificado 2026-11-18) |
| ShellCheck (`-S error`) | Sin hallazgos |
| `node --check web/static/app.js` | Correcto |
| `py_compile`, `bash -n` | Correcto |
| `ci.sh` | `CI OK` |
| Copia portable | Sincronizada y verificada |

## 11. Cobertura real

Medida con `coverage 7.17.3 --branch` y Python 3.12/3.14:

| Módulo | Cobertura |
| --- | --- |
| `xrepost_schedule.py` | 99 % |
| `xrepost_security.py` | 96 % |
| `xrepost_groups.py` | 95 % |
| `xrepost_filters.py` | 94 % |
| `xrepost_history.py` | 95 % |
| `xrepost_state.py` | 94 % |
| `xrepost_store.py` | 90 % |
| `xrepost_exports.py` | 89 % |
| `xrepost_jobs.py` | 89 % |
| `xrepost_inbox.py` | 88 % |
| `xrepost_cdp.py` | 89 % |
| `xrepost_fs.py` | 83 % |
| `xrepost_stats.py` | 82 % |
| **Total de negocio** | **91 %** |
| **Total del proyecto** | **86 %** |

CI exige `--fail-under=90` sobre el conjunto de negocio. La cobertura total es
menor por `xrepost_accounts.py` (CLI interactivo) y `web/app.py`; sus caminos
críticos están cubiertos por `web/test_app.py`. La validación de seguridad
crítica (CSRF, sesión, CDP, symlinks, rutas) tiene pruebas directas, pero no se
declara el 100 % formal solicitado.

## 12. Resultados de herramientas de seguridad

Ejecutadas de nuevo el 2026-11-18 con las versiones fijadas del proyecto
(Ruff 0.17.5, ShellCheck 0.10.0, Bandit 1.9.4, pip-audit 2.10.1, Gitleaks
8.30.1, coverage 7.17.3, pytest 9.2.0):

| Herramienta | Resultado | Estado |
| --- | --- | --- |
| Bandit `-ll` | 0 medium / 0 high; 12 low (`try/except pass` de cierre de recursos) | Bloqueante en medium+ |
| pip-audit | Sin dependencias de ejecución; «No known vulnerabilities found» | Bloqueante |
| Gitleaks (árbol actual) | «no leaks found» | Bloqueante |
| Gitleaks (historial) | Detecta el token de ejemplo del commit `17258ce4`, ya inválido | Pendiente de purga |
| Ruff | `All checks passed!` en `E9,F63,F7,F82` | Bloqueante |
| ShellCheck | Sin errores (`-S error`) | Bloqueante |
| mypy | 33 errores en módulos nuevos (métodos `list` que eclipsan el tipo, etc.) | Informativo |
| SBOM | CycloneDX 1.6 válido, 7 componentes de desarrollo | Artefacto de CI |

## 13. Cambios en CI

`.github/workflows/ci.yml` ejecuta, en orden:

1. Checkout y Python 3.12 con caché de pip.
2. Instalación de `requirements-dev.txt` (versiones fijadas) y ShellCheck.
3. Ruff (`E9,F63,F7,F82`).
4. ShellCheck (`-S error`).
5. `node --check`.
6. Bandit (`-ll`).
7. pip-audit.
8. Gitleaks sobre el árbol de trabajo.
9. mypy informativo (`continue-on-error`).
10. Cobertura con umbral del 90 %; si falla, publica el informe como
    anotación para que sea diagnosticable sin acceso a logs.
11. SBOM CycloneDX.
12. `ci.sh` completo.
13. Paquete `tar.gz` con `SHA256SUMS` y artefactos.

Además, `.github/dependabot.yml` revisa semanalmente pip y GitHub Actions.

## 14. Archivos modificados

**Creados**

```text
xrepost_fs.py xrepost_store.py xrepost_filters.py xrepost_cdp.py
xrepost_security.py xrepost_jobs.py xrepost_exports.py xrepost_groups.py
xrepost_inbox.py xrepost_schedule.py xrepost_stats.py xrepost_selectors.py
xrepost_state.py
tests/test_core_modules.py
docs/ (22 documentos, incluidos ESTADO_TECNICO_INICIAL.md e INFORME_FINAL.md)
SECURITY.md CONTRIBUTING.md CHANGELOG.md LICENSE_PENDING.md
requirements.txt requirements-dev.txt ruff.toml .github/dependabot.yml
```

**Modificados**

```text
xrepost.py xrepost_history.py xrepost_labels.py xrepost.sh iniciar.sh ci.sh
sync_portable.sh .github/workflows/ci.yml .gitignore README.md
web/app.py web/static/index.html web/static/app.js web/static/styles.css
web/test_app.py web/test_engine_selected.py tests/test_start_script.py
ABRIR_LA_APLICACION.md
```

**Eliminados**: ninguno. Los archivos de datos del usuario no se tocaron.

## 15. Compatibilidad

| Elemento | Estado |
| --- | --- |
| CLI y variables `X_*` | Conservados; se añaden comandos, no se eliminan. |
| Endpoints y campos `status`/`lines`/`posts`/`progress` | Conservados. |
| Formato del historial y CSV | Conservado. |
| `accounts.json`, `hashtags.json`, `network.json` | Estructura conservada; metadatos nuevos en archivos aparte. |
| Proxy directo/PAC/servidor | Conservado y validado. |
| Arranque `./iniciar.sh` | Conservado; añade `--check`, `--status` y `--stop`. |
| Copia portable | Conservada y sincronizada. |
| Perfil personal de Chrome | No se toca; se usa un perfil dedicado. |

## 16. Limitaciones conocidas

- **Sin pruebas end-to-end contra X**: requieren una cuenta autorizada y no se
  ejecutan en CI. La verificación del DOM está probada con dobles, no contra X
  en vivo.
- **Accesibilidad**: hay base técnica (roles, foco, contraste, reduced-motion),
  pero no se ha auditado con lector de pantalla; no se declara WCAG 2.2 AA
  completo.
- **mypy**: 33 errores en los módulos nuevos, en su mayoría métodos llamados
  `list` que eclipsan el tipo incorporado. Es informativo y no bloquea.
- **Cobertura**: 91 % de negocio, no el 90 % global ni el 100 % de seguridad
  crítica que pide el objetivo; medido, no estimado.
- **Cookie heredada `xrepost_token`**: ya no se emite; se acepta solo para
  lectura si un cliente antiguo la conserva, nunca para escribir. Retirar su
  aceptación exige migrar clientes antiguos.
- **Token en el historial de git**: el commit `17258ce4` contiene un token de
  ejemplo ya inválido. Purificarlo requiere reescribir la rama y
  `push --force`, no ejecutado.
- **Interfaz**: no hay paginación de tablas, botón de copiar enlace ni botón de
  importación de cuentas (el endpoint y el parser existen). No hay navegación
  lateral ni secciones Dashboard/Exportaciones/Configuración separadas; las
  funciones están en las ocho pestañas.
- **Reconciliación de undo**: tras un undo confirmado, la bandeja pasa el
  elemento por `UNDO_PENDING` y lo deja en `UNDONE`. Como el historial guarda
  minutos (no segundos), se exige además que el último evento de la
  publicación sea ese undo; así un undo antiguo seguido de un repost nuevo no
  se confunde. Un undo fallido deja el elemento como estaba.
- **Modularización de `web/app.py`**: la lógica de dominio está extraída, pero
  el servidor y los handlers siguen en un archivo grande.
- **Licencia**: no hay `LICENSE`; el titular no ha elegido una. Se documenta en
  `LICENSE_PENDING.md` y no se inventa una licencia.

## 17. Riesgos residuales

1. **Chrome o perfil comprometidos**: ninguna capa de la aplicación puede
   garantizar integridad si un tercero controla el navegador.
2. **X cambia el DOM**: los selectores tienen alternativas y diagnóstico, pero
   un cambio profundo puede romper el motor hasta actualizar selectores.
3. **Resultado externo incierto**: X no ofrece transacciones; un corte entre el
   clic y la confirmación puede dejar un repost sin estado verificable. Se
   marca como incierto y no se reintenta solo.
4. **Exposición fuera de loopback**: queda fuera del modelo de amenazas y no
   se soporta.
5. **Token de ejemplo en el historial de git**: ya inválido, pero detectable
   por un escaneo con historial hasta que se purgue.

## 18. Recomendaciones futuras

1. Ejecutar una prueba end-to-end controlada contra una cuenta de prueba
   autorizada antes de usar la herramienta de forma intensiva.
2. Auditar la interfaz con NVDA/Orca y completar WCAG 2.2 AA.
3. Resolver los 33 errores de mypy y activar el paso como bloqueante.
4. Añadir paginación, copiar enlace e importación de cuentas en la UI.
5. Retirar la cookie heredada y purificar el token del historial de git con
   coordinación y `push --force` autorizado.
6. Extraer `web/app.py` por etapas (`server`, `security`, `services`) sin
   cambiar el contrato HTTP.
7. Elegir y añadir una licencia.
8. Elevar la cobertura de `xrepost_stats`, `xrepost_fs` y `xrepost_cdp` para
   acercarse al 90 % global.

## Anexo. Tabla de problemas y estado

| ID | Problema | Prioridad | Solución | Prueba | Estado |
| --- | --- | --- | --- | --- | --- |
| S-01 | Token permanente en URL y log | P0 | Sesión + cookie `HttpOnly`; token de arranque de un solo uso | `web/test_app.py` auth | RESUELTO |
| S-02 | CSRF ausente | P0 | Token por sesión + `Origin`/`Host`/`Sec-Fetch-Site` | Pruebas CSRF | RESUELTO |
| S-03 | Comparación no constante | P2 | `hmac.compare_digest` | Pruebas de token | RESUELTO |
| S-04 | Fuerza bruta | P1 | Bloqueo progresivo por IP | `SecurityHardeningTest` | RESUELTO |
| S-05 | Cabeceras ausentes | P2 | CSP y cabeceras de seguridad | Pruebas de cabeceras | RESUELTO |
| S-06 | CDP sin identidad | P1 | Loopback, puerto, proceso y perfil | `CdpSecurityTest` | RESUELTO |
| S-07 | `shell=True` | P1 | Listas de argumentos y entorno mínimo | Pruebas del panel | RESUELTO |
| S-08 | Permisos laxos | P2 | `0700/0600`, `umask`, atómico | `FilesystemHardeningTest` | RESUELTO |
| S-09 | Symlinks y traversal | P2 | `O_NOFOLLOW`, `safe_join` | `FilesystemHardeningTest` | RESUELTO |
| R-01 | Historial no atómico | P1 | Temporal + `fsync` + `replace` | `HistoryIntegrityTest` | RESUELTO |
| R-02 | Incierto reintentado | P1 | `UNCERTAIN_RESULTS`, sin reintento automático | Pruebas del motor | RESUELTO |
| R-03 | Éxito asumido | P0 | Verificación del DOM | `web/test_engine_selected.py` | RESUELTO |
| R-04 | Fallos de X no detenían | P1 | `FATAL_RESULTS` y parada segura | Pruebas del motor | RESUELTO |
| R-05 | Jobs solo en memoria | P1 | `xrepost_jobs.py` persistente | `JobsTest` | RESUELTO |
| R-06 | Procesos huérfanos | P1 | Grupo propio, `SIGTERM`/`SIGKILL` | Pruebas de cancelación | RESUELTO |
| R-07 | Sin backup verificable | P2 | `--backup`/`--restore` + SHA-256 | `HistoryIntegrityTest` | RESUELTO |
| R-08 | Filtros divergentes | P2 | `normalize_spec()` único | `FiltersTest` | RESUELTO |
| F-01 | Sin bandeja persistente | P1 | Bandeja por ID y reconciliación | Pruebas de bandeja | RESUELTO |
| F-02 | Sin perfiles/grupos | P2 | `xrepost_filters`, `xrepost_groups` | `FiltersTest`, grupos | RESUELTO |
| F-03 | Sin programación | P2 | Solo previsualización | `ScheduleHardeningTest` | RESUELTO |
| F-04 | Estadísticas sin denominador | P2 | `xrepost_stats` explícito | Pruebas de estadísticas | RESUELTO |
| F-05 | Exportaciones limitadas | P2 | CSV/MD/JSON/HTML/PDF | `ExportFormatsTest` | RESUELTO |
| F-06 | UI de una vista | P2 | 8 pestañas, temas, ARIA | `web/test_app.py` UI | RESUELTO |
| F-07 | Mensajes/éxito genéricos | P1 | Estados reales por publicación | Pruebas de snapshot | RESUELTO |
| M-01 | Estado duplicado | P2 | `xrepost_history.py` compartido | Pruebas de historial | RESUELTO |
| M-02 | Pocas pruebas | P1 | 180 pruebas + 32 subtests | Suite completa | RESUELTO |
| M-03 | CI débil | P3 | Ruff, ShellCheck, Bandit, pip-audit, Gitleaks, cobertura, SBOM | CI verde | RESUELTO |
| M-04 | Portable desincronizada | P2 | Lista ampliada y `--check` | `ci.sh` | RESUELTO |
| V-01 | Ruff F821 | P1 | Shim `_injected()` | Ruff local/CI | RESUELTO |
| V-02 | F-string 3.12 | P1 | Reescritura 3.10+ | `py_compile` 3.10+ | RESUELTO |
| V-03 | Token en documentación | P2 | Redactado | Gitleaks | RESUELTO |
| V-04 | Prueba dependía de `browser-use` | P1 | Doble en PATH | Suite con `HOME` vacío | RESUELTO |
| V-05 | Transiciones de jobs sin validar | P2 | `TRANSITIONS` + `JobStateError` | `test_transiciones_de_trabajo` | RESUELTO |
| L-01 | Sin E2E contra X | P0 | Requiere cuenta autorizada | No ejecutada | PENDIENTE |
| L-02 | Accesibilidad sin auditoría | P2 | Revisión con lector de pantalla | Manual | PARCIALMENTE RESUELTO |
| L-03 | mypy informativo | P2 | Resolver 33 errores | `mypy` | PENDIENTE |
| L-04 | Cobertura < 90 % global | P2 | Ampliar pruebas | `coverage` | PARCIALMENTE RESUELTO |
| L-05 | Cookie heredada (sin emisión) | P2 | Migración coordinada | Pruebas de sesión | ACEPTADO CON RIESGO |
| L-06 | Token en historial de git | P2 | Purga con `push --force` | Gitleaks histórico | ACEPTADO CON RIESGO |
| L-07 | UI sin paginación/copiar/importar | P3 | Añadir controles | Manual/UI | PENDIENTE |
| L-08 | `web/app.py` grande | P3 | Extracción por etapas | Pruebas de contrato | PENDIENTE |
| L-09 | Sin licencia | P3 | Decisión del titular | — | ACEPTADO CON RIESGO |
