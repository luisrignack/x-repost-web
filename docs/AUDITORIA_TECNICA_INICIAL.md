# Auditoría técnica inicial

Fecha de referencia: noviembre de 2026.
Rama de trabajo: `modernizacion-integral`.
Ámbito: CLI `xrepost.sh`, motor `xrepost.py`, panel `web/app.py`, interfaz
`web/static/`, scripts de arranque, pruebas y empaquetado portable.

Este documento describe el estado **encontrado** antes de la modernización y
sirve de línea base para medir los cambios. No describe el estado final: eso
está en `INFORME_FINAL_MODERNIZACION.md`.

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

## 2. Hallazgos

Severidad: **Crítica** (explotable o pérdida de datos), **Alta** (fallo probable
o impacto directo en seguridad/integridad), **Media** (degradación, deuda que
bloquea el crecimiento), **Baja** (mantenibilidad o UX).

### 2.1 Seguridad

| ID | Hallazgo | Severidad | Evidencia inicial | Estado |
| --- | --- | --- | --- | --- |
| S-01 | El token maestro viajaba en la URL y se reutilizaba como credencial permanente. | Crítica | Enlace `/?token=…`, comparación directa en cada petición, token escrito en el log de arranque. | Corregido: sesión + cookie `HttpOnly`, token solo para crear sesión, `--token-file`/`--bootstrap-file` 0600. |
| S-02 | Ausencia de CSRF: una página externa podía disparar POST contra `127.0.0.1`. | Crítica | No se validaba `Origin` ni existía token CSRF. | Corregido: `X-CSRF-Token` obligatorio con sesión, validación exacta de `Origin` y `Host`. |
| S-03 | Comparación de tokens no constante en el tiempo. | Media | `==` sobre cadenas. | Corregido: `hmac.compare_digest`. |
| S-04 | Sin límite de intentos de autenticación. | Alta | Bucle de prueba ilimitado. | Corregido: bloqueo progresivo por IP y ventana temporal. |
| S-05 | Cabeceras de seguridad ausentes (CSP, `X-Frame-Options`, COOP/CORP, `Referrer-Policy`). | Media | Respuestas sin cabeceras. | Corregido: CSP estricta y cabeceras en todas las respuestas. |
| S-06 | El CDP aceptaba cualquier URL, incluidas remotas y con credenciales. | Alta | Solo se comprobaba que respondiera. | Corregido: validación de esquema, loopback, puerto y ruta en `xrepost_cdp.py`; `--strict-cdp`. |
| S-07 | Subprocesos con `shell=True` y entorno heredado completo. | Alta | Riesgo de inyección y filtración de secretos al motor. | Corregido: listas de argumentos, sin shell, entorno con lista blanca. |
| S-08 | Permisos de archivos dependientes del `umask` del usuario. | Media | Historial y estado podían quedar en 0644. | Corregido: `umask 077`, directorios 0700 y archivos 0600 en `xrepost_fs.py`. |
| S-09 | Sin defensa contra enlaces simbólicos en rutas de estado. | Media | Lectura/escritura directa con `Path`. | Corregido: rechazo explícito de symlinks y comprobación de pertenencia. |

### 2.2 Integridad y fiabilidad

| ID | Hallazgo | Severidad | Evidencia inicial | Estado |
| --- | --- | --- | --- | --- |
| R-01 | Escritura del historial no atómica. | Alta | `open(..., "a")` sin `fsync` ni reemplazo atómico. | Corregido: escritura atómica con temporal + `os.replace` + `fsync`. |
| R-02 | Un resultado incierto se trataba como fallo reintentable. | Alta | `unconfirmed` no existía como estado diferenciado. | Corregido: `UNCERTAIN_RESULTS`, no se reintenta sin `--force`; bandeja con estado `unconfirmed`. |
| R-03 | El repost no se verificaba tras la acción. | Crítica | Se asumía el éxito tras pulsar el botón. | Corregido: verificación real del botón y del estado de la publicación. |
| R-04 | Un fallo de sesión, captcha o límite de X no detenía la tanda. | Alta | Se seguía iterando. | Corregido: `FATAL_RESULTS` detiene la ejecución y deja estado visible. |
| R-05 | Los trabajos del panel vivían solo en memoria. | Alta | Reiniciar el panel perdía el estado. | Corregido: `xrepost_jobs.py` con estados persistentes y `recover()`. |
| R-06 | Cancelar un trabajo podía dejar procesos huérfanos. | Alta | `subprocess.run` sin grupo de procesos. | Corregido: grupo propio, `SIGTERM` y escalado a `SIGKILL`. |
| R-07 | Historial corrupto detectable solo a mano. | Media | Sin diagnóstico ni backup verificable. | Corregido: `--diagnose`, `--backup`, `--restore` y verificación por checksum. |
| R-08 | Filtros del panel y del motor podían divergir. | Media | Cada capa interpretaba los filtros por su cuenta. | Corregido: `xrepost_filters.normalize_spec()` como fuente única. |

