# Seguridad

Este documento describe los controles implementados en el panel y en el motor,
cómo usarlos y qué límites tienen. Las decisiones de diseño se justifican en
`MODELO_DE_AMENAZAS.md`.

## 1. Modelo de autenticación

El panel escucha en `127.0.0.1` y usa dos credenciales distintas:

| Credencial | Formato | Uso | Caducidad |
| --- | --- | --- | --- |
| Token maestro | 32 bytes aleatorios (o `--token`) | Crear una sesión o autenticar clientes de línea de comandos con `X-Token`. | Mientras viva el proceso. |
| Sesión | Cookie `xrepost_sid` `HttpOnly` + `SameSite=Strict` | Navegar por el panel y ejecutar acciones. | 8 h absolutas y 30 min de inactividad. |
| CSRF | Valor devuelto por `GET /api/session` | Cabecera `X-CSRF-Token` en toda escritura con cookie. | Igual que la sesión; se renueva al rotar. |

### Flujo del navegador

1. `iniciar.sh` genera el token maestro (o lo reutiliza de `panel-token`,
   0600). El panel genera además un **token de arranque** independiente y
   escribe la URL en `panel-url` (0600).
2. Al abrir `http://127.0.0.1:8765/?token=…`, el servidor consume ese token de
   arranque (un solo uso), crea una sesión y responde `303` con la cookie
   `xrepost_sid`. El token maestro nunca viaja en la URL y reutilizar el enlace
   devuelve `401`.
3. El token desaparece de la barra de direcciones. La cookie **no** sirve para
   escribir por sí sola: `app.js` pide `GET /api/session`, guarda el CSRF en
   memoria y lo envía en cada `POST`, `PATCH` o `DELETE`.

### Flujo de línea de comandos

`curl -H "X-Token: …"` sigue funcionando. Una cabecera personalizada no se
puede enviar desde otro origen sin un preflight CORS que el servidor no
concede, por lo que `X-Token` no necesita CSRF. Las lecturas y escrituras
aceptan esta forma.

### Cookie heredada

La cookie `xrepost_token` **ya no se emite** al canjear el enlace de arranque.
Si un cliente antiguo la conserva, se acepta solo para lectura: una petición
autenticada únicamente por esa cookie **no puede escribir** y debe enviar
`X-Token` o disponer de una sesión con CSRF. Está previsto retirar también su
aceptación en una versión futura.

## 2. CSRF y validación de origen

Cada escritura pasa por este orden:

1. `Host` debe ser `127.0.0.1`, `localhost` o `::1`, y el puerto debe coincidir
   con el del servidor.
2. `Origin`, si está presente, debe coincidir exactamente con el `Host`
   (esquema `http`, mismo host y puerto, sin credenciales) y `Sec-Fetch-Site`
   no puede ser `cross-site` ni `same-site`.
3. Se resuelve el tipo de autenticación: `header` (`X-Token`), `session`
   (cookie válida) o `cookie` (heredada, solo lectura).
4. Con `session`, `X-CSRF-Token` debe coincidir con el de la sesión mediante
   `hmac.compare_digest`; además una escritura con cookie exige `Origin` o
   `Sec-Fetch-Site` (su ausencia solo se tolera a clientes con `X-Token`).
5. Solo entonces se lee el cuerpo JSON (máximo 1 MB, `application/json`
   obligatorio).

Si una petición se rechaza antes de leer el cuerpo, la conexión se cierra para
evitar que los bytes pendientes se interpreten como la petición siguiente.

## 3. Sesiones

- Identificador y CSRF generados con `secrets.token_urlsafe(32)`.
- Caducidad absoluta y por inactividad; `GET /api/session` renueva la de
  inactividad.
- `POST /api/session/rotate` invalida la sesión anterior y crea otra (defensa
  contra fijación de sesión).
- `POST /api/session/logout` revoca la sesión y borra la cookie.
- Las sesiones viven solo en memoria: reiniciar el panel las invalida todas.
- `describe()` expone `expires_in`, `idle_expires_in` y `rotations` sin revelar
  el token maestro.

## 4. Fuerza bruta

`xrepost_security.AuthManager` aplica un límite por IP:

- 8 fallos dentro de una ventana de 5 minutos bloquean 60 segundos.
- El bloqueo se consulta antes de validar el token y antes de crear sesión.
- Un acierto limpia el contador.
- El cliente se identifica por `client_address[0]`; el servidor solo escucha en
  loopback, por lo que no se confía en `X-Forwarded-For`.

## 5. Cabeceras de seguridad

Todas las respuestas incluyen:

```
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
X-Frame-Options: DENY
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Resource-Policy: same-origin
Permissions-Policy: geolocation=(), camera=(), microphone=(), payment=(), usb=()
```

Las páginas y los recursos estáticos añaden una CSP:

```
default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self';
img-src 'self' data:; font-src 'self' data:; connect-src 'self';
object-src 'none'; base-uri 'none'; form-action 'self';
frame-ancestors 'none'; worker-src 'none'
```

`style-src 'unsafe-inline'` es necesario para los estilos calculados de la
interfaz (barras de progreso y gráficos). No se permite JavaScript inline.

## 6. Protección del CDP

Chrome expone un puerto de depuración que equivale al control total del
navegador. `xrepost_cdp.py` valida cada endpoint antes de usarlo:

- Esquema `http` (se rechazan `https`, `ws`, `file` y similares).
- Sin usuario ni contraseña en la URL.
- Ruta vacía o `/`; sin query ni fragmento.
- Host loopback (`127.0.0.0/8`, `localhost`, `::1`).
- Puerto explícito y en rango válido.
- `quick_available()` comprueba `/json/version` con un tiempo de espera corto.

