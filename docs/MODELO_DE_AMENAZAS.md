# Modelo de amenazas

## 1. Alcance y supuestos

El sistema es una herramienta personal que se ejecuta en el equipo del usuario
y controla una sesión real de X mediante Chrome/CDP. El panel escucha en
loopback. Quedan fuera del alcance:

- Compromiso del sistema operativo o del usuario local.
- Manipulación del binario de Chrome o de la extensión que habla con CDP.
- Ataques de X o de la red contra la cuenta (bloqueos, captchas, cambios de
  interfaz) más allá de detectarlos y detener la tanda.
- Servicios externos de terceros.

Activos a proteger, por orden de impacto:

1. **Cuenta de X**: publicar, citar o deshacer sin consentimiento.
2. **Integridad del historial**: saber qué se publicó y poder deshacerlo.
3. **Token maestro y sesión**: acceso al panel y, por tanto, a la cuenta.
4. **Datos personales**: perfiles de filtros, grupos, bandeja y textos.
5. **Disponibilidad**: no perder trabajo por un fallo del panel o de Chrome.

## 2. Actores

| Actor | Capacidad | Motivación |
| --- | --- | --- |
| Usuario legítimo | Acceso local, conoce el token | Operar la herramienta. |
| Página web maliciosa abierta en el mismo navegador | Enviar peticiones a `127.0.0.1`, leer respuestas si no hay CORS/CSP | Provocar reposts o filtrar datos. |
| Proceso local no privilegiado | Leer archivos con permisos laxos, escuchar puertos | Robar el token o el historial. |
| Sitio de X comprometido o cambiado | Alterar el DOM, pedir captcha, cerrar sesión | Bloquear la automatización. |
| Atacante de red | Interceptar tráfico si el CDP se expone | Controlar Chrome. |

## 3. Amenazas y controles

### T-01 CSRF contra el panel

**Escenario**: el usuario visita una página que envía un `POST` a
`http://127.0.0.1:8765/api/apply` con `fetch` y `mode: no-cors`. Si el panel
aceptara cookies sin más, se ejecutaría un repost.

**Controles**:

- `Origin` exacto contra `Host`, con rechazo si falta el esquema o el puerto no
  coincide.
- `X-CSRF-Token` obligatorio para sesiones.
- `SameSite=Strict` en la cookie, que impide enviarla en peticiones
  cross-site.
- CSP `connect-src 'self'` y ausencia de CORS.
- `X-Token` solo se acepta como cabecera personalizada, lo que fuerza un
  preflight que el servidor no concede.

**Riesgo residual**: bajo. Un navegador con una extensión maliciosa podría
leer la cookie, pero entonces el perímetro ya está comprometido.

### T-02 Robo del token maestro

**Escenario**: el token aparece en el historial del navegador, en un log o en
`ps`.

**Controles**:

- El enlace `/?token=…` se convierte inmediatamente en cookie y redirige con
  `303`; no se sirve HTML con el token incrustado.
- `iniciar.sh` guarda el token en `panel-token` (0600) y el enlace en
  `panel-url` (0600); no lo imprime en el log.
- `--token-file` permite arrancar sin pasar el token por la línea de comandos.
- La sesión caduca y se puede rotar o revocar.

**Riesgo residual**: medio si el usuario comparte el enlace. Se documenta no
hacerlo.

### T-03 Fuerza bruta del token

**Escenario**: un proceso local prueba tokens contra `/?token=`.

**Controles**: 8 fallos / 5 minutos → bloqueo de 60 s por IP; comparación
constante en el tiempo; token de 32 bytes.

**Riesgo residual**: el atacante puede esperar. El token de 256 bits hace
inviable la fuerza bruta.

### T-04 Control del CDP por otro origen

**Escenario**: Chrome se lanza con `--remote-debugging-address=0.0.0.0` o se
usa un túnel, y un tercero controla el navegador.

**Controles**:

- `xrepost_cdp.parse_endpoint()` exige loopback, esquema `http`, sin
  credenciales y sin ruta.
- `--strict-cdp` añade la comprobación del perfil.
- El panel revalida el endpoint en cada trabajo.
- `xrepost-chrome.sh` lanza Chrome con el perfil de xrepost.

**Riesgo residual**: si el usuario expone el puerto manualmente, el control se
salta. Se documenta como configuración no soportada.

### T-05 Inyección de comandos en subprocesos

**Escenario**: un parámetro con `; rm -rf` llega a una shell.

**Controles**:

- `subprocess` con listas de argumentos, sin `shell=True`.
- Validación de usuarios, fechas, URL y filtros antes de construir el comando.
- Entorno con lista blanca.
- El motor recibe parámetros por variables de entorno controladas y por
  archivos, no por concatenación de shell.

