# Gestión de trabajos

Referencia: [`PERSISTENCIA.md`](PERSISTENCIA.md) · Recuperación:
[`RECUPERACION.md`](RECUPERACION.md) · API: [`API.md`](API.md)

## 1. Dónde se guardan

- Registro: `<runs>/jobs.json` (por defecto `web/.runs/jobs.json`).
- Archivos de una ejecución: `<runs>/<job_id>/posts.csv`,
  `posts.md`, `selected.json` y logs en memoria.
- El registro guarda solo parámetros saneados: se eliminan `token`, `csrf`,
  `password`, `secret`, `confirm`, `only_urls_file` y claves que empiezan por
  `_`.

## 2. Estados canónicos

```text
CREATED → QUEUED → RUNNING → COMPLETED
                            → FAILED
                            → CANCELLED
                            → TIMED_OUT
(reinicio) QUEUED/RUNNING/CREATED → INTERRUPTED
```

`status` conserva el contrato anterior del panel (`running`, `done`, `error`,
`cancelled`, `interrupted`).

## 3. Transiciones permitidas

| Desde | Hacia |
| --- | --- |
| `CREATED` | `QUEUED`, `CANCELLED`, `FAILED` |
| `QUEUED` | `RUNNING`, `CANCELLED`, `FAILED`, `INTERRUPTED` |
| `RUNNING` | `COMPLETED`, `FAILED`, `CANCELLED`, `TIMED_OUT`, `INTERRUPTED` |
| `COMPLETED` | — |
| `FAILED` | — |
| `CANCELLED` | — |
| `TIMED_OUT` | — |
| `INTERRUPTED` | — |

Repetir el estado actual es idempotente. Un estado terminal no vuelve a
`RUNNING`: un reintento debe crear un trabajo nuevo. `JobStateError` (subclase
de `ValueError`) identifica la transición inválida.

## 4. Campos del registro

`id`, `kind`, `state`, `status`, `created`, `started`, `ended`, `duration`,
`returncode`, `error`, `params`, `post_count`, `pid`, `cancelled` y `updated`.
La previsualización asociada a un `apply` se guarda en `params.preview_id`.

## 5. Cancelación y timeout

- Cancelar marca el trabajo como `cancelled` y envía `SIGTERM` al grupo de
  procesos; tras 3 segundos escala a `SIGKILL` si sigue vivo.
- Si se cancela antes de que el proceso arranque, se cierra igualmente.
- Timeout global: `MAX_JOB_SECONDS = 30 min`. El watchdog marca `TIMED_OUT` y
  termina el grupo. Un trabajo ya marcado como `TIMED_OUT` no se degrada a
  `CANCELLED` por la bandera de cancelación.
- No se dejan procesos huérfanos: el motor se lanza en su propio grupo
  (`start_new_session=True`).

## 6. Poda

- `MAX_JOBS = 20` en memoria y `max_records = 200` en disco.
- Se conserva el trabajo en curso y la previsualización en la que se apoya un
  `apply`.
- `prune()` no borra directorios: el panel decide qué archivos eliminar y
  respeta los trabajos referenciados.
- Los trabajos en `RUNNING`/`QUEUED` no se eliminan por antigüedad.

## 7. Pruebas

- `JobsTest`: creación, saneado de parámetros, ciclo de vida, recuperación y
  poda.
- `test_transiciones_de_trabajo`: estados terminales, repetición idempotente,
  transición inválida y `JobStateError`.
- `web/test_app.py`: API de trabajos, cancelación, progreso, exportaciones y
  recuperación al reconstruir la aplicación.

## 8. Limitaciones

- Un trabajo no se reanuda automáticamente tras un reinicio; se marca
  `INTERRUPTED` para revisión humana.
- El registro es JSON: no está pensado para miles de trabajos concurrentes.
  El diseño es de una ejecución a la vez porque Chrome es una sola sesión.
