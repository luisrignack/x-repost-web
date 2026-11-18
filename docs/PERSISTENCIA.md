# Persistencia

## 1. Filosofía

No hay base de datos ni servidor de estado. xrepost usa:

- **JSONL** para el historial: eventos inmutables, append-only, legibles y
  fáciles de respaldar.
- **JSON** para documentos pequeños de estado: perfiles, grupos, bandeja,
  programación, red y metadatos.
- **Archivos de trabajo** para la salida del motor y las exportaciones.

Todos los archivos se escriben con `xrepost_fs.atomic_write()` (temporal +
`fsync` + `os.replace`), con permisos 0600 y directorios 0700.

## 2. Historial

Ruta por defecto: `~/.local/state/xrepost/history.jsonl`.

### Evento

```json
{
  "ts": "2026-11-18T10:00:00+00:00",
  "run": "20261118T100000Z",
  "action": "repost",
  "result": "reposted",
  "id": "1234567890",
  "url": "https://x.com/foo/status/1234567890",
  "user": "foo",
  "search_user": "foo",
  "author": "Foo",
  "text": "Texto de la publicación",
  "date": "2024-01-01",
  "quote": ""
}
```

Campos obligatorios validados por `xrepost_history.validate_event()`:
`action`, `result`, `id`, `url`.

### Acciones

| `action` | Significado |
| --- | --- |
| `repost` | Intento de repost o cita. |
| `undo` | Intento de deshacer. |

### Reglas de estado

`history_state(entries)` devuelve:

- `reposted`: IDs cuyo último estado es `reposted`.
- `ours`: ID → evento del último repost vigente (para deshacer).

Un `undo_failed` **no** borra el estado reposteado: la publicación sigue siendo
deshacible. Un `undone` o `not_reposted` lo limpia.

### Rotación

- Al superar `XREPOST_HISTORY_MAX_BYTES` (32 MB por defecto) se renombra a
  `history-archivo-<fecha>.jsonl`.
- `history_files()` devuelve los archivos del más antiguo al principal.
- `read_events()` tolera líneas corruptas y las omite.
- `diagnose()` las cuenta sin borrarlas.

## 3. Documentos JSON

### `profiles.json`

```json
{
  "version": 1,
  "profiles": [
    {
      "id": "a1b2c3d4e5f6",
      "name": "Cuba",
      "filters": {"include": ["cuba"], "lang": ["es"]},
      "created": "2026-11-18T10:00:00+00:00",
      "updated": "2026-11-18T10:00:00+00:00"
    }
  ]
}
```

Límite: 100 perfiles. IDs de 6 bytes hexadecimales.

### `groups.json`

```json
{
  "version": 1,
  "groups": [
    {
      "id": "a1b2c3d4e5f6",
      "name": "Medios",
      "description": "Prensa",
      "created": "2026-11-18T10:00:00+00:00",
      "members": [{"handle": "foo", "alias": ""}]
    }
  ]
}
```

Límite: 100 grupos, 500 miembros por grupo. Nombres únicos sin distinguir
mayúsculas.

### `account-meta.json`

```json
{
  "version": 1,
  "accounts": {
    "foo": {"handle": "foo", "alias": "Medios", "favorite": true}
  }
}
```

### `inbox.json`

```json
{
  "version": 1,
  "items": [
    {
      "id": "1234567890",
      "url": "https://x.com/foo/status/1234567890",
      "handle": "foo",
      "author": "Foo",
      "text": "…",
      "date": "2024-01-01",
      "status": "pending",
      "decision": "",
      "note": "",
      "added": "2026-11-18T10:00:00+00:00",
      "updated": "2026-11-18T10:00:00+00:00"
    }
  ]
}
```

Límite: 5000 elementos. Estados en `xrepost_inbox.STATUSES`.

### `schedules.json`

