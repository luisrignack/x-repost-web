# Informe final de modernización

Fecha: 2026-11-18 · Rama: `modernizacion-integral` · Versión: 2.0.0

## A. Resumen ejecutivo

**Estado inicial.** xrepost era un CLI funcional para buscar publicaciones de
cuentas concretas y repostearlas, con un panel web mínimo en Python estándar.
Los problemas principales eran: token en la URL y en el log, ausencia de CSRF,
ausencia de comprobación del endpoint CDP, historial sin escritura atómica ni
diagnóstico, trabajos en memoria que se perdían al reiniciar, clics que se
marcaban como éxito sin verificar el DOM, y una interfaz de una sola vista.

**Estado final.** La aplicación conserva el stack (Python estándar, HTML/CSS/JS,
Chrome/CDP, JSON/JSONL, Bash) y el contrato de la CLI, pero incorpora
autenticación por sesión con CSRF, validación de CDP, escritura atómica con
permisos privados, máquina de estados por publicación, verificación real de
repost/cita/undo, trabajos persistentes y recuperables, bandeja de revisión,
perfiles, grupos, programación de previsualizaciones, estadísticas con
denominador y exportaciones CSV/Markdown/JSON/HTML/PDF.

**Mejoras implementadas.** 13 módulos nuevos, 8 secciones de panel, 5 comandos
nuevos de CLI, 35 pruebas nuevas (171 en total), CI con análisis estático y de
seguridad, SBOM y paquete de distribución, y 16 documentos técnicos.

**Riesgos eliminados.** Token en URL/log, CSRF ausente, CDP sin validar,
escrituras no atómicas, permisos laxos, `shell=True`, éxito supuesto, reintento
de resultados inciertos, pérdida de trabajos al reiniciar, historial sin
diagnóstico ni backup verificable.

**Riesgos pendientes.** Sin pruebas end-to-end contra X (requiere cuenta
autorizada), accesibilidad sin auditoría con lector de pantalla, deuda de
tipado (`mypy` informativo), cookie heredada `xrepost_token` todavía aceptada
solo para lectura, y una token de ejemplo de una ejecución local que permanece
en el historial de git (ver B.4).

## B. Seguridad

### B.1 Hallazgos iniciales y correcciones

| Hallazgo | Severidad | Corrección | Evidencia |
| --- | --- | --- | --- |
| Token maestro en la URL y en el log | P0 | Canje por cookie de sesión `HttpOnly`; el log enmascara `token=` y `csrf=` | `web/app.py`, `xrepost_security.py`, `web/test_app.py` |
| Sin CSRF en escrituras | P0 | `X-CSRF-Token` obligatorio con sesión; `Origin`/`Host` exactos | `xrepost_security.py`, pruebas de CSRF |
| CDP aceptado sin validar | P0 | Esquema, loopback, puerto explícito, proceso y perfil dedicados; `--strict-cdp` | `xrepost_cdp.py`, 4 pruebas |
| Escrituras no atómicas y permisos laxos | P1 | `atomic_write`, `flock`, `0700/0600`, `umask 077`, rechazo de symlinks | `xrepost_fs.py`, 7 pruebas |
| `subprocess` con shell y entorno completo | P1 | Listas de argumentos, sin shell, entorno con lista blanca, grupo de procesos | `web/app.py`, `xrepost.sh` |
| Éxito supuesto tras el clic | P1 | Verificación del DOM en repost, cita y undo | `xrepost.py`, `web/test_engine_selected.py` |
| Resultado incierto reintentado | P1 | `UNCERTAIN_RESULTS`, `skipped_uncertain`, bandeja `unconfirmed` | `xrepost_labels.py`, `xrepost.py` |
| Historial sin integridad ni backup | P2 | Rotación, diagnóstico, backup con SHA-256, restore verificado | `xrepost_history.py`, 5 pruebas |
| Fórmulas maliciosas en CSV | P2 | `csv_safe` y neutralización de alias | `xrepost_exports.py`, `xrepost_groups.py` |
| Token de ejemplo real en la documentación | P2 | Redactado en `ABRIR_LA_APLICACION.md` | `gitleaks` limpio en el árbol actual |
| Sin escaneo de secretos en CI | P2 | `gitleaks` bloqueante sobre el árbol de trabajo | `.github/workflows/ci.yml` |

