# Instalación

## 1. Requisitos

| Componente | Versión probada | Obligatorio | Uso |
| --- | --- | --- | --- |
| Linux con sesión gráfica | — | Sí | El motor controla una ventana real de Chrome. |
| Python | 3.12.14 (probado también en 3.14.4) | Sí | CLI, motor y panel. |
| Google Chrome o Chromium | 153 | Sí | Navegador controlado por CDP. |
| `browser-use` (CLI y paquete) | 0.1.13 / 0.13.14 | Sí | Harness que ejecuta el motor. |
| `uv` | 0.12+ | Recomendado | Instala `browser-use` en un entorno aislado. |
| `pytest` | 8.x | Solo para pruebas | Suite automatizada. |
| `node` | 18+ | Solo para desarrollo | Validar la sintaxis de `app.js`. |

El proyecto no necesita React, Vue, Django, PostgreSQL, Redis, Docker ni
Kubernetes. Todo el estado son archivos JSON/JSONL.

> **Solo Linux.** La validación de fechas usa `date -d` de GNU coreutils y el
> bloqueo entre procesos usa `flock`/`fcntl`.

## 2. Instalación rápida (recomendada)

```bash
cd /ruta/a/x-repost-web

# 1. comprobar requisitos sin instalar nada
./iniciar.sh --check

# 2. arrancar Chrome + panel (idempotente)
./iniciar.sh
```

`iniciar.sh`:

1. Comprueba Python, Chrome, `browser-use` y el puerto.
2. Arranca Chrome con el perfil aislado de xrepost y `--remote-debugging-port=9222`.
3. Crea `panel-token` (0600) si no existe y escribe `panel-url` (0600) con el
   enlace de arranque.
4. Arranca `web/app.py` en `127.0.0.1:8765` sin volcar el token al log.
5. Abre el panel en el navegador (salvo `--no-open`).

Opciones:

```bash
./iniciar.sh --no-open    # no abre el navegador
./iniciar.sh --status     # estado de Chrome, panel y red
./iniciar.sh --stop       # detiene panel y Chrome del perfil
./iniciar.sh --check      # solo comprueba requisitos
```

Archivos de estado:

```
~/.local/state/xrepost/panel-token   token maestro (0600)
~/.local/state/xrepost/panel-url     enlace de arranque (0600)
~/.local/state/xrepost/panel.log     log del panel
```

Para abrir el panel manualmente:

```bash
cat ~/.local/state/xrepost/panel-url
```

## 3. Instalación manual

### 3.1 Python y Chrome

```bash
python3 --version          # debe ser 3.12 o superior
google-chrome --version    # o chromium --version
```

### 3.2 `browser-use`

```bash
uv tool install --python 3.12 browser-use
browser-use --version
browser-use --doctor
```

Si no usas `uv`, instala `browser-use` en un entorno virtual dedicado. No se
recomienda instalarlo en el Python del sistema.

### 3.3 Chrome con CDP

```bash
./xrepost-chrome.sh
```

El lanzador usa `~/.local/state/xrepost/chrome-profile` y el puerto 9222. Para
usar otro perfil:

```bash
XREPOST_CHROME_PROFILE=~/.config/xrepost-perfil ./xrepost-chrome.sh
```

### 3.4 Panel

```bash
python3 web/app.py --port 8765 --token-file ~/.local/state/xrepost/panel-token
```

o, sin archivo:

```bash
python3 web/app.py --port 8765
```

El panel imprime el enlace de arranque en la terminal. No lo compartas.

## 4. Primer uso

1. Abre Chrome en el perfil de xrepost e inicia sesión en X.
2. Abre el enlace del panel.
3. Comprueba la pestaña **Sistema**: motor, Chrome, CDP, historial y
   diagnóstico deben estar en verde.
4. Haz una búsqueda de prueba con una cuenta y un rango de fechas corto.
5. Revisa la bandeja y ejecuta solo si estás de acuerdo con la lista.

## 5. Copia portable

La carpeta `xrepost-portable/` contiene todo lo necesario para otro equipo:

```bash
cd xrepost-portable
./instalar.sh              # requisitos + acceso directo ejecutable
```

`instalar.sh` comprueba los requisitos (y solo instala lo que falta con
consentimiento explícito), deja los lanzadores ejecutables y crea **X-Repost**
en el escritorio y en el menú de aplicaciones, con el icono propio de la
carpeta. El acceso queda marcado como de confianza para que el doble clic
funcione. Para recrear solo el acceso, sin tocar dependencias:

```bash
./instalar.sh --no-deps
```

El lanzamiento directo (mismo comportamiento que el acceso) y el modo clásico
de terminal siguen disponibles:

```bash
./abrir-xrepost.sh         # X y el panel en dos pestañas
./start.sh                 # panel en ventana aparte
```

La copia se regenera desde el repositorio con:

```bash
./sync_portable.sh
./sync_portable.sh --check   # verifica que está sincronizada
```

## 6. Pruebas

```bash
python3 -m pytest -q
bash ./ci.sh
```

La suite no necesita Chrome ni credenciales: usa dobles locales para el motor.

## 7. Desinstalación

```bash
./iniciar.sh --stop
```

Después puedes borrar la carpeta del proyecto. Los datos de usuario están en
`~/.local/state/xrepost/`; bórralos solo si quieres eliminar el historial, los
perfiles y la sesión de Chrome. Haz antes un backup:

```bash
./xrepost.sh --backup
```

## 8. Problemas frecuentes

| Síntoma | Causa probable | Solución |
| --- | --- | --- |
| `401` al abrir el panel | Falta el token o caducó el enlace | Usa `panel-url` o reinicia `iniciar.sh`. |
| `403 Origen no permitido` | Abriste el panel desde otro host | Usa `127.0.0.1` o `localhost`, no la IP de la LAN. |
| `Chrome no responde` | Chrome cerrado o puerto ocupado | `./xrepost-chrome.sh --force` y revisa `--status`. |
| `No se encontró browser-use` | Falta el CLI | `uv tool install --python 3.12 browser-use`. |
| `La sesión de X caducó` | La sesión del perfil expiró | Inicia sesión en la ventana de Chrome de xrepost. |
| `CDP no es local` | `BU_CDP_URL` apunta a otra máquina | Usa `http://127.0.0.1:9222`. |
| El panel no arranca | Puerto 8765 ocupado | `XREPOST_PORT=8766 ./iniciar.sh`. |

## 9. Notas de seguridad

- No expongas el panel en la red: está pensado para loopback.
- No compartas `panel-url` ni `panel-token`.
- El perfil de Chrome contiene la sesión de X: trátalo como una credencial.
- Haz backups periódicos con `./xrepost.sh --backup`.