**Riesgo residual**: bajo.

### T-06 Repost no deseado por estado obsoleto

**Escenario**: se previsualiza, cambian los datos y se pulsa ejecutar; o se
reintenta una tanda cuyo resultado se desconoce.

**Controles**:

- `preview.params["key"]` debe coincidir con la clave de los parámetros
  actuales antes de ejecutar.
- La previsualización debe haber terminado correctamente y tener
  publicaciones.
- `selected_urls`, si se envía, debe ser un subconjunto exacto de la
  previsualización.
- Los resultados `unconfirmed` y `quote_unverified` no se reintentan sin
  `--force`.
- El motor verifica el estado real del botón tras la acción.

**Riesgo residual**: bajo; un resultado incierto puede requerir revisión
manual, que es el comportamiento deseado.

### T-07 Pérdida o corrupción del historial

**Escenario**: corte de luz durante una escritura, disco lleno, edición
manual.

**Controles**:

- Escritura atómica con `fsync`.
- Rotación con archivos `history-archivo-*`.
- `--diagnose` cuenta líneas corruptas sin borrarlas.
- `--backup` genera un archivo con checksum; `--restore` lo verifica y
  conserva el historial anterior como `history.pre-restore-*`.
- Las líneas corruptas se ignoran al leer, pero no se eliminan.

**Riesgo residual**: bajo. Un backup también puede corromperse; se recomienda
copiarlo fuera del equipo.

### T-08 Filtración de secretos en logs

**Escenario**: el entorno del servidor contiene credenciales y el motor las
hereda o las imprime.

**Controles**:

- Entorno con lista blanca.
- `sanitize_params()` antes de persistir.
- `--verbose` no registra cabeceras ni cuerpos.
- Los errores del motor se muestran al usuario, pero los detalles internos se
  limitan a la traza del log local.

### T-09 XSS mediante contenido de publicaciones

**Escenario**: un post contiene `<script>` o `javascript:` y la interfaz lo
inserta como HTML.

**Controles**:

- La interfaz usa `textContent` y creación de nodos, no `innerHTML` con datos.
- Las exportaciones HTML escapan y solo enlazan URLs `http(s)`.
- CSP sin `unsafe-inline` para scripts.
- CSV neutraliza fórmulas.

**Riesgo residual**: bajo.

### T-10 Denegación de servicio local

**Escenario**: un trabajo bloquea Chrome durante 30 minutos o un archivo de
estado crece sin límite.

**Controles**:

- Un trabajo a la vez; los demás quedan en cola.
- Límite de 30 minutos por trabajo.
- Límite de 1 MB por cuerpo y 8 MB por documento de estado (la bandeja, 8 MB).
- `MAX_JOBS = 20` y poda de ejecuciones antiguas.
- Cancelación con grupo de procesos.

## 4. Matriz de riesgo

| Amenaza | Probabilidad | Impacto | Riesgo residual |
| --- | --- | --- | --- |
| T-01 CSRF | Media | Alto | Bajo |
| T-02 Robo de token | Media | Alto | Medio |
| T-03 Fuerza bruta | Baja | Alto | Bajo |
| T-04 CDP expuesto | Baja | Crítico | Bajo (con `--strict-cdp`) |
| T-05 Inyección | Baja | Alto | Bajo |
| T-06 Repost no deseado | Media | Alto | Bajo |
| T-07 Pérdida de historial | Media | Medio | Bajo |
| T-08 Filtración de logs | Baja | Medio | Bajo |
| T-09 XSS | Media | Medio | Bajo |
| T-10 DoS local | Media | Bajo | Bajo |

## 5. Decisiones y compensaciones

- **Sesión en memoria frente a persistente**: se pierde comodidad al reiniciar,
  pero se elimina el riesgo de robar un archivo de sesión.
- **`X-Token` para CLI**: mantiene compatibilidad y automatización, a cambio de
  que el token circule en la cabecera. Se acepta porque no hay CSRF posible sin
  preflight.
- **Programación solo de previsualización**: evita reposts automáticos sin
  revisión humana. Es una decisión de producto y de seguridad.
- **Sin TLS**: el tráfico no sale del equipo. Añadir TLS complicaría el
  arranque sin mejorar el modelo frente a un atacante local.
- **CSP con estilos inline**: se prioriza una interfaz sin dependencias frente
  a una CSP más estricta. Los scripts siguen vetados.

## 6. Revisión

Este modelo debe revisarse si:

- El panel deja de escuchar en loopback.
- Se añade un servicio externo o una API remota.
- Se permite ejecutar `apply` desde la programación.
- Se añade autenticación multiusuario.
- Cambia el mecanismo de control de Chrome.