### B.2 Controles implementados

- Token maestro de 32 bytes, comparación con `hmac.compare_digest`.
- Sesiones con caducidad absoluta (8 h) y por inactividad (30 min), rotación y
  revocación; solo en memoria.
- Bloqueo progresivo por IP tras 8 fallos en 5 minutos.
- CSRF por sesión, validación de `Host`/`Origin`, rechazo de `Content-Type`
  inesperado y límite de cuerpo.
- CSP, `X-Content-Type-Options`, `Referrer-Policy`, `Cache-Control: no-store`,
  `X-Frame-Options: DENY`, COOP/CORP.
- Endpoint CDP validado antes de cada operación; el panel no es un proxy CDP.
- Escritura atómica, `O_NOFOLLOW`, validación de propietario, `safe_join`,
  `remove_tree` limitado a la carpeta de datos.
- Subprocesos sin shell, con `start_new_session`, timeout y limpieza del grupo.

### B.3 Pruebas de seguridad

`web/test_app.py` (55) y `tests/test_core_modules.py` (59) cubren: acceso sin
sesión, token inválido, caducidad, CSRF correcto/incorrecto, `Origin` y `Host`
inválidos, traversal, symlinks, archivos gigantes, JSON corrupto, inyección de
argumentos, CDP no autorizado, fuerza bruta y rotación de sesión.

### B.4 Hallazgos pendientes

- **Cookie heredada `xrepost_token`**: se acepta solo para lectura (crear
  sesión); no puede escribir. Retirarla exige una migración coordinada con
  clientes antiguos; está documentada en `docs/SEGURIDAD.md`.
- **Token en el historial de git**: el commit `10d3896` incluyó un token de
  ejemplo de una ejecución local. Ya no es válido (no existe el archivo de
  token), pero un `gitleaks` con historial lo detectaría. Purificarlo requiere
  reescribir la rama y un `push --force`, que no se ha hecho sin autorización.
- **Sin TLS**: el panel es solo loopback; exponerlo fuera de esa interfaz queda
  fuera del modelo de amenazas.

## C. Arquitectura

### C.1 Cambios

La arquitectura sigue siendo un núcleo Python con módulos compartidos por CLI y
panel, sin frameworks ni servicios externos.

```
xrepost.sh ──► xrepost.py (motor, ejecutado por browser-use)
     │              │
     │              ├── xrepost_history.py ──► JSONL
     │              ├── xrepost_filters.py
     │              ├── xrepost_labels.py
     │              └── xrepost_selectors.py
     │
     └── web/app.py (HTTP 127.0.0.1)
             ├── xrepost_security.py  (sesiones/CSRF)
             ├── xrepost_cdp.py      (validación CDP)
             ├── xrepost_jobs.py     (trabajos)
             ├── xrepost_inbox.py    (bandeja)
             ├── xrepost_state.py    (máquina de estados)
             ├── xrepost_groups.py   (grupos/alias)
             ├── xrepost_filters.py  (perfiles)
             ├── xrepost_schedule.py (programación)
             ├── xrepost_stats.py    (estadísticas)
             ├── xrepost_exports.py  (CSV/MD/JSON/HTML/PDF)
             ├── xrepost_fs.py       (E/S segura)
             └── xrepost_store.py    (JSON concurrente)
```

### C.2 Módulos nuevos

`xrepost_fs`, `xrepost_store`, `xrepost_filters`, `xrepost_cdp`,
`xrepost_security`, `xrepost_jobs`, `xrepost_exports`, `xrepost_groups`,
`xrepost_inbox`, `xrepost_schedule`, `xrepost_stats`, `xrepost_selectors`,
`xrepost_state`.

### C.3 Módulos modificados

`xrepost.py`, `xrepost_history.py`, `xrepost_labels.py`, `web/app.py`,
`web/static/{index.html,app.js,styles.css}`, `xrepost.sh`, `iniciar.sh`,
`ci.sh`, `sync_portable.sh`, `.github/workflows/ci.yml`.

### C.4 Decisiones técnicas