```json
{
  "version": 1,
  "schedules": [
    {
      "id": "a1b2c3d4e5f6",
      "name": "Diario",
      "frequency": "daily",
      "run_at": "2026-11-19T08:00:00+00:00",
      "next_run": "2026-11-19T08:00:00+00:00",
      "enabled": true,
      "notify": true,
      "mode": "preview",
      "params": {"users": "@foo", "from": "2026-11-18", "to": "2026-11-18"},
      "last_run": "",
      "last_job": "",
      "last_result": ""
    }
  ]
}
```

Límite: 50 programaciones. `mode` siempre es `preview`.

### `network.json`

```json
{
  "mode": "direct",
  "proxy": "",
  "proxy_scheme": "http",
  "pac_path": "/ruta/proxy_empresa.pac",
  "bypass": "localhost,127.0.0.1"
}
```

### `accounts.json` y `hashtags.json`

Los mantienen `xrepost_accounts.py` y `xrepost_hashtags.py`; conservan el
formato histórico para no romper el CLI.

## 4. Trabajos

`web/.runs/<id>/`:

```
meta.json        estado y parámetros saneados
engine.log       salida del motor
posts.csv        publicaciones encontradas
exports/         CSV, Markdown, JSON, HTML y PDF
```

`meta.json` se actualiza con `xrepost_jobs.JobStore` y nunca contiene tokens,
CSRF, contraseñas ni `only_urls_file`.

Estados persistentes:

```
CREATED → QUEUED → RUNNING → COMPLETED
                            → FAILED
                            → CANCELLED
                            → TIMED_OUT
(reinicio) RUNNING/QUEUED → INTERRUPTED
```

Al arrancar, `recover()` marca como `INTERRUPTED` los trabajos que quedaron en
`RUNNING` o `QUEUED`. No se reanudan solos.

Poda:

- `MAX_JOBS = 20` en memoria.
- `prune(keep=…)` elimina ejecuciones antiguas, conservando las activas.
- `max_records` y `max_age_days` limitan el registro persistente.

## 5. Concurrencia

`JsonStore` usa `xrepost_fs.locked(path)`:

- Bloqueo exclusivo (`LOCK_EX`) para mutaciones.
- Bloqueo compartido (`LOCK_SH`) para lecturas cuando procede.
- Lectura-modificación-escritura dentro del bloqueo.
- Si el JSON está corrupto, se guarda una copia `<archivo>.corrupt-<fecha>` y
  se devuelve el valor por defecto.
- Si la versión del documento es mayor que la soportada, se lanza `ValueError`
  para no degradar datos de una versión futura.

## 6. Límites y validación

| Documento | Tamaño máximo | Elementos |
| --- | --- | --- |
| Documentos JSON | 4 MB (bandeja 8 MB) | Según el tipo |
| Historial de lectura | 32 MB por archivo | — |
| Cuerpo HTTP | 1 MB | — |
| Exportación | Sin límite explícito | Filas del trabajo |

Los documentos se validan al leer: se descartan entradas sin `id`, listas que
no son listas y tipos inesperados.

## 7. Migraciones

No hay migraciones automáticas. El campo `version` permite detectar documentos
futuros. Para cambiar un esquema:

1. Añade el campo con un valor por defecto al leer.
2. Mantén la escritura compatible hacia atrás durante una versión.
3. Documenta el cambio en `CHANGELOG_TECNICO.md`.
4. Añade una prueba de lectura del formato anterior.

## 8. Integridad

- `diagnose()` informa de eventos válidos, corruptos, archivos y estado.
- `backup()` copia historial y rotaciones en un único JSONL con checksum.
- `verify_backup()` comprueba SHA-256 y que no haya líneas corruptas.
- `restore()` conserva el historial actual antes de sobrescribir.
- Los backups de estado completo (`bundle`) excluyen el perfil de Chrome.

## 9. Qué no se guarda

- Tokens, CSRF o contraseñas.
- El contenido del perfil de Chrome dentro de los backups.
- Resultados de `apply` en la programación.
- Contadores derivados: las estadísticas se recalculan siempre.
