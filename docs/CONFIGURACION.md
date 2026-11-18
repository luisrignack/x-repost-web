# Configuración

## 1. Prioridad de configuración

Para el panel y el motor, el orden es:

1. Argumentos de línea de comandos.
2. Variables de entorno.
3. Archivos de estado existentes.
4. Valores por defecto.

## 2. Rutas por defecto

| Recurso | Ruta | Variable |
| --- | --- | --- |
| Directorio de estado | `~/.local/state/xrepost/` | `XDG_STATE_HOME` |
| Historial | `~/.local/state/xrepost/history.jsonl` | `X_HISTORY` |
| Cuentas | `~/.local/state/xrepost/accounts.json` | `X_ACCOUNTS` |
| Hashtags | `~/.local/state/xrepost/hashtags.json` | `X_HASHTAGS` |
| Perfiles | `~/.local/state/xrepost/profiles.json` | — |
| Grupos | `~/.local/state/xrepost/groups.json` | — |
| Metadatos de cuentas | `~/.local/state/xrepost/account-meta.json` | — |
| Bandeja | `~/.local/state/xrepost/inbox.json` | — |
| Programación | `~/.local/state/xrepost/schedules.json` | — |
| Trabajos | `web/.runs/` | `--runs` |
| Preferencia de red | `~/.local/state/xrepost/network.json` | `XREPOST_NETWORK_CONFIG` |
| Perfil de Chrome | `~/.local/state/xrepost/chrome-profile` | `XREPOST_CHROME_PROFILE` |
| Token del panel | `~/.local/state/xrepost/panel-token` | `XREPOST_TOKEN_FILE` |
| Enlace de arranque | `~/.local/state/xrepost/panel-url` | `XREPOST_BOOTSTRAP_FILE` |

## 3. Variables del motor y del CLI

| Variable | Valores | Efecto |
| --- | --- | --- |
| `X_APPLY` | `0`/`1` | `1` publica de verdad. Por defecto solo lista. |
| `X_LIMIT` | entero | Máximo de reposts por ejecución. |
| `X_DELAY` | 0–300 | Segundos entre reposts. |
| `X_SKIP_REPLIES` | `0`/`1` | Ignorar respuestas (por defecto `1`). |
| `X_SKIP_RETWEETS` | `0`/`1` | Ignorar retweets (por defecto `1`). |
| `X_MATCH` | lista separada por comas | Solo posts con alguna palabra. |
| `X_EXCLUDE` | lista separada por comas | Descarta posts con alguna palabra. |
| `X_INCLUDE_REGEX` | expresión | Incluye si coincide. |
| `X_EXCLUDE_REGEX` | expresión | Excluye si coincide. |
| `X_LANG` | códigos | Filtra por idioma. |
| `X_MEDIA` | `yes`/`no` | Solo con/sin contenido multimedia. |
| `X_MIN_LEN`, `X_MAX_LEN` | enteros | Longitud del texto. |
| `X_EXACT` | `0`/`1` | Coincidencia exacta de palabras. |
| `X_QUOTE` | texto | Repost con cita. |
| `X_FORCE` | `0`/`1` | Ignora el historial y los estados inciertos. |
| `X_HISTORY` | ruta | Historial. |
| `X_ACCOUNTS` | ruta | Cuentas recordadas. |
| `X_HASHTAGS` | ruta | Hashtags recordados. |
| `X_ONLY_URLS_FILE` | ruta | Ejecuta solo las URLs del archivo. |
| `X_SELF_DIR` | ruta | La exporta `xrepost.sh` para que el motor importe módulos locales. |
| `BU_CDP_URL` | URL | Endpoint de Chrome (por defecto `http://127.0.0.1:9222`). |
| `XREPOST_CHROME_PROFILE` | ruta | Perfil de Chrome. |
| `XREPOST_ENGINE` | ruta | Motor que usa el panel. |
| `XREPOST_NETWORK_CONFIG` | ruta | Archivo de preferencia de red. |
| `XREPOST_HISTORY_MAX_BYTES` | entero | Tamaño de rotación del historial. |

## 4. Argumentos del panel (`web/app.py`)

