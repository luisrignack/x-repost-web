# API del panel

Base: `http://127.0.0.1:8765`. Todas las respuestas son JSON excepto los
recursos estáticos y las descargas.

## 1. Autenticación

### Sesión de navegador

1. `GET /?token=<token>` valida el **token de arranque** (de un solo uso) y
   responde `303` con `Set-Cookie: xrepost_sid=…`. Reutilizarlo devuelve `401`.
   El token maestro no se acepta en la URL.
2. `GET /api/session` devuelve el token CSRF.
3. Cada escritura envía `X-CSRF-Token`.

### Cliente de línea de comandos

```bash
curl -H "X-Token: $TOKEN" http://127.0.0.1:8765/api/health
```

`X-Token` no necesita CSRF. La cookie heredada `xrepost_token` solo permite
lecturas.

### Cabeceras obligatorias

| Cabecera | Cuándo |
| --- | --- |
| `Host` | Siempre; debe ser loopback y el puerto del servidor. |
| `Origin` | En escrituras; si está, debe coincidir con `Host`. |
| `X-Token` o cookie + `X-CSRF-Token` | Autenticación. |
| `Content-Type: application/json` | En escrituras con cuerpo. |

### Errores

| Código | Significado |
| --- | --- |
| `400` | Datos inválidos. |
| `401` | Sin autenticación o sesión caducada. |
| `403` | `Host`/`Origin`/CSRF incorrectos. |
| `404` | Recurso inexistente. |
| `409` | Ya hay una ejecución en curso. |
| `413` | Cuerpo mayor de 1 MB. |
| `415` | `Content-Type` incorrecto. |
| `429` | Demasiados intentos; incluye `retry_after`. |
| `500` | Error interno (sin detalles sensibles). |

Formato de error:

```json
{"error": "Mensaje para el usuario"}
```

## 2. Sesión y estado

### `GET /api/session`

```json
{
  "ok": true,
  "authenticated": true,
  "created": 1763500000,
  "expires_in": 28740,
  "idle_expires_in": 1790,
  "rotations": 0,
  "csrf": "…",
  "token_ok": true
}
```

Crea una cookie de sesión si no existe.

### `POST /api/session/rotate`

Rota la sesión y devuelve el nuevo CSRF. Requiere CSRF.

### `POST /api/session/logout`

Revoca la sesión y borra la cookie.

### `GET /api/health`

```json
{
  "ok": true,
  "engine": "/ruta/xrepost.sh",
  "engine_ok": true,
  "chrome": true,
  "history": "/ruta/history.jsonl",
  "busy": false,
  "state_dir": "/ruta/state",
  "version": "2.0"
}
```

### `GET /api/diagnostics`

Informe de motor, permisos, historial, Chrome/CDP y red. No incluye secretos.

### `GET /api/cdp`

Estado del endpoint CDP, procesos de Chrome y problemas detectados.

### `GET /api/network` / `POST /api/network`

Consulta o guarda la preferencia de red. `POST` acepta:

```json
{
  "mode": "server",
  "proxy": "proxy.empresa:8080",
  "proxy_scheme": "http",
  "bypass": "localhost,127.0.0.1,.etnea.cu"
}
```

### `POST /api/network/restart`

Relanza Chrome con la preferencia vigente. Rechaza `409` si hay un trabajo.

## 3. Búsqueda y ejecución

### `POST /api/preview`

```json
{
  "users": "@foo, @bar",
  "from": "2024-01-01",
  "to": "2024-01-31",
  "scope": "originals",
  "match": "cuba",
  "exclude": "empleo",
  "quote": "",
  "limit": 10,
  "delay": 20,
  "profile_id": "",
  "filters": {
    "include": ["cuba"],
    "lang": ["es"],
    "media": "yes"
  }
}
```

Respuesta `202`:

```json
{"id": "a1b2c3d4", "state": "CREATED"}
```

### `POST /api/apply`

```json
{
  "users": "@foo",
  "from": "2024-01-01",
  "to": "2024-01-31",
  "scope": "originals",
  "quote": "",
  "limit": 10,
  "delay": 20,
  "confirm": true,
  "preview_id": "a1b2c3d4",
  "selected_urls": ["https://x.com/foo/status/1"]
}
```

Requisitos:

- `confirm` debe ser `true`.
- `delay` mínimo 5 segundos.
- `preview_id` debe existir, ser una previsualización terminada y coincidir en
  su clave de parámetros.
- `selected_urls` es opcional, pero debe ser un subconjunto de la
  previsualización.

Respuesta `202`: `{"id": "…", "state": "CREATED"}`.

### `POST /api/undo`

```json
{"last": true}
```

o

```json
{"url": "https://x.com/foo/status/1234567890"}
```

### `POST /api/cancel`

Cancela el trabajo en curso. Devuelve `409` si no hay ninguno.

