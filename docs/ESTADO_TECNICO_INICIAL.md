# Estado técnico inicial

Fecha de referencia: noviembre de 2026.
Rama de trabajo: `modernizacion-integral`.
Ámbito: CLI `xrepost.sh`, motor `xrepost.py`, panel `web/app.py`, interfaz
`web/static/`, scripts de arranque, pruebas y empaquetado portable.

Este documento describe el estado **encontrado** antes de la modernización y
sirve de línea base para medir los cambios. No describe el estado final: eso
está en [`INFORME_FINAL.md`](INFORME_FINAL.md).

## 1. Inventario de partida

| Pieza | Tecnología | Observaciones |
| --- | --- | --- |
| `xrepost.sh` | Bash + Python embebido | Interfaz principal, modo interactivo y por argumentos, exportación CSV/Markdown, historial y deshacer. |
| `xrepost.py` | Python ejecutado por `browser-use` vía stdin | Motor de navegación real sobre Chrome/CDP. No dispone de `__file__`. |
| `web/app.py` | `http.server` de la biblioteca estándar | Panel local que lanza el motor como subproceso. |
| `web/static/` | HTML + CSS + JavaScript nativo | Una sola página, sin capas de estado formales. |
| `xrepost_accounts.py`, `xrepost_hashtags.py`, `xrepost_network.py` | Python | Persistencia y preferencias auxiliares. |
| Pruebas | `unittest` ejecutado con `pytest` | 96 pruebas y 18 subpruebas en la línea base. |
| CI | `.github/workflows/ci.yml` + `ci.sh` | Pruebas, sintaxis y comprobación de la copia portable. |

## 2. Método y métricas de la línea base

- Inspección de todos los módulos Python, scripts Bash, HTML/CSS/JS, pruebas,
  workflow de CI y documentación.
- Ejecución de la suite antes de modificar código: **96 pruebas aprobadas**,
  18 subpruebas, Python 3.14.4.
- Cobertura medida: no disponible en el entorno inicial (sin `coverage`).
  No se declara ninguna cifra no medida.
- Módulos de estado compartido entre CLI y panel: 0.
- Endpoints del panel: contrato antiguo, sin sesiones ni CSRF.
- Documentación: `README.md` extenso, sin carpeta `docs/` separada por
  audiencias.

### Escala de prioridad

| Prioridad | Equivalencia | Criterio |
| --- | --- | --- |
| **P0** | Crítica | Explotable de forma directa o pérdida/integridad grave de datos. |
| **P1** | Alta | Fallo probable con impacto directo en seguridad, integridad o fiabilidad. |
| **P2** | Media | Degradación, deuda que bloquea el crecimiento o riesgo acotado. |
| **P3** | Baja | Mantenibilidad, accesibilidad o experiencia de uso. |

## 3. Hallazgos

Cada fila incluye los campos exigidos: identificador, prioridad, archivo o
componente, evidencia, impacto, riesgo, solución propuesta, prueba necesaria y
estado. Los estados son: pendiente, resuelto, aceptado o no reproducible.

### 3.1 Seguridad