`xrepost.sh --strict-cdp` exige además que el endpoint sea local y que el
perfil de Chrome sea el de xrepost (`~/.local/state/xrepost/chrome-profile` o
`XREPOST_CHROME_PROFILE`). El panel revalida el endpoint en cada trabajo.

## 7. Subprocesos

El motor se lanza con una lista de argumentos, nunca con `shell=True`.

- `cwd` es el directorio del proyecto.
- El entorno se construye con una lista blanca: `PATH`, `HOME`, `LANG`,
  `XDG_*`, `DISPLAY`, etc., más los prefijos `XREPOST_`, `BU_` y `STUB_`.
- No se heredan `X_*` del servidor, salvo los que el propio panel construye
  para el trabajo.
- Cada trabajo abre su propio grupo de procesos (`start_new_session=True`) y
  la cancelación envía `SIGTERM` al grupo y, tras una espera, `SIGKILL`.
- La salida se captura en un archivo dentro de `web/.runs/<id>/` con permisos
  privados.

## 8. Archivos y permisos

`xrepost_fs.py` centraliza el acceso:

- Directorios `0700`, archivos `0600`.
- Escritura atómica: temporal en el mismo directorio, `fsync`, `os.replace`,
  `fsync` del directorio.
- Lectura con límite de tamaño (8 MB por defecto en documentos de estado).
- Rechazo de enlaces simbólicos en lectura y escritura.
- `safe_join()` y `remove_tree()` comprueban que la ruta está dentro de la base.
- Los backups se verifican con SHA-256 antes de restaurar.

Rutas sensibles:

| Ruta | Contenido | Permisos |
| --- | --- | --- |
| `~/.local/state/xrepost/panel-token` | Token maestro | 0600 |
| `~/.local/state/xrepost/panel-url` | Enlace de arranque con token | 0600 |
| `~/.local/state/xrepost/history.jsonl` | Historial | 0600 |
| `~/.local/state/xrepost/*.json` | Perfiles, grupos, bandeja, programación | 0600 |
| `web/.runs/` | Ejecuciones y exportaciones | 0700 |

## 9. Validación de entradas

- Fechas: `AAAA-MM-DD` o `DD/MM/AAAA`, con validación de calendario y rango.
- Usuarios: `[A-Za-z0-9_]{1,15}`.
- URL de estado: solo `x.com`/`twitter.com` con `/status/<id>`.
- Filtros: longitud máxima, listas acotadas y expresiones regulares con
  protecciones contra retroceso catastrófico (`xrepost_filters.compile_safe`).
- Cuerpo JSON: objeto, tamaño máximo y tipo de contenido.
- Exportaciones: CSV neutraliza fórmulas (`=`, `+`, `-`, `@`), HTML escapa
  todo y Markdown escapa tablas. Las URLs solo se enlazan si son `http(s)`.

## 10. Registro y secretos

- El token no se escribe en el log del panel: `iniciar.sh` usa `--token-file`.
- `--verbose` registra método, ruta y estado, nunca cabeceras ni cuerpos.
- Los parámetros persistidos de un trabajo se filtran con
  `xrepost_jobs.sanitize_params()`: se eliminan `token`, `csrf`, `password`,
  `secret`, `confirm`, `only_urls_file` y claves que empiezan por `_`.
- Los errores internos se registran con traza en el log y se devuelve un
  mensaje genérico al cliente.

## 11. Lista de comprobación antes de publicar

```bash
python3 -m pytest -q
bash ./ci.sh
node --check web/static/app.js
```

Comprobaciones manuales recomendadas:

- Abrir el panel sin token: debe mostrar 401 y no filtrar datos.
- Intentar un `POST` con cookie pero sin `X-CSRF-Token`: debe devolver 403.
- Enviar `Origin: http://evil.example`: debe devolver 403.
- Enviar `Host: evil.example`: debe devolver 403.
- Escritura con cookie válida y CSRF correcto pero sin `Origin` ni
  `Sec-Fetch-Site`: debe devolver 403.
- Escritura con `Sec-Fetch-Site: cross-site`: debe devolver 403.
- Ejecutar `xrepost.sh --strict-cdp` con un CDP remoto: debe rechazarlo.

## 12. Escaneo de secretos y dependencias

- `gitleaks` se ejecuta en CI sobre el árbol de trabajo (`--no-git`) y no debe
  encontrar nada. El historial de git contiene un token de ejemplo de una
  ejecución local en el commit `10d3896`; ya no es válido, pero un escaneo con
  historial lo marcaría hasta que se purifique la rama.
- `pip-audit` audita `requirements.txt`, que no declara dependencias de
  ejecución: la aplicación usa solo la biblioteca estándar.
- `bandit -ll` se ejecuta sin hallazgos medium/high. Los avisos low son
  `try/except pass` deliberados en cierres de recursos.
- Los ejemplos de la documentación usan `<token-aleatorio>`, nunca un token
  real.

## 13. Limitaciones conocidas

- El panel no implementa TLS: es exclusivamente local.
- No hay autenticación multifactor; el token maestro es la única credencial.
- Si el equipo está comprometido, el atacante puede leer el token del archivo
  o el perfil de Chrome. Los controles protegen frente a otros orígenes web,
  errores de configuración y procesos no confiables, no frente a un usuario
  local malicioso con los mismos permisos.
- `browser-use` y Chrome son dependencias externas fuera del perímetro de la
  aplicación.
