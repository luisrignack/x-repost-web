# Chrome y CDP

Referencia: [`SEGURIDAD.md`](SEGURIDAD.md) · Arranque:
[`INSTALACION.md`](INSTALACION.md) · Motor: [`MOTOR_X.md`](MOTOR_X.md)

## 1. Por qué se valida el endpoint

CDP da control total sobre una sesión autenticada de X. Aceptar una URL
arbitraria permitiría dirigir el motor a un Chrome remoto, a un puerto de otro
programa o a un perfil personal. Por eso `xrepost_cdp.py` valida antes de cada
operación que actúa sobre X.

## 2. Reglas de la URL

| Regla | Ejemplo válido | Ejemplo rechazado |
| --- | --- | --- |
| Esquema `http` | `http://127.0.0.1:9222` | `https://…` |
| Host de loopback literal | `127.0.0.1`, `::1`, `localhost` | `10.0.0.5`, `example.com` |
| Puerto explícito y en rango | `:9222` | sin puerto, `:0`, `:99999` |
| Sin credenciales | — | `http://user:pass@127.0.0.1:9222` |
| Sin ruta ni query | — | `http://127.0.0.1:9222/x?y=1` |

`parse_endpoint()` devuelve la lista de problemas; `status()` la convierte en
un informe con `secure` y `reachable`. `require_ready()` lanza
`CdpSecurityError` y bloquea la operación si algo no cuadra.

## 3. Identidad del navegador

Además de la URL se comprueba:

1. `/json/version` responde y se identifica como Chrome/Chromium.
2. El `webSocketDebuggerUrl` anunciado también apunta a loopback y al mismo
   puerto.
3. El puerto escucha solo en direcciones de loopback (`/proc/net/tcp`).
4. Existe **un solo** proceso Chrome con
   `--remote-debugging-port=<puerto>` y el `--user-data-dir` esperado.
5. Ese perfil no es el perfil personal habitual de Chrome.

Si hay dos procesos, un perfil distinto o una ruta parecida, se rechaza. No se
comparan argumentos por coincidencia parcial de texto: se comparan rutas
normalizadas y argumentos completos.

## 4. Perfil dedicado

- Ruta por defecto: `~/.local/state/xrepost/chrome-profile`.
- `XREPOST_CHROME_PROFILE` permite cambiarla de forma explícita.
- `XREPOST_CHROME_PROFILE` no puede apuntar al perfil personal.
- El perfil se crea con permisos restrictivos y no se borra al cerrar.

`xrepost-chrome.sh` es el único lanzador soportado. Detecta una instancia
existente, reutiliza el perfil dedicado, limpia locks solo cuando el proceso
correspondiente ya no existe y no mata Chrome de otros perfiles.

## 5. Modo estricto y diagnóstico

- `--strict-cdp` exige que la validación completa pase; si no, la CLI aborta
  antes de buscar o publicar.
- `--diagnose` imprime el informe de CDP, perfil, sesión y selectores sin
  ejecutar reposts, citas ni undo.
- `iniciar.sh --check` comprueba Python, `browser-use`, `curl`, el lanzador y el
  panel; `--status` muestra panel, CDP y preferencia de red.

## 6. Pruebas

`tests/test_core_modules.py::CdpSecurityTest` cubre:

- URL válida, remota, con credenciales, con ruta y con puerto inválido.
- `/json/version` válido, navegador que no es Chrome, websocket a otro host y
  JSON vacío.
- Servidor local simulado (sin Chrome real) y puerto cerrado.
- Informe `status()` con puerto no loopback, dos procesos, perfil ajeno y
  ausencia de `--user-data-dir`.
- `require_ready()` bloqueando endpoints inseguros.
- `quick_available()` y valores por defecto del perfil.

## 7. Limitaciones

- No se puede verificar la sesión de X sin abrir Chrome; eso queda para la
  prueba manual.
- Un Chrome comprometido por un tercero queda fuera del modelo de amenazas.
- La comprobación de procesos usa `/proc`, por lo que está pensada para Linux.
