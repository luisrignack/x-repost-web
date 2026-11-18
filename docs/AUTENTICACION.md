# Autenticación y sesiones

Referencia: [`SEGURIDAD.md`](SEGURIDAD.md) · Modelo de amenazas:
[`MODELO_DE_AMENAZAS.md`](MODELO_DE_AMENAZAS.md)

## 1. Dos secretos distintos

| Secreto | Dónde vive | Para qué sirve | Caducidad |
| --- | --- | --- | --- |
| Token maestro | Archivo `panel-token` con permisos `0600` en el directorio de estado | Autenticar clientes de CLI mediante `X-Token` | Hasta que se regenera |
| Token de arranque | Memoria del panel; su URL se escribe en `panel-url` (`0600`) | Canjearlo **una sola vez** por una cookie de sesión | Un uso |
| Sesión (`sid` + `csrf`) | Memoria del panel y cookie `HttpOnly` | Autenticar peticiones y proteger escrituras | 8 h absolutas, 30 min de inactividad |

El token maestro **no viaja en la URL** ni se escribe en el log. `iniciar.sh`
escribe un enlace con el token de arranque en `panel-url` (`0600`); al abrirlo,
el panel lo canjea por una cookie y redirige a `/`. El token de arranque queda
invalidado en ese mismo instante: reutilizarlo devuelve 401.

## 2. Flujo del navegador

1. `iniciar.sh` genera el token maestro si no existe y arranca `web/app.py`
   con `--token-file` y `--bootstrap-file`.
2. El panel genera un token de arranque aleatorio **independiente** del maestro
   y escribe la URL en el archivo de bootstrap.
3. El navegador abre `/?token=…`; el panel valida y consume el token, crea una
   sesión y responde con
   `Set-Cookie: xrepost_sid=…; HttpOnly; SameSite=Strict; Path=/`.
4. El token de arranque queda usado. Una segunda petición con la misma URL
   devuelve 401; no se emite ninguna cookie con el token maestro.
5. Cada escritura exige `X-CSRF-Token` con el valor ligado a la sesión.

## 3. Flujo de línea de comandos

Los clientes de CLI pueden enviar el token maestro en `X-Token` para crear una
sesión. También se acepta la cookie de sesión. El token maestro nunca se
registra; si se pasa por variable de entorno, el proceso debe ser del usuario.

## 4. CSRF

- El token CSRF se genera con `secrets.token_urlsafe(32)` por sesión.
- Se exige en `POST`/`PUT`/`DELETE` que modifiquen estado.
- Se valida `Host` exacto contra el puerto de escucha, `Origin` exacto
  (`http://127.0.0.1:8765` o `http://localhost:8765`), `Sec-Fetch-Site` cuando
  está presente y `Content-Type` JSON.
- Un `POST` sin `Origin` **no** se acepta como si fuera local: la ausencia de
  cabeceras solo se tolera en el canje inicial del token, no en escrituras.

## 5. Sesiones

- `sid` y `csrf` son aleatorios; no se derivan del token maestro.
- Caducidad absoluta (`DEFAULT_TTL = 8 h`) y por inactividad
  (`DEFAULT_IDLE = 30 min`).
- Rotación explícita (`/api/session/rotate`): invalida el `sid` anterior y
  emite uno nuevo con su CSRF.
- Cierre de sesión (`/api/session/logout`) y revocación global al reiniciar.
- No se guardan sesiones en disco.

## 6. Fuerza bruta

- 8 fallos en 5 minutos por IP bloquean 60 segundos
  (`DEFAULT_MAX_FAILURES`, `DEFAULT_WINDOW`, `DEFAULT_BLOCK`).
- El bloqueo es progresivo por repetición y se libera al autenticar
  correctamente.
- La IP se obtiene de `client_address`; no se confía en `X-Forwarded-For`
  porque el panel no está detrás de un proxy soportado.

## 7. Cookie heredada

`xrepost_token` **ya no se emite** al iniciar sesión. Se sigue aceptando si un
cliente antiguo conserva la cookie, y solo para lecturas: no permite escribir,
no se renueva y no se vuelve a entregar. Su retirada definitiva requiere una
migración coordinada y está registrada como deuda en `INFORME_FINAL.md`.

## 8. Pruebas

- `web/test_app.py`: acceso sin sesión, token inválido, caducidad, rotación,
  cierre, CSRF correcto/incorrecto, `Origin`/`Host` externos, cuerpo excesivo.
- `tests/test_core_modules.py::SecurityHardeningTest`: expiración absoluta y
  por inactividad, rotación, revocación, fuerza bruta, cookies y comparación
  constante.

## 9. Limitaciones

- Sin TLS: el panel es solo loopback; marcar `Secure` rompería el uso local.
- Sin segundo factor: el modelo es un usuario local y un token de 32 bytes.
- La cookie heredada sigue aceptándose para lectura hasta que se migren los
  clientes, pero ya no se emite.