| ID | Pri. | Archivo / componente | Evidencia inicial | Impacto | Riesgo | Solución propuesta | Prueba necesaria | Estado |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S-01 | P0 | `web/app.py` autenticación; `iniciar.sh` | El token maestro viajaba en `/?token=…` y se escribía en el log; se aceptaba como credencial permanente. | Robo del token por historial, logs o Referer; control total del panel. | Alto | Token de arranque de un solo uso canjeado por cookie `HttpOnly` + `SameSite=Strict`; secreto en archivo `0600`; no se registra. | Acceso sin sesión, token inválido, reutilización, caducidad y rotación. | Resuelto |
| S-02 | P0 | `web/app.py` `_origin_ok` y handlers POST | No se validaba `Origin` ni existía token CSRF. | Una página externa podía disparar POST contra `127.0.0.1`. | Alto | `X-CSRF-Token` por sesión, `Origin`/`Host` exactos, `Sec-Fetch-Site` y `Content-Type`. | POST sin Origin, externo, sin token, token erróneo y válido. | Resuelto |
| S-03 | P2 | `web/app.py` comparación de tokens | Comparación con `==` sobre cadenas. | Fuga de información por temporización. | Bajo | `hmac.compare_digest` en todas las comparaciones de secretos. | Comparación correcta/incorrecta y longitudes distintas. | Resuelto |
| S-04 | P1 | `web/app.py` login | Sin límite de intentos. | Fuerza bruta local/remota contra el panel. | Medio | Bloqueo progresivo por IP con ventana temporal y registro del bloqueo. | Fallos sucesivos, bloqueo, expiración y éxito posterior. | Resuelto |
| S-05 | P2 | `web/app.py` respuestas HTTP | Sin CSP, `X-Frame-Options`, COOP/CORP ni `Referrer-Policy`. | Clickjacking, sniffing y filtrado de Referer. | Medio | CSP estricta, `no-store`, `nosniff`, `DENY`, COOP/CORP y `frame-ancestors 'none'`. | Cabeceras presentes en HTML, JSON y errores. | Resuelto |
| S-06 | P1 | `web/app.py`, `xrepost_cdp.py` | El CDP aceptaba cualquier URL, incluidas remotas y con credenciales. | Control de un navegador ajeno o remoto con la sesión de X. | Alto | Validación de esquema, loopback literal, puerto explícito, proceso y perfil dedicados; `--strict-cdp`. | Endpoint remoto, credenciales, ruta, puerto inválido, Chrome ausente y perfil ajeno. | Resuelto |
| S-07 | P1 | `web/app.py` ejecución del motor | `shell=True` y entorno heredado completo. | Inyección de comandos y filtración de secretos al subproceso. | Alto | Listas de argumentos, sin shell, entorno con lista blanca y grupo de procesos propio. | Argumentos con metacaracteres y entorno sin variables sensibles. | Resuelto |
| S-08 | P2 | `xrepost_fs.py` | Permisos dependientes del `umask` del usuario. | Historial y estado legibles por otros usuarios locales. | Medio | `umask 077`, directorios `0700`, archivos `0600` y escritura atómica. | Modos tras crear y tras reemplazar archivos. | Resuelto |
| S-09 | P2 | `xrepost_fs.py` | Lectura/escritura directa con `Path`, sin comprobar enlaces simbólicos. | Escape del directorio de datos mediante symlinks. | Medio | `O_NOFOLLOW`, validación de propietario y `safe_join` para rutas relativas. | Symlink en archivo y directorio; ruta con `..`. | Resuelto |

### 3.2 Integridad y fiabilidad

| ID | Pri. | Archivo / componente | Evidencia inicial | Impacto | Riesgo | Solución propuesta | Prueba necesaria | Estado |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R-01 | P1 | `xrepost_history.py` | `open(..., "a")` sin `fsync` ni reemplazo atómico. | Eventos truncados o perdidos tras un corte. | Alto | Escritura temporal + `fsync` + `os.replace` y bloqueo de escritura. | Corte simulado, concurrencia y relectura del JSONL. | Resuelto |
| R-02 | P1 | `xrepost.py`, `xrepost_labels.py` | Un resultado incierto se trataba como fallo reintentable. | Reposts duplicados cuando la acción sí se completó. | Alto | `UNCERTAIN_RESULTS`, estado `unconfirmed`, sin reintento automático; `--force` explícito. | Resultado ambiguo y comprobación de que no se reintenta. | Resuelto |
| R-03 | P0 | `xrepost.py` repost/cita/undo | Se asumía el éxito tras pulsar el botón. | Historial falso y acciones no realizadas. | Alto | Verificación del DOM y del estado del botón tras cada acción. | Confirmación ausente, botón sin cambiar y éxito real. | Resuelto |
| R-04 | P1 | `xrepost.py` bucle de ejecución | Un fallo de sesión, captcha o límite de X no detenía la tanda. | Ráfaga de fallos y posible bloqueo de la cuenta. | Alto | `FATAL_RESULTS` detiene la ejecución y deja estado visible. | Sesión expirada, captcha y límite de actividad. | Resuelto |
| R-05 | P1 | `web/app.py` trabajos | Los trabajos vivían solo en memoria. | Reiniciar el panel perdía el estado y el progreso. | Alto | `xrepost_jobs.py` con registro JSON persistente, estados y `recover()`. | Crear, reiniciar y recuperar como `INTERRUPTED`. | Resuelto |
| R-06 | P1 | `web/app.py` subprocesos | `subprocess.run` sin grupo de procesos. | Procesos huérfanos y Chrome ocupado tras cancelar. | Alto | `start_new_session`, `SIGTERM` y escalado a `SIGKILL` con espera. | Cancelación, timeout y cierre del panel. | Resuelto |
| R-07 | P2 | `xrepost_history.py` | Sin diagnóstico ni backup verificable. | Corrupción del historial detectada solo a mano. | Medio | `--diagnose`, `--backup`, `--restore` y checksum SHA-256. | Backup manipulado, restauración forzada y diagnóstico. | Resuelto |
| R-08 | P2 | `xrepost_filters.py` | El panel y el motor interpretaban los filtros por separado. | Resultados distintos entre previsualización y ejecución. | Medio | `normalize_spec()` como fuente única y `to_env()` para el motor. | Mismos filtros en panel y entorno `X_*`. | Resuelto |

### 3.3 Funcionalidad y experiencia de uso