| Argumento | Por defecto | Descripción |
| --- | --- | --- |
| `--port` | `8765` | Puerto; `0` elige uno aleatorio. |
| `--host` | `127.0.0.1` | Solo loopback; otro valor se rechaza. |
| `--token` | aleatorio | Token fijo (evítalo en entornos compartidos). |
| `--token-file` | — | Archivo 0600 con el token; se crea si no existe. |
| `--bootstrap-file` | — | Archivo 0600 donde escribir el enlace de arranque. |
| `--engine` | `xrepost.sh` | Ruta al motor. |
| `--history` | ruta por defecto | Historial JSONL. |
| `--accounts` | junto al historial | Cuentas recordadas. |
| `--hashtags` | junto al historial | Hashtags recordados. |
| `--runs` | `web/.runs` | Ejecuciones y exportaciones. |
| `--no-open` | desactivado | No abrir el navegador. |
| `--no-scheduler` | desactivado | No ejecutar la programación. |
| `--verbose` | desactivado | Registrar peticiones (sin secretos). |

## 5. Preferencia de red

Se guarda en `network.json` y se aplica al relanzar Chrome:

```json
{
  "mode": "direct",
  "proxy": "",
  "proxy_scheme": "http",
  "pac_path": "/ruta/proxy_empresa.pac",
  "bypass": "localhost,127.0.0.1,.etecsa.cu"
}
```

| Modo | Flags de Chrome |
| --- | --- |
| `direct` | `--no-proxy-server` |
| `pac` | `--proxy-pac-url=file:///…/proxy_empresa.pac` |
| `auto` | `--proxy-pac-url=file:///…/proxy_auto.pac` |
| `server` | `--proxy-server=http(s)://host:puerto` y `--proxy-bypass-list=…` |

El modo `server` exige `proxy`; el modo `pac` exige `pac_path`.

## 6. Filtros de publicación

Los filtros se normalizan con `xrepost_filters.normalize_spec()`:

| Campo | Tipo | Límite |
| --- | --- | --- |
| `include` | lista de términos | 200 caracteres por patrón |
| `exclude` | lista de términos | 200 caracteres por patrón |
| `include_regex` | expresión regular | 200 caracteres, sin construcciones peligrosas |
| `exclude_regex` | expresión regular | 200 caracteres |
| `lang` | lista de códigos | — |
| `media` | `""`, `yes`, `no` | — |
| `kind` | `""`, `original`, `reply`, `retweet` | — |
| `min_len`, `max_len` | enteros | 0–5000 |
| `exact` | booleano | — |

Los perfiles se guardan en `profiles.json` (máximo 100). Se pueden importar y
exportar en JSON.

## 7. Programación

`ScheduledStore` guarda:

```json
{
  "id": "…",
  "name": "Diario Cuba",
  "frequency": "daily",
  "run_at": "2026-11-19T08:00:00+00:00",
  "next_run": "2026-11-19T08:00:00+00:00",
  "enabled": true,
  "notify": true,
  "mode": "preview",
  "params": {"users": "@foo", "from": "...", "to": "..."}
}
```

- Frecuencias: `once`, `daily`, `weekly`, `monthly`.
- `mode` es siempre `preview`; no existe programación de `apply`.
- Mínimo 5 minutos entre ejecuciones.
- Máximo 50 programaciones.
- `--no-scheduler` desactiva el hilo de fondo.

## 8. Límites del panel

| Límite | Valor |
| --- | --- |
| Cuerpo HTTP | 1 MB |
| Historial devuelto | 200 eventos |
| Trabajos en memoria | 20 |
| Duración de un trabajo | 30 minutos |
| Sesión absoluta | 8 horas |
| Inactividad | 30 minutos |
| Fallos de autenticación | 8 por 5 minutos → 60 s de bloqueo |
| Bandeja | 5000 elementos |
| Grupos | 100 grupos, 500 miembros cada uno |
| Perfiles | 100 |

## 9. Configuración recomendada

- Usa `--token-file` en lugar de `--token`.
- Activa `--strict-cdp` en el CLI si el equipo es compartido.
- Mantén el panel en `127.0.0.1`.
- Programa solo previsualizaciones y revisa la bandeja antes de ejecutar.
- Haz backups periódicos y guárdalos fuera del equipo.