## 4. Trabajos

### `GET /api/jobs`

Lista hasta 100 trabajos persistidos y los activos en memoria.

```json
{
  "jobs": [
    {
      "id": "a1b2c3d4",
      "kind": "preview",
      "state": "COMPLETED",
      "status": "done",
      "created": "2026-11-18T10:00:00+00:00",
      "started": "2026-11-18T10:00:01+00:00",
      "finished": "2026-11-18T10:02:00+00:00",
      "elapsed_label": "1m 59s",
      "post_count": 12,
      "lines": ["…"],
      "posts": [{"url": "…", "autor": "…", "usuario": "…", "texto": "…", "fecha": "…", "estado": "…"}],
      "progress": 1.0,
      "exports": {"csv": "…"},
      "params": {"users": "@foo", "from": "2024-01-01"}
    }
  ]
}
```

### `GET /api/jobs/<id>`

Detalle del trabajo. Busca primero en memoria y luego en el registro
persistente.

### `GET /api/jobs/<id>/export/<formato>`

Formatos: `csv`, `md`, `json`, `html`, `pdf`. Devuelve el archivo con
`Content-Disposition: attachment`.

### `GET /api/history?n=30`

```json
{"entries": [{"ts": "…", "action": "repost", "result": "reposted", "id": "1", "url": "…"}]}
```

`n` se limita a 1–200.

### `GET /api/history/diagnostic`

```json
{
  "path": "/ruta/history.jsonl",
  "exists": true,
  "size_bytes": 48210,
  "archives": ["/ruta/history-archivo-2026-10-01.jsonl"],
  "total_lines": 120,
  "total_events": 120,
  "valid_events": 120,
  "corrupt_events": 0,
  "corrupt": [],
  "unique_posts": 95,
  "reposts_confirmed": 80,
  "quotes": 5,
  "undone": 3,
  "unknown": 1,
  "errors": 0,
  "still_reposted": 77,
  "undoable": 77,
  "last_event": "2026-11-18T10:00:00+00:00",
  "last_run": "20261118T100000Z",
  "integrity": "ok",
  "warnings": []
}
```

## 5. Cuentas y grupos

### `GET /api/accounts?q=…&limit=8&exclude=…`

Sugerencias de cuentas recordadas, con alias y favorito si existen.

### `GET /api/accounts/all`

Lista completa con actividad:

```json
{
  "accounts": [
    {
      "handle": "foo",
      "count": 12,
      "last_used": "2026-11-01T…",
      "alias": "Medios",
      "favorite": true,
      "reposts": 8,
      "quotes": 2,
      "undone": 1,
      "errors": 1,
      "last_activity": "2026-11-10T…"
    }
  ]
}
```

### `POST /api/accounts/meta`

```json
{"handle": "foo", "alias": "Medios", "favorite": true}
```

### `POST /api/accounts/clear`

Borra las cuentas recordadas (no el historial).

### `GET /api/groups`

```json
{"groups": [{"id": "…", "name": "Medios", "members": [{"handle": "foo", "alias": ""}]}], "counts": {"…": 3}}
```

### `POST /api/groups`

```json
{"name": "Medios", "description": "Prensa", "members": ["@foo", "bar"]}
```

### `PATCH /api/groups/<id>`

Permite `name`, `description` y `members`.

### `POST /api/groups/<id>/members`

```json
{"handles": ["baz"], "action": "add"}
```

o

```json
{"handles": ["bar"], "action": "remove"}
```

También se acepta la clave `members` en lugar de `handles`.

### `POST /api/groups/<id>/import`

```json
{"text": "nuevo;Alias\n@otro\n", "replace": false}
```

### `POST /api/groups/<id>/delete`

Borra el grupo.

### `GET /api/groups/<id>/export?format=csv|json`

Descarga el grupo.

## 6. Perfiles de filtros

### `GET /api/profiles`

```json
{"profiles": [{"id": "…", "name": "Cuba", "filters": {"include": ["cuba"]}}]}
```

### `POST /api/profiles`

```json
{"id": "", "name": "Cuba", "filters": {"include": ["cuba"], "lang": ["es"]}}
```

### `POST /api/profiles/<id>/duplicate`

```json
{"name": "Cuba (copia)"}
```

### `DELETE /api/profiles/<id>`

Borra el perfil. (También se acepta `POST /api/profiles/<id>` con el mismo
efecto, por compatibilidad con clientes que solo usan POST.)

### `POST /api/profiles/import`

```json
{"version": 1, "profiles": [{"name": "…", "filters": {}}]}
```

### `POST /api/filters/validate`

```json
{"filters": {"include": ["cuba"], "regex": "…"}}
```

Devuelve:

```json
{"ok": true, "filters": {"include": ["cuba"]}, "env": {"X_MATCH": "cuba"}}
```