| ID | Pri. | Archivo / componente | Evidencia inicial | Impacto | Riesgo | Solución propuesta | Prueba necesaria | Estado |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F-01 | P1 | `web/app.py`, `xrepost_inbox.py` | Previsualizar y ejecutar eran pasos sin trazabilidad persistente. | Imposible revisar o aprobar publicaciones concretas. | Medio | Bandeja persistente por ID con estados y reconciliación con el motor. | Alta, decisión, importación y sincronización tras ejecución. | Resuelto |
| F-02 | P2 | `xrepost_filters.py`, `xrepost_groups.py` | No se podían guardar perfiles ni grupos de cuentas. | Repetición manual de la misma configuración. | Bajo | Perfiles de filtros, grupos con alias y favoritos, exportación CSV. | CRUD, límites, duplicados e importación. | Resuelto |
| F-03 | P2 | `xrepost_schedule.py` | No había programación de búsquedas. | Dependencia de ejecutar a mano cada día. | Bajo | Programación de solo previsualización; nunca repost automático. | Frecuencias, próxima ejecución y vencimiento. | Resuelto |
| F-04 | P2 | `xrepost_stats.py` | Sin estadísticas o sin distinguir resultados inciertos. | Métricas engañosas. | Medio | Estadísticas con denominador explícito y separación de confirmados/desconocidos. | Agregación de historial y porcentajes. | Resuelto |
| F-05 | P2 | `xrepost_exports.py` | Exportación limitada a CSV/Markdown por ejecución. | Dificultad para conservar o compartir resultados. | Bajo | CSV con neutralización de fórmulas, Markdown, JSON, HTML y PDF. | Cada formato, escape y enlace seguro. | Resuelto |
| F-06 | P2 | `web/static/` | Una sola vista, sin temas ni navegación por teclado. | Uso incómodo y poca accesibilidad. | Medio | Ocho pestañas, temas claro/oscuro, ARIA, foco visible y responsive. | Estructura, pestañas, CSRF en la UI y contraste. | Resuelto |
| F-07 | P1 | `web/static/`, motor | Mensajes genéricos y éxito asumido. | El usuario no sabía qué se publicó realmente. | Alto | Estados reales por publicación, progreso y errores del motor. | Snapshot, progreso, estados y exportación. | Resuelto |

### 3.4 Mantenibilidad y pruebas

| ID | Pri. | Archivo / componente | Evidencia inicial | Impacto | Riesgo | Solución propuesta | Prueba necesaria | Estado |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M-01 | P2 | `xrepost_history.py` y consumidores | Tres lecturas distintas del historial. | Estados incoherentes entre CLI, motor y panel. | Medio | Módulo compartido con lectura, estados y rotación. | Consistencia entre capas y eventos de undo. | Resuelto |
| M-02 | P1 | `tests/`, `web/test_*.py` | 96 pruebas centradas en CLI y panel básico. | Regresiones de seguridad y persistencia sin detectar. | Alto | Pruebas de módulos, seguridad, estados y simulación del motor. | Suite completa sin fallos ni pruebas desactivadas. | Resuelto |
| M-03 | P3 | `.github/workflows/ci.yml`, `ci.sh` | Solo `pytest` y comprobaciones de sintaxis. | Deuda de estilo y seguridad sin visibilidad. | Bajo | Ruff, ShellCheck, Bandit, pip-audit, Gitleaks, cobertura, SBOM y paquete. | CI reproducible y bloqueante en seguridad. | Resuelto |
| M-04 | P2 | `sync_portable.sh` | Lista incompleta de archivos. | Copia portable rota o desactualizada. | Medio | Lista ampliada y verificación `--check` en CI. | Sincronización de todos los módulos. | Resuelto |

## 4. Riesgos residuales aceptados

1. **Uso personal en loopback**: el panel no está pensado para exposición en
   red. `--host` distinto de loopback se rechaza salvo petición explícita y se
   documenta como fuera de soporte.
2. **Chrome comprometido**: si un tercero controla el navegador o el perfil,
   ninguna capa de la aplicación puede garantizar integridad. Se documenta en
   el modelo de amenazas.
3. **Dependencias externas**: `browser-use`, Chrome y la sesión de X no se
   pueden simular por completo. Las pruebas usan dobles locales y los límites
   se documentan en `TESTING.md`.
4. **Cobertura**: el entorno de auditoría inicial no permitía instalar
   `coverage`; se midió después en un entorno aislado y la cifra real está en
   `INFORME_FINAL.md`.

## 5. Conclusión

La línea base era funcional pero acumulaba deuda crítica en autenticación,
verificación de acciones y persistencia. La modernización se organizó por
fases (seguridad → integridad → fiabilidad → funcionalidad → UX → pruebas →
documentación), verificando cada fase con la suite completa antes de avanzar.