1. Sin dependencias de ejecución: solo biblioteca estándar.
2. Una ejecución a la vez (Chrome es una sola sesión).
3. El planificador solo previsualiza; nunca publica.
4. Un resultado incierto no se reintenta sin `--force`.
5. El historial es la fuente de verdad compartida entre CLI y panel.
6. Los metadatos nuevos (grupos, alias, perfiles) viven en archivos separados
   para que una versión anterior siga leyendo `accounts.json`.

## D. Funcionalidades

**Preservadas.** Todas las opciones del CLI, variables `X_*`, endpoints
antiguos, campos `status`/`lines`/`posts`/`progress`, formato del historial y
del CSV, y estructura de `accounts.json` y `hashtags.json`.

**Nuevas.** Sesión/CSRF, CDP validado, trabajos persistentes, bandeja,
perfiles, grupos con alias/favoritos, programación de previsualizaciones,
estadísticas, exportaciones JSON/HTML/PDF, backups verificables, `--stats`,
`--diagnose`, `--backup`, `--restore`, `--strict-cdp`, `--version`.

**Pendientes.**

| Elemento | Estado | Motivo |
| --- | --- | --- |
| Navegación lateral y secciones Dashboard/Exportaciones/Configuración | No implementado | La UI usa 8 pestañas con las funciones equivalentes; no se partió en más secciones para no duplicar vistas. |
| Paginación de tablas | No implementado | Se filtra y ordena; el límite de resultados acota el volumen. |
| Copiar enlace al portapapeles | No implementado | Existe «Ver en X» y el enlace completo en la tabla. |
| Importación de cuentas desde la UI | Parcial | `parse_import`/`import_into` y el endpoint existen; falta el botón en la interfaz. |
| `UNDO_PENDING`/`UNDONE` en la bandeja | Parcial | La máquina de estados los define y valida, pero el flujo de undo registra el evento en el historial y no actualiza el estado de la bandeja. |
| Notificaciones del sistema | No implementado | La programación avisa dentro del panel (`notify`). |
| Repost automático programado | No implementado a propósito | Requiere consentimiento explícito y auditoría; el prompt lo desaconseja por defecto. |

## E. UX/UI

- Paleta solicitada aplicada como variables CSS (`#0B1220`, `#111C2E`,
  `#1B293D`, `#3B82F6`, `#38BDF8`, `#22C55E`, `#F59E0B`, `#EF4444`,
  `#F1F5F9`, `#94A3B8`).
- Tema claro/oscuro persistido en `localStorage` y `data-theme`.
- Ocho pestañas: Buscar, Bandeja, Cuentas, Filtros, Programación, Historial,
  Estadísticas, Sistema.
- Tablas con ordenación, selección múltiple, «Ver en X» y estados reales.
- Diálogos de confirmación destructiva con resumen y casilla obligatoria.
- Barra de progreso, estados vacíos, mensajes de error y avisos accesibles.
- Responsive verificado a 1280×900 y 390×844 sin desbordamiento.
- Accesibilidad: skip-link, roles `tablist/tab/tabpanel`, `aria-live`, foco
  visible, contraste, `prefers-reduced-motion` y navegación por teclado entre
  pestañas.
- **Pendiente**: auditoría con lector de pantalla real; no se declara WCAG 2.2
  AA completo.

## F. Pruebas

| Métrica | Resultado |
| --- | --- |
| Pruebas | **171 passed, 18 subtests passed** |
| Duración | ~43 s |
| Cobertura de negocio | **91 %** (umbral CI: 90 %) |
| Cobertura total | **85 %** |
| Ruff (`E9,F63,F7,F82`) | Sin hallazgos |
| ShellCheck (`-S error`) | Sin hallazgos |
| Bandit (`-ll`) | 0 medium/high; 12 low documentados |
| Gitleaks (árbol actual) | Sin fugas |
| pip-audit | Sin dependencias de ejecución |
| Mypy | Errores de tipado en módulos históricos; informativo, no bloqueante |
| Pruebas contra X | No ejecutadas (requieren cuenta autorizada) |

Detalle y comandos en `docs/TESTING.md`. No se han desactivado pruebas ni se ha
reducido la cobertura para pasar CI.

## G. Instalación

Requisitos: Linux, Python 3.10+, Chrome/Chromium. Sin dependencias de ejecución.

```bash
git clone https://github.com/luisrignack/x-repost-web
cd x-repost-web
./iniciar.sh            # Chrome dedicado + panel en 127.0.0.1:8765
```

