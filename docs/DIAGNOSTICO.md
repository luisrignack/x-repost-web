# Diagnóstico

Referencia: [`CHROME_CDP.md`](CHROME_CDP.md) · [`RECUPERACION.md`](RECUPERACION.md) ·
API: [`API.md`](API.md)

## 1. Modo de solo lectura

`--diagnose` y la validación CDP **no publican nada**: no ejecutan reposts,
citas ni undo, no abren Chrome por su cuenta y no modifican el historial. Solo
leen archivos y consultan `/json/version` del Chrome que ya esté arriba.

## 2. CLI

```bash
./xrepost.sh --diagnose
./xrepost.sh --diagnose --strict-cdp
./xrepost.sh --stats --days 30
./iniciar.sh --check
./iniciar.sh --status
```

| Comando | Qué muestra |
| --- | --- |
| `--diagnose` | JSON con integridad del historial: eventos, corruptos, archivos y checksum. |
| `--strict-cdp` | Aborta si el endpoint CDP no es loopback o no pertenece al perfil dedicado. |
| `--stats` | Eventos confirmados, deshechos, fallos, desconocidos y tasa con denominador. |
| `iniciar.sh --check` | Python, `browser-use`, `curl`, lanzador, panel y estado. |
| `iniciar.sh --status` | Panel, CDP y preferencia de red. |

`--diagnose` no sustituye a `--strict-cdp`: el primero mira el historial; el
segundo, la identidad del navegador.

## 3. API del panel

| Endpoint | Contenido |
| --- | --- |
| `GET /api/health` | Estado mínimo del servicio. |
| `GET /api/cdp` | Informe de `xrepost_cdp.status()`. |
| `GET /api/history/diagnostic` | Diagnóstico del historial. |
| `GET /api/diagnostics` | Historial, CDP, motor, almacenamiento, sesiones y trabajos. |
| `GET /api/stats` | Estadísticas agregadas. |

`/api/diagnostics` devuelve, entre otros campos:

```json
{
  "history": {"total_events": 0, "corrupt_events": 0},
  "cdp": {"secure": true, "reachable": true, "problems": []},
  "engine": {"path": "…", "exists": true, "regular": true},
  "storage": {"state_dir": "…", "runs": "…", "journal_mode": "append-only"},
  "auth": {"sessions": 1},
  "jobs": {"runtime": 0, "persistent": 0}
}
```

## 4. Qué revisar cuando algo falla

1. **Panel no arranca** → `iniciar.sh --check` y el log
   `~/.local/state/xrepost/panel.log`.
2. **CDP no válido** → `GET /api/cdp`; comprobar que Chrome se lanzó con
   `xrepost-chrome.sh`, el puerto 9222 y el perfil dedicado.
3. **Historial corrupto** → `--diagnose`; si hay líneas inválidas, hacer
   `--backup` antes de tocar nada.
4. **Trabajo interrumpido** → revisar X y el estado `INTERRUPTED`; no repetir a
   ciegas.
5. **Proxy** → `python3 xrepost_network.py get` y `flags`; recordar que el
   cambio exige reiniciar Chrome.

## 5. Límites

- El diagnóstico no puede verificar el estado real de una publicación en X sin
  una sesión autenticada y una navegación real.
- No se muestra el token maestro ni el CSRF; solo el número de sesiones.
- Los logs del motor se recortan a las últimas 2.000 líneas en memoria.