o `400` con el error.

## 7. Bandeja

### `GET /api/inbox?status=pending&q=…&limit=200`

```json
{
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
      "added": "…",
      "updated": "…"
    }
  ],
  "counts": {"pending": 2, "approved": 1, "verified": 0}
}
```

### `POST /api/inbox/decide`

```json
{"ids": ["123"], "status": "approved"}
```

Estados humanos permitidos: `pending`, `approved`, `rejected`.

### `POST /api/inbox/apply`

Ejecuta las aprobadas:

```json
{"delay": 20}
```

### `POST /api/inbox/import`

```json
{"items": [{"id": "123", "url": "https://x.com/foo/status/123"}]}
```

## 8. Programación

### `GET /api/schedules`

Lista ordenada por `next_run`.

### `POST /api/schedules`

```json
{
  "name": "Diario",
  "params": {"users": "@foo", "from": "2026-11-18", "to": "2026-11-18"},
  "frequency": "daily",
  "run_at": "2026-11-19T08:00:00+00:00",
  "enabled": true,
  "notify": true
}
```

`frequency`: `once`, `daily`, `weekly`, `monthly`. `run_at` debe ser futuro.

### `POST /api/schedules/<id>/run`

Lanza una previsualización ahora.

### `PATCH /api/schedules/<id>`

Permite `name`, `enabled`, `notify`, `frequency`, `run_at`, `params`.

### `POST /api/schedules/<id>/delete`

Borra la programación.

## 9. Estadísticas

### `GET /api/stats?days=30`

```json
{
  "found": 25,
  "reposts_confirmed": 8,
  "confirmed_total": 10,
  "quotes": 2,
  "undone": 1,
  "failed": 0,
  "unknown": 1,
  "errors": 1,
  "discarded": 3,
  "approved": 4,
  "verified": 8,
  "inbox_pending": 2,
  "confirmation_rate": 90.9,
  "rate_denominator": 11,
  "by_account": [
    {
      "handle": "foo",
      "reposts": 8,
      "quotes": 2,
      "undone": 1,
      "failed": 0,
      "unknown": 1,
      "last": "2026-11-10T…"
    }
  ],
  "daily": [{"date": "2026-11-01", "events": 3}],
  "monthly": [{"month": "2026-11", "events": 12}],
  "last_activity": "2026-11-10T…",
  "jobs": {
    "total": 5,
    "previews": 3,
    "applies": 2,
    "undos": 0,
    "states": {"COMPLETED": 5}
  },
  "schedules": {"total": 2, "enabled": 1, "next": "2026-11-19T08:00:00+00:00"},
  "total_events": 120
}
```

`confirmation_rate` usa
`confirmados / (confirmados + desconocidos + fallos)`.

## 10. Exportaciones y backup

### `POST /api/export`

```json
{
  "format": "csv",
  "rows": [{"fecha": "…", "autor": "…", "usuario": "…", "texto": "…", "url": "…", "estado": "…"}],
  "title": "Informe"
}
```

Formatos: `csv`, `md`, `json`, `html`, `pdf`.

### `GET /api/backups`

Lista backups del historial con tamaño, fecha y checksum.

### `POST /api/backup`

```json
{"mode": "history"}
```

o

```json
{"mode": "bundle"}
```

`bundle` incluye historial y documentos de estado.

### `POST /api/restore`

```json
{"path": "/ruta/backup.jsonl", "force": false}
```

Verifica el checksum, conserva el estado actual y devuelve el diagnóstico.

### `POST /api/history/backup`

Alias compatible de `POST /api/backup` con `mode=history`.

## 11. Recursos estáticos

- `GET /` sirve el panel (requiere autenticación).
- `GET /static/<archivo>` sirve JS, CSS e imágenes con CSP.
- `GET /favicon.ico` responde `204`.

## 12. Ejemplo completo con curl

```bash
TOKEN="$(cat ~/.local/state/xrepost/panel-token)"
BASE="http://127.0.0.1:8765"

curl -s -H "X-Token: $TOKEN" "$BASE/api/health" | jq .

curl -s -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"users":"@foo","from":"2024-01-01","to":"2024-01-31"}' \
  "$BASE/api/preview" | jq .
```

## 13. Compatibilidad

Se conservan los endpoints anteriores: `/api/health`, `/api/history`,
`/api/network`, `/api/network/restart`, `/api/preview`, `/api/apply`,
`/api/undo`, `/api/cancel`, `/api/accounts`, `/api/hashtags`,
`/api/accounts/clear`, `/api/hashtags/clear`, `/api/jobs/<id>` y
`/api/jobs/<id>/export/{csv,md}`.

Los campos antiguos de los trabajos (`status`, `lines`, `posts`, `progress`)
siguen presentes junto a los nuevos (`state`, `elapsed_label`, `exports`).