### 2.3 Funcionalidad y UX

| ID | Hallazgo | Severidad | Evidencia inicial | Estado |
| --- | --- | --- | --- | --- |
| F-01 | No había revisión previa persistente: previsualizar y ejecutar eran pasos separados sin trazabilidad. | Alta | Sin bandeja ni decisiones. | Corregido: bandeja con estados `pending/approved/rejected/…`. |
| F-02 | No se podían guardar perfiles de filtros ni grupos de cuentas. | Media | Formularios sueltos. | Corregido: `xrepost_filters.py`, `xrepost_groups.py`. |
| F-03 | No había programación de búsquedas. | Media | Solo ejecución manual. | Corregido: `xrepost_schedule.py` (solo previsualización). |
| F-04 | Las estadísticas no existían o no distinguían resultados inciertos. | Media | Sin módulo. | Corregido: `xrepost_stats.py` con denominador explícito. |
| F-05 | Exportaciones limitadas a CSV/Markdown por ejecución. | Media | Sin JSON/HTML/PDF ni backups completos. | Corregido: `xrepost_exports.py`. |
| F-06 | Interfaz de una sola vista, sin temas ni navegación por teclado. | Media | Todo en una página. | Corregido: 8 pestañas, temas claro/oscuro, ARIA y responsive. |
| F-07 | Mensajes de error genéricos y éxito asumido. | Alta | La UI marcaba "hecho" sin comprobar. | Corregido: estados reales por publicación y mensajes del motor. |

### 2.4 Mantenibilidad y pruebas

| ID | Hallazgo | Severidad | Evidencia inicial | Estado |
| --- | --- | --- | --- | --- |
| M-01 | Lógica de estado duplicada entre CLI, motor y panel. | Media | Tres lecturas distintas del historial. | Corregido: `xrepost_history.py` compartido. |
| M-02 | Sin pruebas de los módulos nuevos ni de seguridad. | Alta | 96 pruebas centradas en CLI y panel básico. | Corregido: 136 pruebas y 18 subpruebas, incluidas las de seguridad y módulos. |
| M-03 | CI sin cobertura ni análisis estático condicional. | Baja | Solo `pytest` y sintaxis. | Corregido: cobertura informativa, `ruff`, `shellcheck` y validaciones de sincronización. |
| M-04 | Copia portable desincronizada con los módulos nuevos. | Media | `sync_portable.sh` con lista incompleta. | Corregido: lista ampliada y verificación en CI. |

## 3. Métricas de la línea base

- Pruebas: **96 aprobadas**, 18 subpruebas, Python 3.14.4.
- Módulos de estado compartido: 0.
- Endpoints del panel: contrato antiguo sin sesiones ni CSRF.
- Cobertura medida: no disponible en el entorno inicial (sin `coverage`).
- Documentación: `README.md` extenso, sin carpeta `docs/` ni separación por
  audiencia.

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
4. **Cobertura**: el entorno de auditoría no permite instalar `coverage`; la CI
   remota la ejecuta de forma informativa. No se declara un porcentaje no
   medido.

## 5. Conclusión

La línea base era funcional pero acumulaba deuda crítica en autenticación,
verificación de acciones y persistencia. La modernización se organizó por
fases (seguridad → integridad → fiabilidad → funcionalidad → UX → pruebas →
documentación), verificando cada fase con la suite completa antes de avanzar.
