# Configuración de red y proxy

Referencia: [`CONFIGURACION.md`](CONFIGURACION.md) · Arranque de Chrome:
[`CHROME_CDP.md`](CHROME_CDP.md)

## 1. Modos

| Modo | Flag de Chrome | Uso |
| --- | --- | --- |
| `direct` | `--no-proxy-server` | Sin proxy. |
| `pac` | `--proxy-pac-url=file:///…/proxy_empresa.pac` | PAC empresarial explícito. |
| `auto` | `--proxy-pac-url=file:///…/proxy_auto.pac` | PAC que decide con `dnsResolve`. |
| `server` | `--proxy-server=<scheme>://host:puerto` + bypass | Proxy fijo. |

Cambiar de modo **requiere relanzar Chrome**: CDP no permite modificar el proxy
en caliente de forma fiable. El panel ofrece `/api/network/restart`, que llama
a `xrepost-chrome.sh` y se bloquea si hay un trabajo en curso.

## 2. Persistencia

- Ruta por defecto: `~/.local/state/xrepost/network.json`.
- `XREPOST_NETWORK_CONFIG` permite usar otra ruta (pruebas y perfiles
  aislados).
- El directorio se crea con permisos restrictivos.
- La escritura es atómica: temporal en el mismo directorio y `os.replace`.
- Un JSON corrupto o un modo desconocido cae a `direct` al leer, sin
  sobrescribir el archivo hasta que el usuario guarde una configuración válida.

## 3. Validación

Al guardar (`save_config`) y al calcular los flags (`chrome_flags`) se valida:

- `proxy_scheme`: solo `http` o `https`.
- `proxy`: obligatorio en modo `server`, con formato `host:puerto`, sin
  esquema, credenciales, espacios, saltos de línea ni caracteres de control.
  Se admiten nombres DNS, IPv4 e IPv6 entre corchetes.
- Puerto: entero entre 1 y 65535.
- `bypass`: elementos separados por coma; cada uno con caracteres permitidos y
  sin empezar por `-` (evita inyectar flags de Chrome).
- `pac_path`: ruta absoluta, existente, con extensión `.pac`.
- `mode`: uno de `direct`, `pac`, `auto`, `server`.

La revalidación en `chrome_flags` es deliberada: `network.json` es un archivo
del usuario y podría haberse editado a mano. Un valor manipulado no debe
convertirse en argumentos adicionales de Chrome.

## 4. Credenciales

El formato aceptado **no admite** `user:pass@host`. Si una red exige
autenticación de proxy, debe resolverse en Chrome o en el PAC, no guardando
credenciales en `network.json` ni en la línea de comandos. Los mensajes de
error no incluyen el valor completo del proxy.

## 5. PAC

- `proxy_empresa.pac` y `proxy_auto.pac` viven en la raíz del repositorio.
- No se sobrescriben al cambiar de modo.
- El PAC automático usa `dnsResolve` para decidir; el empresarial contiene la
  regla explícita de `internet.etecsa.cu`.
- La ruta se convierte a URI `file://` y se pasa como un único argumento.

## 6. Uso desde la CLI

```bash
python3 xrepost_network.py get
python3 xrepost_network.py flags
python3 xrepost_network.py set direct
python3 xrepost_network.py set server --proxy proxy.ejemplo.cu:8080 --scheme http
python3 xrepost_network.py set pac --pac /ruta/proxy_empresa.pac
```

`xrepost-chrome.sh` lee `flags` línea por línea en un array; no usa `eval`.

## 7. Pruebas

`tests/test_network.py` cubre los cuatro modos, el rechazo de proxy vacío,
modo inválido, JSON roto, roundtrip, PACs reales, CLI `get/flags/set`, proxy
con esquema/credenciales/puerto inválido/saltos de línea, bypass con `-` o
separadores peligrosos, PAC relativo o inexistente y revalidación de una
configuración manipulada.