Actualización: `git pull` y relanzar `./iniciar.sh` (idempotente).
Backup/restore: `./xrepost.sh --backup`, `./xrepost.sh --restore RUTA`.
Diagnóstico: `./xrepost.sh --diagnose --strict-cdp`.
Desinstalación: borrar el repositorio y, si se desea, `~/.local/state/xrepost`.
El instalador no modifica perfiles personales de Chrome ni archivos ajenos.

## H. Archivos

**Creados**

```
xrepost_fs.py xrepost_store.py xrepost_filters.py xrepost_cdp.py
xrepost_security.py xrepost_jobs.py xrepost_exports.py xrepost_groups.py
xrepost_inbox.py xrepost_schedule.py xrepost_stats.py xrepost_selectors.py
xrepost_state.py
tests/test_core_modules.py docs/*.md (16)
SECURITY.md CONTRIBUTING.md CHANGELOG.md LICENSE_PENDING.md
requirements.txt requirements-dev.txt ruff.toml .github/dependabot.yml
```

**Modificados**

```
xrepost.py xrepost_history.py xrepost_labels.py xrepost.sh iniciar.sh ci.sh
sync_portable.sh .github/workflows/ci.yml .gitignore README.md
web/app.py web/static/index.html web/static/app.js web/static/styles.css
web/test_app.py web/test_engine_selected.py ABRIR_LA_APLICACION.md
```

**Eliminados**: ninguno.

## I. Evaluación final

**Clasificación: apto para uso local.**

Justificación:

- No quedan vulnerabilidades críticas conocidas sin resolver en el modelo de
  despliegue soportado (loopback, un usuario, sin TLS).
- La CLI y el panel funcionan y están cubiertos por 171 pruebas; CI está en
  verde y bloquea regresiones de sintaxis, seguridad y cobertura.
- Las operaciones que publican están verificadas contra el DOM y los resultados
  inciertos no se reintentan.
- No se declara «producción» porque faltan pruebas end-to-end contra X, la
  accesibilidad no se ha auditado con lector de pantalla y persisten deudas de
  tipado y compatibilidad (cookie heredada).

## Anexo. Criterios de aceptación

| Criterio | Estado | Nota |
| --- | --- | --- |
| Funcionalidades originales | Cumplido | CLI, endpoints y formatos conservados. |
| CLI operativa | Cumplido | Opciones antiguas + 5 nuevas. |
| Panel operativo | Cumplido | 8 secciones. |
| Autenticación endurecida | Cumplido | Sesión, rotación, bloqueo. |
| CSRF | Cumplido | Cabecera + Origin/Host. |
| CDP protegido | Cumplido | Loopback, puerto, proceso y perfil. |
| Permisos de archivos | Cumplido | 0700/0600, sin symlinks. |
| Subprocesos controlados | Cumplido | Sin shell, entorno mínimo. |
| Verificación real del motor | Cumplido | DOM tras cada acción. |
| Inciertos no repetidos | Cumplido | `unconfirmed`, `--force`. |
| Trabajos recuperables | Cumplido | `INTERRUPTED`. |
| Historial consistente | Cumplido | Atómico, diagnóstico, backup. |
| Cuentas y perfiles | Cumplido | Grupos, alias, perfiles. |
| Filtros | Cumplido | 12 criterios, regex seguras. |
| Bandeja | Cumplido | Persistente por ID. |
| Estadísticas reales | Cumplido | Denominador explícito. |
| Exportaciones | Cumplido | CSV/MD/JSON/HTML/PDF. |
| Responsive | Cumplido | 1280 y 390 px. |
| Temas claro/oscuro | Cumplido | Persistido. |
| Accesibilidad revisada | Parcial | Falta lector de pantalla. |
| CI ampliada | Cumplido | Ruff, ShellCheck, Bandit, Gitleaks, pip-audit, mypy informativo, cobertura, SBOM. |
| Pruebas aprobadas | Cumplido | 171 + 18 subtests. |
| Documentación | Cumplido | 16 documentos. |
| Sin funcionalidades simuladas | Cumplido | Sin TODO ni botones vacíos. |
| Sin vulnerabilidades críticas | Cumplido en el modelo soportado | Ver B.4. |
