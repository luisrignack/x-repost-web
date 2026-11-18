# Cómo abrir la aplicación en cualquier situación

Guía práctica y autocontenida para arrancar **xrepost** en este equipo o en otro.
Complementa a [`README.md`](README.md) (referencia del motor/CLI),
[`web/README.md`](web/README.md) (panel) y
[`xrepost-portable/SETUP.md`](xrepost-portable/SETUP.md) (instalación en otra PC).

---

## 0. Decisión rápida

| Situación | Qué hacer |
|---|---|
| Ya hay un panel arriba y solo quieres usarlo | [§2](#2-el-panel-ya-est-arrancado) — abre la URL con token |
| Quieres la interfaz web desde cero | [§3](#3-arrancar-el-panel-web-solo) — `./web/run.sh` |
| El panel dice `chrome:false` o no encuentra posts | [§4](#4-arrancar-chrome-con-cdp-el-motor) — Chrome en el puerto 9222 |
| Quieres todo de una vez (Chrome + panel) | [§5](#5-todo-en-un-comando-portable) — `./xrepost-portable/start.sh` |
| No quieres interfaz, solo comandos | [§6](#6-cli-sin-panel) — `./xrepost.sh` |
| Es otra PC / no hay internet | [§7](#7-otra-pc-o-sin-internet) — carpeta `xrepost-portable/` |
| Algo no funciona | [§9](#9-resolucin-de-problemas) — tabla síntoma → causa → solución |
| **Es la primera vez / quieres empezar de cero** | **[§0.1](#01-desde-cero-paso-a-paso-primera-vez)** — 10 pasos ordenados |

**Idea clave:** son **dos piezas independientes**.

1. **Panel web** (`web/app.py`): servidor local en `127.0.0.1:8765` que muestra la UI y lanza el motor. Es lo que abres en el navegador.
2. **Motor** (`xrepost.sh` + `xrepost.py`): se ejecuta dentro del harness `browser-use` y controla tu **Chrome real** por CDP (puerto `9222`). Sin Chrome con CDP, el panel abre pero **no puede buscar ni repostear** (`/api/health` → `"chrome": false`).

---

## 0.1 Desde cero, paso a paso (primera vez)

Diez pasos en orden. Cada uno incluye **qué esperar**; si algo falla, salta a [§9](#9-resolucin-de-problemas).

### Paso 1 — Comprueba el entorno

```bash
uname -s                       # debe decir Linux
python3 --version              # 3.10 o superior
command -v google-chrome || command -v chromium
command -v uv || echo "FALTA uv"
```

Esperado: `Linux`, `Python 3.10+`, una ruta a Chrome, y `uv`. Si no hay `uv`, instálalo según tu distro o usa la vía portable de [§7](#7-otra-pc-o-sin-internet).

### Paso 2 — Instala el harness `browser-use` (solo una vez)

```bash
uv tool install --python 3.12 browser-use
export PATH="$HOME/.local/bin:$PATH"      # añade esta línea a ~/.bashrc
browser-use --version
browser-use --doctor
```

Esperado: `browser-use, version 0.1.13` y el doctor sin errores. **No hace falta ninguna clave de IA**; el motor no usa modelos.

### Paso 3 — Cierra TODAS las ventanas de Chrome

Guárdate el trabajo y ciérralas a mano. Es obligatorio: si queda una instancia, el siguiente comando solo dirá *"Opening in existing browser session."* e **ignorará** `--remote-debugging-port`.

Último recurso (cierra todo Chrome):

```bash
pkill -f '/opt/google/chrome/chrome' || true
```

### Paso 4 — Arranca Chrome con el puerto de control

Usa el lanzador del proyecto: **aplica automáticamente los flags de proxy** guardados en la preferencia de red.

```bash
cd ~/Downloads/x-repost-web
./xrepost-chrome.sh
curl -s http://127.0.0.1:9222/json/version | grep Browser
```

Esperado: una línea `"Browser": "Chrome/153.…"`. Si no aparece, revisa [§9](#9-resolucin-de-problemas) (Wayland/Vulkan o instancia previa).

Si prefieres el comando directo, añade los flags que imprime `python3 xrepost_network.py flags`. Ver [§4.1](#41-proxy-trabajo-vs-casa).

### Paso 5 — Inicia sesión en X en esa ventana

En la ventana de Chrome que acaba de abrirse, entra en X **una sola vez**. La sesión queda guardada en `~/.local/state/xrepost/chrome-profile` y se reutiliza. Comprueba que ves tu timeline al recargar.

### Paso 6 — Arranca el panel web

```bash
cd ~/Downloads/x-repost-web
nohup python3 -u web/app.py --no-open > /var/tmp/xrepost-panel.log 2>&1 &
sleep 3
grep 'Panel:' /var/tmp/xrepost-panel.log
```

Esperado: `Panel: http://127.0.0.1:8765/?token=…`. Ese token es aleatorio y cambia en cada arranque.

### Paso 7 — Abre la interfaz

Copia la URL completa del paso 6 y pégala en el navegador. Verás el formulario de cuentas/fechas. Si Sale `No autorizado.`, falta el `?token=…`.

### Paso 8 — Comprueba que las dos piezas están vivas

```bash
TOKEN=$(grep -oE 'token=[A-Za-z0-9_-]+' /var/tmp/xrepost-panel.log | head -1 | cut -d= -f2)
curl -s -H "Cookie: xrepost_token=$TOKEN" http://127.0.0.1:8765/api/health
```

Esperado: `{"ok": true, "engine_ok": true, "chrome": true, "busy": false}`.
- `engine_ok:false` → ruta al motor equivocada.
- `chrome:false` → vuelve al **paso 3** y al **paso 4**.

### Paso 9 — Haz una prueba SIN publicar

En el panel: escribe una cuenta pública (p. ej. `kubernetesio`), rango de fechas reciente y pulsa **Previsualizar**. Verás autor, fecha, texto y enlace. **No pulses Repostear todavía**: es modo dry-run y no se publica nada.

Equivalente por CLI:

```bash
cd ~/Downloads/x-repost-web
./xrepost.sh kubernetesio 01/11/2026 15/11/2026     # sin X_APPLY = solo lista
```

### Paso 10 — Verificación final

```bash
python3 -m pytest -q          # 77 passed + 18 subtests
tail -3 ~/.local/state/xrepost/history.jsonl
./ci.sh                       # opcional: guardas extra
```

Ya está listo. Para **publicar de verdad**: marca los posts en el panel y pulsa Repostear (confirmación + retardo ≥5 s), o usa `X_APPLY=1 ./xrepost.sh …` en CLI. Al terminar, `Ctrl-C` en la terminal del panel lo detiene; Chrome queda abierto con tu sesión.

---

## 1. Requisitos (una sola vez)

| Pieza | Versión conocida | Para qué |
|---|---|---|
| Linux con escritorio | — | `date -d` GNU y `flock`/`fcntl`; macOS/Windows no soportados |
| Python | 3.10+ (solo stdlib) | panel y módulos compartidos |
| Google Chrome / Chromium | 153 | navegador que controla el motor |
| `browser-use` (CLI) | 0.1.13 | harness que habla CDP |
| `uv` | 0.12+ | instala el CLI en entorno aislado |
| `pytest` (opcional) | 9.x | correr las pruebas |

Instalación del CLI:

```bash
uv tool install --python 3.12 browser-use
export PATH="$HOME/.local/bin:$PATH"      # añádelo a tu ~/.bashrc si hace falta
browser-use --version
browser-use --doctor
```

No hace falta ninguna clave de API de IA: el motor es automatización determinista del DOM.

---

## 2. El panel ya está arrancado

Comprueba si hay algo escuchando:

```bash
ss -ltnp | grep 8765 || echo "no hay panel"
curl -s --max-time 2 http://127.0.0.1:8765/api/health
# Sin token responde {"error":"No autorizado."} → el panel SÍ está vivo
```

Para obtener la URL con el token, busca el último arranque:

```bash
grep -h 'Panel:' ~/.local/state/xrepost/panel.log /var/tmp/xrepost-panel.log 2>/dev/null | tail -1
```

Abre esa URL (ejemplo): `http://127.0.0.1:8765/?token=<token-aleatorio>`.

> El token **cambia en cada arranque**. El fichero `panel-url.txt` (ignorado por git) ya no guarda un token fijo: solo explica dónde está. No uses la vieja URL con `?token=xrepost-local`.

Comprueba que el motor pueda trabajar:

```bash
TOKEN="$(grep -oE 'token=[A-Za-z0-9_-]+' ~/.local/state/xrepost/panel.log /var/tmp/xrepost-panel.log 2>/dev/null | tail -1 | cut -d= -f2)"
curl -s -H "Cookie: xrepost_token=$TOKEN" http://127.0.0.1:8765/api/health
```

- `"chrome": true` → listo para previsualizar.
- `"chrome": false` → ve a [§4](#4-arrancar-chrome-con-cdp-el-motor).

---

## 3. Arrancar el panel web (solo)

Desde la raíz del repositorio:

```bash
cd ~/Downloads/x-repost-web
./web/run.sh                       # equivalente: python3 web/app.py
```

La terminal imprime algo como:

```
  xrepost · panel local
  Panel:     http://127.0.0.1:8765/?token=1uttlYxjUQAIzuXU5zpyf6dj
  Motor:     .../xrepost.sh
  ...
```

Opciones útiles:

```bash
python3 web/app.py --port 0            # puerto aleatorio
python3 web/app.py --port 8766         # si 8765 está ocupado
python3 web/app.py --no-open           # no abrir navegador automáticamente
python3 web/app.py --verbose           # registrar cada petición HTTP
python3 web/app.py --token fijo        # NO recomendado: token adivinable
```

Por defecto escucha **solo en `127.0.0.1`** (`--host`). No lo expongas a la red: la seguridad depende del token y de las comprobaciones Host/Origin.

Para detenerlo: `Ctrl-C`, o `pkill -f 'python3 -u app.py --no-open'` si lo dejaste en segundo plano.

Si quieres dejarlo corriendo en background y recuperar la URL después:

```bash
cd ~/Downloads/x-repost-web/web
nohup python3 -u app.py --no-open > /var/tmp/xrepost-panel.log 2>&1 &
sleep 3; grep 'Panel:' /var/tmp/xrepost-panel.log
```

---

## 4. Arrancar Chrome con CDP (el motor)

Chrome 136+ bloquea el debugging remoto en el perfil por defecto, así que se usa un **perfil dedicado**.

```bash
# 1) CIERRA TODAS las ventanas de Chrome antes de continuar.
#    Si queda una instancia abierta, el comando siguiente solo dice
#    "Opening in existing browser session." e IGNORA --remote-debugging-port.

# 2) Arranca Chrome con el perfil y el puerto de control:
google-chrome --user-data-dir="$HOME/.local/state/xrepost/chrome-profile" \
              --remote-debugging-port=9222 \
              --no-first-run --no-default-browser-check \
              https://x.com/ &

# 3) Inicia sesión en X UNA VEZ en esa ventana. La sesión queda guardada en el perfil.

# 4) Verifica:
curl -s http://127.0.0.1:9222/json/version | grep Browser
ss -ltnp | grep 9222
```

Si Chrome se queja de Wayland/Vulkan, añade `--ozone-platform=x11 --disable-gpu --no-sandbox`.

Cada ejecución abre **su propia pestaña** en esa ventana (`about:blank`), navega solo ahí y la cierra al terminar: tus pestañas no se mueven. El panel se abre en una **ventana de Chrome distinta** (perfil `~/.cache/xrepost-web/panel-profile`, sin CDP), así que el motor nunca puede llevarse la UI por delante.

El panel debe pasar a `"chrome": true` (recarga la página si hace falta).

---

## 4.1 Proxy: trabajo vs casa

El proxy se fija **al arrancar Chrome**: no se puede cambiar en caliente desde CDP.
Por eso el panel tiene un selector **Red** en la barra superior:

| Modo | Cuándo | Flags que aplica |
|---|---|---|
| **Casa · sin proxy** | sin proxy (o proxy transparente) | `--no-proxy-server` |
| **Empresa · PAC** | red corporativa con tu PAC | `--proxy-pac-url=file:///.../proxy_empresa.pac` |
| **Automático · PAC** | quieres que decida el DNS | `--proxy-pac-url=file:///.../proxy_auto.pac` |
| **Empresa · servidor** | proxy HTTP/HTTPS explícito | `--proxy-server=<scheme>://host:puerto` + bypass |

**Para cambiar de red:** elige el modo → **Aplicar** → confirma. El panel guarda la preferencia en `~/.local/state/xrepost/network.json`, **cierra solo el Chrome del perfil dedicado** y lo relanza con los flags nuevos. Se avisa antes porque se cierran las pestañas de ese perfil. Si hay una ejecución en curso, el botón responde `409` y no reinicia nada.

Sin panel (CLI):

```bash
python3 xrepost_network.py set direct
python3 xrepost_network.py set pac
python3 xrepost_network.py set auto
python3 xrepost_network.py set server --proxy internet.etecsa.cu:3128 --scheme http
python3 xrepost_network.py flags          # comprueba los flags resultantes
./xrepost-chrome.sh --force               # reinicia Chrome aplicando el cambio
```

> **Importante sobre tu PAC:** `HTTPS internet.etecsa.cu` implica CONNECT TLS al **puerto 443**. Si tu proxy es en realidad HTTP en `3128`, usa el modo **Empresa · servidor** con esquema `http` y `internet.etecsa.cu:3128` (el bypass ya trae los dominios internos). El modo `Auto` usa `dnsResolve("internet.etecsa.cu")`: si ese nombre resuelve desde casa (VPN/DNS público), seguirá usando el proxy. Valídalo en ambos entornos.

`xrepost-portable/start.sh` también lee esta preferencia, así que en la otra PC basta con copiar `network.json` junto con el resto del estado.

---

## 5. Todo en un comando (portable)

`start.sh` comprueba requisitos (con consentimiento), abre Chrome con CDP si no está activo, y levanta el panel:

```bash
cd ~/Downloads/x-repost-web
./xrepost-portable/start.sh
```

Variables opcionales:

| Variable | Por defecto | Uso |
|---|---|---|
| `XREPOST_PORT` | `8765` (respaldo 8766-8769) | puerto del panel |
| `BU_CDP_URL` | `http://127.0.0.1:9222` | endpoint CDP |
| `XREPOST_CHROME_PROFILE` | `~/.local/state/xrepost/chrome-profile` | perfil del motor |

Si ya tienes un panel en 8765:

```bash
XREPOST_PORT=8766 ./xrepost-portable/start.sh
```

Al salir con `Ctrl-C` se detiene el panel; Chrome queda abierto con tu sesión de X.

---

## 6. CLI (sin panel)

```bash
cd ~/Downloads/x-repost-web

./xrepost.sh                                         # interactivo: cuentas, fechas, alcance
./xrepost.sh kubernetesio 01/11/2026 15/11/2026      # DRY-RUN: solo lista
X_APPLY=1 ./xrepost.sh kubernetesio 01/11/2026       # repostea de verdad
X_APPLY=1 X_LIMIT=5 X_DELAY=30 ./xrepost.sh foo 01/11/2026 --quote "#ETECSA"
./xrepost.sh --history 20                            # últimas 20 acciones
./xrepost.sh --undo-last                             # deshacer última tanda
./xrepost.sh --undo-last 3                           # últimos 3 reposts
./xrepost.sh --undo https://x.com/foo/status/123     # deshacer uno
```

**Por defecto no se publica nada.** Hace falta `X_APPLY=1` en CLI o el diálogo de confirmación del panel (con retardo mínimo de 5 s). Solo se permite **una ejecución a la vez** (bloqueo por fichero); el historial evita repetir posts (`--force` lo ignora).

Variables principales: `X_USERS`, `X_FROM`, `X_TO`, `X_MATCH`, `X_EXCLUDE`, `X_SKIP_REPLIES`, `X_SKIP_RETWEETS`, `X_LIMIT`, `X_DELAY`, `X_APPLY`, `X_QUOTE`, `X_HISTORY`, `X_ACCOUNTS`, `X_HASHTAGS`.

---

## 7. Otra PC o sin internet

La carpeta **`xrepost-portable/`** es autocontenida: motor, panel, tests, `start.sh` y guía. No depende del repo ni del worktree.

```bash
# En la PC de destino (copiar la carpeta, p. ej. con USB):
cd xrepost-portable
cat SETUP.md                # guía completa
./install-deps.sh           # comprueba e instala solo tras confirmación
./start.sh                  # Chrome CDP + panel
```

El panel y el motor funcionan sin internet salvo para llegar a X. No hay llamadas a proveedores de IA ni telemetría de la librería agente (no se usa).

---

## 8. Flujo normal de uso en el panel

1. Abre la URL con token.
2. Escribe cuentas (separadas por coma; autocompletado de las recordadas) y fechas `DD/MM/AAAA` (8 dígitos, barras automáticas).
3. Elige alcance: solo originales (default) o incluir retweets de otras cuentas.
4. **Previsualizar** → revisa la lista; puedes filtrar, ordenar y marcar solo los posts que quieras.
5. **Repostear** → confirmación con número exacto y duración estimada; barra de progreso y estado por fila.
6. Pestaña **Historial**: todas las acciones (incluido el comentario de la cita) y botón **Deshacer** (uno, última tanda o últimos N).

Las cuentas y hashtags recordados se borran con la papelera junto a cada campo (pide confirmación). El historial se mantiene en `~/.local/state/xrepost/history.jsonl`.

---

## 9. Resolución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| `{"error":"No autorizado."}` al abrir | Falta el token en la URL/cookie | Copia la URL completa que imprime el panel; `grep 'Panel:'` en el log |
| `No se pudo conectar` | Panel caído o puerto distinto | [§3](#3-arrancar-el-panel-web-solo); comprueba `ss -ltnp \| grep 8765` |
| `OSError: [Errno 98] Address already in use` | Ya hay un panel en 8765 | Úsalo ([§2](#2-el-panel-ya-est-arrancado)) o `--port 8766` |
| `/api/health` → `"chrome": false` | Chrome sin CDP | [§4](#4-arrancar-chrome-con-cdp-el-motor) |
| `Opening in existing browser session.` y CDP no abre | Hay otro Chrome abierto; el wrapper ignora los flags | **Cierra todas las ventanas de Chrome** y relanza con `--user-data-dir` y `--remote-debugging-port` |
| `vaInitialize failed` / error Wayland/Vulkan | GPU del portátil | Añade `--ozone-platform=x11 --disable-gpu --no-sandbox` |
| `browser-use: command not found` | PATH sin `~/.local/bin` | `export PATH="$HOME/.local/bin:$PATH"` y `uv tool install --python 3.12 browser-use` |
| "No hay resultados" en la búsqueda | Sesión de X caducada en el perfil CDP | Abre `https://x.com/` en esa ventana e inicia sesión |
| `429` / "Demasiadas solicitudes" | X limita la frecuencia | Sube `X_DELAY` (p. ej. 30) y baja `X_LIMIT` |
| La UI da 403 "Host/Origen no permitido" | Abierta vía `file://`, IP o proxy | Usa siempre `http://127.0.0.1:8765/...` en el mismo equipo |
| Cita no confirmada (`quote_unverified`) | X no mostró el toast de confirmación | No se marca como hecha: **reintenta**; no es un fallo del historial |
| Token perdido | Se regenera en cada arranque | `grep 'Panel:'` en el log; si no, reinicia el panel |
| En el trabajo no carga X; en casa sí | Falta el proxy corporativo | Selector **Red** → modo Empresa (PAC o servidor) → Aplicar |
| Con el modo PAC sigue sin cargar | `HTTPS host` apunta a 443 y tu proxy puede ser HTTP 3128 | Usa modo **Empresa · servidor**, esquema `http`, `internet.etecsa.cu:3128` |
| "Hay una ejecución en curso" al aplicar red | Job activo | Espera a que termine y vuelve a Aplicar |
| El cambio de red no surte efecto | Chrome ya estaba abierto y no se reinició | Pulsa **Aplicar** (reinicia) o `./xrepost-chrome.sh --force` |
| Tests fallan | Entorno equivocado | `./ci.sh` desde la raíz (usa `tests/` y `web/`, no el portable) |

---

## 10. Verificación rápida

```bash
cd ~/Downloads/x-repost-web

python3 -m pytest -q          # 77 passed + 18 subtests (sin Chrome ni red)
./ci.sh                       # + sintaxis, portable y módulos trackeados
node --check web/static/app.js

ss -ltnp | grep 8765          # panel
ss -ltnp | grep 9222          # CDP del motor
curl -s http://127.0.0.1:9222/json/version | head -c 120
```

---

## 11. Dónde están los datos

| Dato | Ruta |
|---|---|
| Historial | `~/.local/state/xrepost/history.jsonl` (`X_HISTORY`) |
| Cuentas recordadas | `~/.local/state/xrepost/accounts.json` (`X_ACCOUNTS`) |
| Hashtags recordados | `~/.local/state/xrepost/hashtags.json` (`X_HASHTAGS`) |
| Perfil de Chrome del motor | `~/.local/state/xrepost/chrome-profile` |
| Perfil de Chrome del panel | `~/.cache/xrepost-web/panel-profile` |
| Exportaciones y logs del panel | `web/.runs/<job-id>/` |

---

*Guía verificada el 2026-11-18 contra el código de las ramas `web-ui` / `main`. Si cambias puerto, perfil o variables, actualiza este documento en el mismo commit.*
