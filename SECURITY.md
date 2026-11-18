# Política de seguridad

## Versiones soportadas

Se da soporte a la rama `main` y a la rama de desarrollo activa. Las versiones
anteriores no reciben parches salvo que el fallo afecte a la integridad de los
datos del usuario.

## Cómo informar de una vulnerabilidad

No abras un issue público con detalles explotables. Escribe al mantenedor del
repositorio (luisrignack) indicando:

- versión o commit afectado;
- pasos de reproducción;
- impacto esperado (confidencialidad, integridad, disponibilidad);
- si el fallo requiere una sesión de X autenticada.

Se acusará recibo en un plazo orientativo de 7 días y se publicará la corrección
junto con una nota en `CHANGELOG.md` cuando el fallo esté resuelto.

## Modelo de despliegue

xrepost es una aplicación **local**:

- el panel escucha únicamente en `127.0.0.1`;
- no hay TLS porque no hay tráfico de red;
- el token maestro y las sesiones viven en memoria y en archivos `0600`;
- CDP se valida contra loopback, un puerto explícito y el perfil dedicado de
  xrepost antes de cualquier operación sobre X.

Exponer el panel en una interfaz de red, un proxy inverso o un contenedor con
puertos publicados queda **fuera del modelo de amenazas** y no se considera un
uso soportado.

## Alcance

Se consideran vulnerabilidades:

- ejecución de comandos o lectura/escritura arbitraria de archivos;
- elusión de la autenticación o del CSRF;
- uso del panel como proxy hacia CDP o hacia X;
- exfiltración del token maestro, de la cookie de sesión o del historial;
- corrupción o pérdida de historial, cuentas o perfiles.

No se consideran vulnerabilidades:

- que un usuario con acceso físico a la máquina lea sus propios archivos;
- limitaciones o bloqueos impuestos por X;
- captchas o restricciones de cuenta (la aplicación se detiene, no las elude).

## Prácticas del repositorio

- Dependencias de ejecución: solo biblioteca estándar de Python.
- CI ejecuta `ruff`, `shellcheck`, `bandit`, `gitleaks`, `pip-audit` y la suite
  de pruebas.
- Los secretos no se registran en logs y los archivos sensibles se crean con
  `umask 077` y permisos `0600`.
- Las pruebas no realizan reposts reales ni llamadas a X.
