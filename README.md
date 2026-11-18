# xrepost — documentación completa

Herramienta para **repostear posts de usuarios concretos dentro de un rango de fechas** en X (Twitter), usando la sesión de Chrome que ya tienes abierta.

No usa la API de X ni pide contraseñas: controla tu navegador real mediante CDP (Chrome DevTools Protocol) a través del harness `browser-use`.

---

## Índice

1. [Qué es y qué hace](#1-qué-es-y-qué-hace)
2. [Estructura de la carpeta](#2-estructura-de-la-carpeta)
3. [Requisitos](#3-requisitos)
   - [3.1 ¿Hace falta un modelo de IA?](#31-hace-falta-un-modelo-de-ia)
4. [Instalación (una sola vez)](#4-instalación-una-sola-vez)
5. [Uso](#5-uso)
6. [Variables de entorno](#6-variables-de-entorno)
7. [Cómo funciona por dentro](#7-cómo-funciona-por-dentro)
8. [Estados de salida y errores](#8-estados-de-salida-y-errores)
9. [Diagnóstico](#9-diagnóstico)
10. [Límites, riesgos y buenas prácticas](#10-límites-riesgos-y-buenas-prácticas)
11. [Cómo extenderlo](#11-cómo-extenderlo)
12. [Verificación realizada](#12-verificación-realizada)
13. [Preguntas frecuentes](#13-preguntas-frecuentes)

---

## 1. Qué es y qué hace

`xrepost` responde a una pregunta concreta: *"¿qué publicó tal usuario entre el día A y el día B, y quiero repostearlo?"*

Hace cuatro cosas:

1. **Busca** los posts de una lista de usuarios en un rango de fechas, usando la búsqueda nativa de X (`from:`, `since:`, `until:`).
2. **Filtra** por fecha real, descarta respuestas y —según el alcance elegido— los retweets de otras cuentas, elimina duplicados, aplica filtros de palabras (`X_MATCH` / `X_EXCLUDE`) y muestra un listado con autor, fecha, texto y enlace; opcionalmente lo exporta a CSV o Markdown.
3. **Repostea** (opcional) cada uno de esos posts, con límite y pausas, verificando que el repost se hizo de verdad. Con `--quote` (o el campo del panel) publica en su lugar un **repost con cita** y un comentario de hashtags común a toda la tanda.
4. **Registra y deshace**: guarda cada repost en un historial para no repetirlo en ejecuciones futuras y permite revertirlo con `--undo-last` o `--undo`.

Por defecto **no repostea nada**: primero enseña la lista (modo *dry-run*). Solo actúa si se lo pides explícitamente con `X_APPLY=1`.

---

## 2. Estructura de la carpeta

```
~/Downloads/x-repost/
├── xrepost.sh                 # interfaz: pregunta usuarios/fechas o recibe argumentos
├── xrepost.py                 # lógica: búsqueda, filtrado, repost y verificación
├── xrepost_accounts.py        # cuentas recordadas, ranking y prompt con sugerencias
├── xrepost_hashtags.py        # hashtags recordados, ranking y normalización de la cita
├── xrepost_history.py         # estado del historial compartido: deduplicación y tanda deshacible
├── xrepost_labels.py          # etiquetas de resultado compartidas (motor, CLI y panel)
├── web/                       # panel web local (guía propia en web/README.md)
├── README.md                  # este documento (texto, se actualiza primero)
└── xrepost-documentacion.pdf  # este mismo documento en PDF (16 páginas)
```

- **`xrepost.sh`** es un envoltorio Bash. Recoge los datos, los pasa como variables de entorno y ejecuta `browser-use < xrepost.py`.
- **`xrepost.py`** se ejecuta *dentro* del harness. No importa `browser-use`: las funciones (`goto_url`, `js`, `wait_for_load`, …) ya están disponibles en el entorno de ejecución.
- **`xrepost_accounts.py`** guarda las cuentas usadas, calcula las coincidencias y dibuja el autocompletado del modo interactivo. El panel web usa el mismo archivo.
- **`xrepost_hashtags.py`** hace lo mismo con los hashtags del comentario de una cita: normaliza el texto, guarda los usados y calcula las sugerencias del panel.
- **`xrepost_labels.py`** es la única fuente de las etiquetas de resultado (`reposteado`, `citado con comentario`, `deshecho`…): la usan el motor, `--history` y el historial del panel, para que no se desincronicen.
- **`xrepost_history.py`** es la única fuente de verdad sobre qué posts siguen reposteados y cuáles puede deshacer la herramienta (p. ej. tras un `undo_failed` el repost sigue vigente y el panel debe seguir ofreciendo deshacerlo). La usan el motor y el panel.
- **`web/`** contiene el panel web local: un servidor de la biblioteca estándar (`web/app.py`) que invoca al mismo motor como subproceso y una interfaz estática (`web/static/`). Su guía completa —arranque, flujo, selección post a post, progreso en vivo, seguridad y pruebas— está en `web/README.md`.

En el panel, la **papelera** a la derecha de «Cuentas» y de «Hashtag de la cita» borra el historial guardado de cada campo, con confirmación previa. Las sugerencias quedan vacías y solo se vuelven a llenar cuando se usan cuentas o hashtags de nuevo.

El historial y los estados no viven en la carpeta, sino en `~/.local/state/xrepost/history.jsonl` (una línea JSON por acción). Se puede cambiar con `X_HISTORY`; los `--csv` / `--md` se guardan donde indiques. Las cuentas recordadas se guardan en `~/.local/state/xrepost/accounts.json` (cambiable con `X_ACCOUNTS`) y los hashtags en `~/.local/state/xrepost/hashtags.json` (cambiable con `X_HASHTAGS`).

---

## 3. Requisitos

| Pieza | Versión usada | Para qué |
|---|---|---|
| Google Chrome | 153 | El navegador que se controla |
| `browser-use` (CLI) | 0.1.13 | Harness que habla CDP |
| `browser-use` (paquete) | 0.13.14 | Librería |
| Python | 3.12.14 (gestionado por `uv`) | Ejecuta el script |
| `uv` | 0.12+ | Instala y aísla Python/paquetes |

Comprobar que todo está:

```bash
browser-use --version
browser-use --doctor
```

### 3.1 ¿Hace falta un modelo de IA?

**No.** `xrepost` no llama a ningún modelo de lenguaje en tiempo de ejecución. Es automatización determinista del DOM: órdenes fijas ("navega a esta URL", "lee este selector", "haz clic aquí") ejecutadas contra Chrome.

Hay dos cosas distintas que se llaman `browser-use`:

| Componente | Qué es | ¿Usa LLM? |
|---|---|---|
| **CLI / harness** (`browser-use`) | Controlador de Chrome por CDP. Expone `goto_url`, `js`, `wait_for_load`… | **No** |
| **Librería `Agent`** (Python) | Agente que decide los pasos por su cuenta | Sí, pero **no se usa aquí** |

`xrepost.py` se ejecuta dentro del **harness**, no dentro de `Agent`. No hay ninguna decisión "inteligente" en el camino: la lista de acciones está escrita de antemano.

Verificación sobre el código instalado:

```bash
grep -rE "OPENAI_API_KEY|api.openai.com|api.anthropic.com" \
  ~/.local/share/uv/tools/browser-use/lib/python3.12/site-packages/browser_harness/
# → sin resultados
```

Las únicas llamadas de red del harness son:

| Destino | Cuándo |
|---|---|
| `api.browser-use.com` | Solo si se usan navegadores en la nube (aquí no) |
| `eu.i.posthog.com` | Telemetría anónima; se apaga con `browser-use telemetry disable` |

Es decir: el programa funciona sin ninguna clave de API de IA, sin conexión a un proveedor de modelos y sin coste por token. Con internet solo para llegar a X.

**¿Dónde está entonces la IA?** En el agente que construyó el script (OpenCode) mientras se conversaba con él. Una vez creado, el programa se lanza desde una terminal sin ningún modelo involucrado:

```bash
cd ~/Downloads/x-repost && ./xrepost.sh
```

**Cuándo sí haría falta un modelo (opcional):**

- Decidir *qué* posts merecen repost ("solo los de Kubernetes, no las ofertas de empleo").
- Resumir el timeline antes de aprobar.
- Redactar un comentario libre para un quote-repost: la herramienta solo convierte en hashtags lo que escribas (por ejemplo `ETECSA, cuba` → `#ETECSA #cuba`).
- Sustituir el script por un agente que se adapte si X cambia el HTML.

Nada de eso es necesario para la función actual: usuarios + fecha → lista → repost verificado.

---

## 4. Instalación (una sola vez)

```bash
# 1. instalar el CLI y la librería en un entorno aislado con Python 3.12
uv tool install --python 3.12 browser-use

# 2. registrar la skill en OpenCode (opcional, para usarlo desde el agente)
browser-use skill install --target opencode --no-install
```

La skill queda en `~/.config/opencode/skills/browser-use/SKILL.md` y permite pedirle tareas al agente en lenguaje natural.

---

## 5. Uso

### 5.1 Arrancar Chrome con el puerto de control

Chrome tiene que estar escuchando en `9222`. Desde Chrome 136 el debugging remoto está **bloqueado en el perfil por defecto**, así que se usa un perfil dedicado:

```bash
google-chrome --user-data-dir="$HOME/.local/state/xrepost/chrome-profile" \
              --remote-debugging-port=9222 &
```

En ese perfil, inicia sesión en X una vez (la sesión se guarda ahí).

Comprobar que el puerto responde:

```bash
curl -s http://127.0.0.1:9222/json/version | grep Browser
```

### 5.2 Modo interactivo (usuarios, fechas y alcance)

```bash
cd ~/Downloads/x-repost
./xrepost.sh
```

```
=== xrepost ===
  ↑/↓ elegir · Tab completar · Enter aceptar · Esc cerrar
Usuarios (separados por coma, @ opcional): kubernetesio, docker

Fechas (DD/MM/AAAA): escribe los 8 dígitos seguidos; las barras se añaden solas.
Enter acepta el valor entre corchetes.
  Fecha desde [28/10/2026]: 20102026
  Fecha hasta (Enter = la misma) [20/10/2026]: 28102026

Alcance de las publicaciones
  Indique qué publicaciones de las cuentas seleccionadas desea considerar:

    1) Solo publicaciones originales (recomendado)
       Se excluyen los retweets que esas cuentas hayan hecho de otras cuentas.

    2) Publicaciones originales y retweets de otras cuentas
       Se incluyen también esos retweets; al repostear, se repostea la
       publicación original, no el retweet.

  Seleccione una opción [1/2] (Enter = 1): 2
  → Alcance: publicaciones originales y retweets de otras cuentas.
```

Al escribir una cuenta, el campo muestra un desplegable con las cuentas usadas antes que coinciden con lo tecleado. Las coincidencias se ordenan por tipo (exacta, empieza por, contiene), luego por uso reciente y frecuencia. `↑`/`↓` mueve la selección, `Tab` completa el token y añade una coma para la siguiente cuenta, `Enter` acepta lo escrito o la sugerencia seleccionada, y `Esc` cierra el desplegable. Las cuentas se recuerdan al ejecutar la búsqueda, también cuando se pasan como argumentos. La **papelera** a la derecha del campo borra el historial de cuentas guardadas (pide confirmación); las cuentas anteriores dejan de sugerirse y solo vuelven a aparecer cuando se usan otra vez. El borrado también ignora los eventos anteriores del historial JSONL que alimentaban el autocompletado.

Las fechas se escriben en un campo enmascarado con avance automático en formato **DD/MM/AAAA**: al teclear `20102026` se ve `20/10/2026`, las barras se insertan solas y no hace falta pulsar Enter. El campo rechaza mientras se escribe lo imposible (día `90`, mes `13`…), autorrellena `9` como `09` y al octavo dígito valida el calendario: `30/02/2026` se marca y se vuelve a pedir; lo mismo con años fuera de 2006–2100. `Enter` sobre un campo vacío toma el valor entre corchetes (hoy para «desde», la fecha inicial para «hasta»). Si la fecha inicial queda después de la final, se vuelven a pedir ambas.

La pregunta de alcance define qué se considera publicación de la cuenta:

- **Opción 1 (por defecto):** solo publicaciones originales. Los retweets que la cuenta haya hecho de otras cuentas se omiten (`X_SKIP_RETWEETS=1`).
- **Opción 2:** incluye también esos retweets (`X_SKIP_RETWEETS=0`). Al repostear se abre la publicación original, no el retweet.

Si `X_SKIP_RETWEETS` ya está definida en el entorno, no se pregunta: se respeta ese valor y se informa del alcance elegido.

### 5.3 Modo con argumentos

```bash
./xrepost.sh <usuarios> <desde> [hasta]
```

| Ejemplo | Qué hace |
|---|---|
| `./xrepost.sh kubernetesio 27/10/2026` | Lista los posts de ese día (dry-run) |
| `./xrepost.sh kubernetesio 20/10/2026 28/10/2026` | Lista el rango |
| `./xrepost.sh a,b,c 27/10/2026` | Varios usuarios a la vez |
| `X_MATCH="kubernetes,cloud" ./xrepost.sh a 27/10/2026` | Solo posts que contengan alguna de esas palabras |
| `X_EXCLUDE="empleo,oferta" ./xrepost.sh a 27/10/2026` | Descarta posts que contengan alguna |
| `X_SKIP_RETWEETS=0 ./xrepost.sh a 27/10/2026` | Incluye también los retweets de otras cuentas |
| `X_APPLY=1 ./xrepost.sh kubernetesio 27/10/2026` | Repostea de verdad |
| `X_APPLY=1 X_LIMIT=3 X_DELAY=45 ./xrepost.sh a 27/10/2026` | Máximo 3, con 45 s entre cada uno |
| `X_APPLY=1 ./xrepost.sh --quote "#ETECSA" a 27/10/2026` | Repost con cita y el comentario `#ETECSA` |
| `./xrepost.sh --quote "ETECSA, cuba" a 27/10/2026` | Dry-run de citas; normaliza a `#ETECSA #cuba` |

Al citar, el motor trae la pestaña de Chrome al frente antes de abrir el menú: X no monta el modal de cita si la pestaña está en segundo plano.

Las fechas por argumentos se escriben **DD/MM/AAAA** (también se acepta `AAAA-MM-DD` por compatibilidad). Si solo se pasa una, se usa como día único.

También se puede pasar todo por variables de entorno, sin argumentos:

```bash
X_USERS=kubernetesio X_FROM=27/10/2026 X_MATCH=cloud ./xrepost.sh
```

En modo con argumentos o por variables no se pregunta nada: el alcance queda en «solo originales» salvo que definas `X_SKIP_RETWEETS=0`. Las fechas se validan igualmente y un valor imposible termina con un error claro antes de abrir Chrome. Las cuentas usadas por argumentos o por `X_USERS` también se guardan para las próximas sugerencias.

### 5.4 Exportar el listado

```bash
./xrepost.sh --csv posts.csv kubernetesio 27/10/2026
./xrepost.sh --md posts.md kubernetesio 20/10/2026 28/10/2026
```

El CSV lleva `fecha,autor,usuario,texto,url,estado`; el Markdown es una tabla con enlace al post. El estado es `solo listado` en dry-run y el resultado real (reposteado, ya estaba, fallo…) cuando se aplica. Se pueden usar ambos a la vez.

### 5.5 Historial

```bash
./xrepost.sh --history        # últimos 20 movimientos
./xrepost.sh --history 50     # últimos 50
```

Cada repost o undo se guarda en `~/.local/state/xrepost/history.jsonl` con fecha (en ISO, para ordenar), ejecución, autor, handle, URL y resultado. `--history` la muestra como DD/MM/YYYY HH:MM. Antes de repostear, la herramienta omite lo que ya consta como reposteado; para forzar que lo vuelva a procesar: `--force` (o `X_FORCE=1`).

### 5.6 Deshacer

```bash
./xrepost.sh --undo-last          # todo lo reposteado en la última ejecución
./xrepost.sh --undo-last 3        # los últimos 3 reposts
./xrepost.sh --undo https://x.com/usuario/status/1234567890
./xrepost.sh --undo 1234567890
```

Solo deshace reposts **hechos por la herramienta** (no los que ya estaban antes); verifica contra el DOM que el botón vuelve a ser `retweet`. Igual que al repostear, hay pausa `X_DELAY` entre cada uno.

### 5.7 Ayuda

```bash
./xrepost.sh --help
```

---

## 6. Variables de entorno

| Variable | Por defecto | Significado |
|---|---|---|
| `X_USERS` | — | Lista separada por comas. El `@` es opcional |
| `X_FROM` | — | Fecha inicial `DD/MM/AAAA` (también `YYYY-MM-DD`) |
| `X_TO` | igual a `X_FROM` | Fecha final **incluida** |
| `X_APPLY` | `0` | `0` = solo listar · `1` = repostear |
| `X_LIMIT` | `10` | Máximo de reposts en la ejecución |
| `X_DELAY` | `20` | Segundos de espera entre reposts |
| `X_SKIP_REPLIES` | `1` | `1` = ignorar respuestas · `0` = incluirlas |
| `X_SKIP_RETWEETS` | `1` | `1` = solo publicaciones originales (omite los retweets de otras cuentas) · `0` = incluye esos retweets. En modo interactivo se pregunta, salvo que la variable ya esté definida |
| `X_MATCH` | — | Palabras separadas por comas; el post debe contener **alguna** (sin distinguir mayúsculas) |
| `X_EXCLUDE` | — | Palabras separadas por comas; si el post contiene **alguna**, se descarta |
| `X_QUOTE` | — | Comentario del repost con cita. Cada palabra se normaliza a hashtag (`ETECSA, cuba` → `#ETECSA #cuba`). Vacío = repost normal |
| `X_FORCE` | `0` | `1` = ignorar el historial y volver a procesar lo ya reposteado |
| `X_HISTORY` | `~/.local/state/xrepost/history.jsonl` | Ruta del historial JSONL |
| `X_ACCOUNTS` | junto al historial (`.../accounts.json`) | Ruta de las cuentas recordadas para el autocompletado |
| `X_HASHTAGS` | junto al historial (`.../hashtags.json`) | Ruta de los hashtags recordados para el autocompletado de la cita |
| `X_CSV` / `X_MD` | — | Exportación; normalmente se usan los flags `--csv` / `--md` |
| `BU_CDP_URL` | `http://127.0.0.1:9222` | Endpoint de Chrome |

---

## 7. Cómo funciona por dentro

### 7.1 Arquitectura

```
┌─────────────────┐   CDP (WebSocket)   ┌──────────────┐   stdin    ┌───────────────┐
│  Chrome real    │◄───────────────────►│ browser-use  │◄───────────│  xrepost.py   │
│ (tu sesión X)   │   puerto 9222       │  daemon/CLI  │  (script)  │  + xrepost.sh │
└─────────────────┘                     └──────────────┘            └───────────────┘
```

- **Chrome con CDP**: una API para programar el navegador (navegar, evaluar JS, leer el DOM, hacer clic). Es la misma que usan las DevTools con F12.
- **browser-use**: mantiene un daemon conectado al navegador y expone funciones cortas que traducen a comandos CDP (`Page.navigate`, `Runtime.evaluate`, …). El daemon persiste entre ejecuciones, por eso recuerda la pestaña actual.
- **xrepost.py**: decide *qué* hacer; no habla con Chrome directamente.

### 7.2 Recorrido de una ejecución

**Paso 1 — el wrapper recoge los datos.** `xrepost.sh` interpreta los flags (`--csv`, `--md`, `--force`, `--undo-last`, …), toma usuarios y fechas de los argumentos (o de `X_USERS`/`X_FROM`, o los pregunta) y los exporta como variables de entorno. En modo interactivo delega la entrada de usuarios en `xrepost_accounts.py`, que lee las cuentas recordadas y el historial, dibuja las coincidencias mientras se escribe y devuelve la lista elegida. Si se pasa `--quote` (o `X_QUOTE`), el wrapper normaliza el comentario con `xrepost_hashtags.py` (cada palabra se vuelve un hashtag, sin duplicados) y lo guarda para las sugerencias del panel. En modo interactivo, la fecha es un campo enmascarado DD/MM/AAAA que inserta las barras y valida el calendario (por dentro se normaliza a ISO); después se pregunta el alcance (solo originales o también retweets) y la respuesta se traduce a `X_SKIP_RETWEETS`. Las fechas recibidas por argumentos o variables también se validan antes de navegar. Después ejecuta:

```bash
exec browser-use < xrepost.py
```

El script entra por **stdin**; por eso no necesita importar nada del harness.

**Paso 2 — construye la búsqueda.** Traduce usuarios y fechas a la sintaxis de X:

```
https://x.com/search?q=from%3Akubernetesio%20since%3A2026-10-27%20until%3A2026-10-28&f=live
```

| Parte | Por qué |
|---|---|
| `from:usuario` | limita al autor |
| `since:` / `until:` | rango de fechas; `until` es **exclusivo**, así que se suma un día |
| `f=live` | orden cronológico en vez del "Top" algorítmico |

**Paso 3 — navega y espera.** `goto_url()` y `wait_for_load()`. Como X es una SPA, "cargado" no implica "con posts": `wait_articles()` sondea cada segundo hasta que aparece al menos un `article[data-testid="tweet"]` (máx. 12 s).

**Paso 4 — extrae datos del DOM** con JavaScript ejecutado dentro de la página:

| Campo | Selector / fuente |
|---|---|
| `time` | atributo `datetime` del `<time>` (ISO real, no "2h") |
| `url` | `href` del enlace que contiene `/status/` |
| `user` | `[data-testid="User-Name"]` (nombre visible) |
| `handle` | segunda línea de `[data-testid="User-Name"]` (`@usuario`); si falta, se saca de la URL |
| `text` | `[data-testid="tweetText"]` |
| `ctx` | `[data-testid="socialContext"]` (contexto tipo "reposted", solo informativo) |
| `reply` | ¿hay enlaces de perfil antes de `tweetText`? → detecta respuestas por estructura, no por idioma |

**Paso 5 — filtra y pagina.** Descarta lo que cae fuera del rango, descarta respuestas (`X_SKIP_REPLIES=1`, por estructura del DOM) y **retweets** cuando el alcance es «solo originales» (`X_SKIP_RETWEETS=1`, comparando el handle del autor con el usuario buscado), aplica `X_MATCH` / `X_EXCLUDE` sobre el texto, deduplica por URL de forma global (también entre usuarios de la misma ejecución) y hace `window.scrollBy(0, 1600)` hasta 8 veces para forzar el scroll infinito de X. En cada vuelta vuelve a extraer y acumula.

**Paso 6 — decide y exporta.** Consulta el historial y omite lo que ya consta como reposteado (salvo `--force`). Sin `X_APPLY=1` imprime el listado, escribe los `--csv` / `--md` si se pidieron y termina. Cero escrituras en X.

**Paso 7 — repostea (solo con `X_APPLY=1`).** Para cada URL:

1. `goto_url(post)` y espera.
2. Si ya existe `[data-testid="unretweet"]` → ya estaba reposteado, se salta.
3. Clic en `[data-testid="retweet"]` → X abre un menú.
4. Espera a que aparezca `[data-testid="retweetConfirm"]` ("Repost / Quote").
5. Clic en "Repost".
6. **Verifica**: si ahora existe `unretweet`, se hizo. Si no, lo reporta como fallo.
7. Anota el resultado en el historial y `sleep(X_DELAY)`; siguiente, hasta `X_LIMIT`.

**Paso 8 — informa.** Una línea por post con el resultado y el total reposteado. Si se pidió exportación, reescribe el CSV/Markdown con el estado final de cada post.

**Paso 9 — deshacer (`--undo-last` / `--undo`).** No busca ni repostea: lee el historial, elige los reposts hechos por la herramienta que siguen vigentes, entra en cada URL, pulsa `unretweet` (y confirma si X abre el menú) y verifica que el botón vuelve a ser `retweet`. Cada intento se apunta en el historial.

### 7.3 Decisiones de diseño (y por qué)

- **Clics por JS, no por coordenadas.** El harness ofrece `click_at_xy` (ratón real), pero en X el `scroll()` por rueda se colgaba (`Input.dispatchMouseEvent timed out`). Solución: `element.click()` desde la página y scroll con `window.scrollBy`. Funciona porque React de X escucha eventos nativos de clic.
- **Verificar contra el DOM, no contra "no dio error".** Un clic puede fallar en silencio; el cambio `retweet` → `unretweet` es la única prueba fiable.
- **Cada ejecución trabaja en su propia pestaña.** El motor abre una pestaña nueva (`about:blank`) al empezar, navega solo en ella y la cierra al terminar o al cancelar el trabajo (el panel cancela con `SIGTERM`). Así las pestañas que dejes abiertas en el Chrome de CDP no se mueven, y tampoco el panel, que además vive en otra instancia de Chrome con perfil propio (`~/.cache/xrepost-web/panel-profile`).
- **Solo el post abierto y una ejecución a la vez.** Los botones se buscan dentro del artículo del post indicado en la URL (no en toda la página, donde las respuestas también tienen `retweet`/`unretweet`), y `xrepost.sh` toma un `flock` sobre `$X_HISTORY.lock` para que el CLI y el panel no reposteén en paralelo.
- **Fechas del `<time>`, no del texto visible.** X muestra "8h" o "Oct 27", que engaña al cruzar días u husos horarios.
- **La fecha se escribe como campo enmascarado, no como texto libre.** El prompt inserta las barras, descarta días y meses imposibles al teclear y acepta al octavo dígito, así que no se puede escribir `2O/1O/2O26` ni `90/90/9090`. Se muestra en DD/MM/AAAA (el orden que usa el usuario) y se convierte a ISO por dentro para la búsqueda de X y el historial. La validación usa el calendario real (`date -d`) antes de abrir Chrome, y el rango se comprueba en el mismo paso: un error de fecha se detecta en segundos, no después de navegar.
- **El alcance se pregunta explícitamente y se traduce a una variable.** «Solo originales» y «también retweets» son decisiones con consecuencias distintas sobre la cuenta; en vez de dejar que el usuario adivine el valor de `X_SKIP_RETWEETS`, el modo interactivo lo pregunta con las dos opciones descritas, recomienda la conservadora y respeta la variable si ya venía definida (útil para `cron`).
- **Buscar en vez de recorrer el perfil.** Recorrer `x.com/usuario` exige decenas de scrolls y mezcla reposts y posts fijados; la búsqueda `from:` da exactamente autor y rango.
- **Dry-run por defecto.** Evita el escenario "me equivoqué de usuario y reposteé 200 posts".
- **Deduplicación global por URL** antes de actuar: el conjunto `SEEN` es único para toda la ejecución, no por usuario, así que un mismo post encontrado en la búsqueda de dos cuentas (o repetido por el scroll) se lista y se repostea una sola vez.
- **Los retweets se descartan por defecto.** La búsqueda `from:usuario` también devuelve lo que ese usuario ha retuiteado, y ahí el autor real es otro. Repostear eso sería redundante y atribuiría mal el contenido, así que se compara el handle del autor (extraído de `User-Name`, con la URL como respaldo) con el usuario buscado: si no coinciden, es un retweet y se ignora. Antes se buscaba el texto `"X reposted"`, que solo existe con la interfaz en inglés. Para incluirlos: opción 2 del modo interactivo o `X_SKIP_RETWEETS=0`.
- **Las respuestas también se detectan por estructura, no por idioma.** X dibuja la línea "Replying to" (o "Respondiendo a", "Réponse à"…) como enlaces de perfil situados antes del texto del post. Basta con encontrar un enlace `@usuario` fuera de `User-Name` y de `tweetText` que preceda a este último; la lista multilingüe de textos queda solo como respaldo.
- **Historial como fuente de verdad para no repetir.** Cada acción se guarda en JSONL (`reposted`, `already`, `undone`…). Antes de repostear se omiten los IDs cuyo último evento indica que siguen reposteados. Es idempotente entre ejecuciones y sobrevive a reinicios; `--force` lo ignora cuando haces cambios a mano.
- **Deshacer solo lo que hizo la herramienta.** `--undo-last` no toca los posts que ya estaban reposteados antes (`already`), para no revertir acciones ajenas. Si el repost se deshizo a mano, el historial puede quedar desfasado: usa `--force` para volver a procesarlo.
- **Filtros de texto simples, no regex.** `X_MATCH` / `X_EXCLUDE` son subcadenas separadas por comas, sin distinguir mayúsculas: predecible, sin sorpresas de expresiones regulares sobre el contenido.
- **Exportar antes y después.** El CSV/Markdown se escribe al listar (estado `solo listado` o `pendiente`) y se reescribe al terminar con el resultado real, para poder revisar o archivar la tanda.

---

## 8. Estados de salida y errores

Cada post recibe uno de estos estados:

| Estado | Significado |
|---|---|
| `reposteado` | Se hizo y se verificó |
| `ya estaba reposteado` | Se detectó `unretweet` antes de actuar; no se tocó |
| `no encontré el botón de repost` | El post no cargó o no es reposteable (p. ej. borrado o protegido) |
| `el menú no se abrió` | El clic no desplegó el menú de repost |
| `no se pudo confirmar` | Se hizo clic pero no apareció `unretweet` (posible fallo de red o límite de X) |
| `citado con comentario` | Repost con cita publicado y verificado (el modal se cerró) |
| `el menú no ofrecía «Citar»` | El menú de repost no mostró la opción de cita |
| `no se abrió el editor de la cita` | No apareció el compositor con el post citado |
| `no se pudo publicar la cita` | El botón «Post» siguió deshabilitado o el modal no se cerró |

Al deshacer (`--undo-last` / `--undo`):

| Estado | Significado |
|---|---|
| `deshecho` | Se quitó el repost y se verificó que el botón vuelve a `retweet` |
| `no estaba reposteado` | El post ya no tenía repost; no se tocó |
| `no se pudo deshacer` | Se intentó pero `unretweet` sigue apareciendo |

Además, si el historial ya tenía un post como reposteado, el listado avisa `(N ya reposteados en ejecuciones anteriores; usa --force para incluirlos)` y no lo procesa.

El motor imprime una línea por post con el formato `  {estado}: {url}` (dos espacios iniciales). El panel web parsea esas líneas mientras la ejecución corre y las convierte en **progreso en vivo**: barra «X de Y» y etiqueta de estado en cada fila, sin esperar a que termine la tanda.

Códigos de salida:

- `0` — terminó (haya reposteado o no).
- `1` — faltan usuarios o fecha (lo devuelve el wrapper).
- `2` — faltan `X_USERS` o `X_FROM` dentro del script.

---

## 9. Diagnóstico

```bash
# estado general: Chrome, daemon, conexiones
browser-use --doctor

# log del daemon (aquí aparecen los errores reales)
tail -f ~/.config/browser-harness/tmp/bu-default.log

# ¿responde Chrome?
curl -s http://127.0.0.1:9222/json/version

# ver la última captura que hizo el script
ls -l ~/.config/browser-harness/tmp/shot.png

# historial de reposts y deshacer
./xrepost.sh --history 20
ls -l ~/.local/state/xrepost/history.jsonl
```

Errores típicos:

| Síntoma | Causa | Solución |
|---|---|---|
| `chrome-not-running` | Chrome cerrado o sin puerto | Arrancarlo con `--remote-debugging-port=9222` |
| `Input.dispatchMouseEvent timed out` | Scroll por rueda en X | Ya evitado: el script usa `window.scrollBy` |
| `Sin posts en ese rango` | No hay posts, o la búsqueda no cargó | Probar el rango en el navegador a mano |
| `no se pudo confirmar` | Rate limit o fallo de red | Bajar `X_LIMIT`, subir `X_DELAY` |

---

## 10. Límites, riesgos y buenas prácticas

- **Esto automatiza acciones en tu cuenta.** Un fallo del script actúa sobre tu cuenta real, no sobre una copia.
- **Reglas de X:** el repost automatizado y masivo entra en sus políticas de automatización. Con pocos reposts, espaciados y sobre contenido propio o de cuentas que te autorizan, el riesgo es bajo; con cientos, la cuenta acaba limitada o suspendida.
- **Recomendaciones:** `X_LIMIT` entre 3 y 10, `X_DELAY` entre 20 y 60 s, y no ejecutarlo en bucle.
- **Sesión:** usa un perfil de Chrome dedicado (`~/.local/state/xrepost/chrome-profile`), no tu perfil personal con banca y correo.
- **Volumen alto:** el camino correcto es la API oficial (`POST /2/users/:id/retweets`), no el navegador.
- **Credenciales:** el script nunca las toca; aprovecha la sesión ya iniciada.
- **El historial no es un freno de seguridad.** Evita repetir lo ya hecho, pero no limita el volumen: `X_LIMIT` y `X_DELAY` siguen siendo la defensa principal.

---

## 11. Cómo extenderlo

| Idea | Dónde tocar |
|---|---|
| Citar con comentario en vez de repost | Tras abrir el menú, usar `[data-testid="quote"]` |
| Incluir respuestas | `X_SKIP_REPLIES=0` |
| Filtros con expresiones regulares | Cambiar `text_ok()` por `re.search` sobre `p["text"]` |
| Zona horaria configurable | Convertir `time` (UTC) a la zona local antes de comparar fechas |
| Notificar al terminar | Leer el historial o añadir un `curl` a un webhook al final de `main()` |
| Ejecución diaria | `cron` o `systemd --user` con `X_APPLY=1` y `--force` puntual |
| Versión con API oficial | OAuth 2.0 + `POST /2/users/:id/retweets` |
| Interfaz gráfica | Envolver `xrepost.sh` con `zenity` o una TUI |

---

## 12. Verificación realizada

Todo lo siguiente se probó con la cuenta real, dejándola sin cambios (donde se indica, con un DOM simulado):

1. **Dry-run** con `kubernetesio` (27-oct-2026): 2 posts listados con URL correcta.
2. **Dry-run** con `kubernetesio` (20→28-oct-2026): 5 posts, incluyendo el salto de día correcto.
3. **Ciclo completo de repost** sobre un post público: `retweet` 0 → 1 tras confirmar, captura guardada.
4. **Deshacer**: `unretweet` 1 → 0, dejando la cuenta como estaba.
5. **Persistencia de sesión**: la cuenta detectada fue la del perfil de Chrome usado (`@rignack_X`).
6. **Modo interactivo**: con entrada simulada se recorrieron usuarios, campo de fecha enmascarado y pregunta de alcance, y el wrapper exportó las variables esperadas.
7. **Caso real con retweet mezclado**: buscando a `@garcia_yec52416` (21→28-oct-2026) la búsqueda devolvía 3 posts suyos y 1 retweet de otra cuenta; el filtro `X_SKIP_RETWEETS` descartó el retweet y dejó los 3 propios.
8. **Filtro por handle, no por texto**: ese retweet se descartó porque su autor (`@ManuelMilian9`) no coincide con el usuario buscado, sin depender de que la interfaz diga "reposted".
9. **Deduplicación global**: con `X_SKIP_RETWEETS=0 ./xrepost.sh garcia_yec52416,ManuelMilian9 21/10/2026 28/10/2026`, el post retuiteado apareció una sola vez pese a salir en las dos búsquedas.
10. **Respuestas por DOM**: buscando a `@ETECSA_Cuba` (25→28-oct-2026) se listaron solo los posts originales; las respuestas (una con tres menciones en la línea "Replying to") quedaron fuera sin mirar el idioma.
11. **Ayuda**: `./xrepost.sh --help` muestra el bloque completo de variables y ya no imprime la línea `set -euo pipefail`.
12. **Filtros de texto y exportación** (dry-run real): `X_MATCH="zzzz-no-existe"` descartó los 2 posts y dejó el CSV solo con cabecera; sin filtro, `--csv` y `--md` guardaron los 2 posts con estado `solo listado`.
13. **Historial, idempotencia y deshacer** (DOM simulado, sin tocar la cuenta): repostar → repetir la ejecución (0 acciones) → `--undo-last` → `--undo` por ID → `--force`. Se comprobó que no duplica, que tras deshacer el post vuelve a estar disponible y que `--undo-last` no revierte un `ya estaba reposteado` ajeno.
14. **Modos sin navegador**: `--history` lee el JSONL y sale sin abrir Chrome; `--undo-last` sin candidatos tampoco navega.
15. **Fechas con avance automático** (entrada simulada): `20102026` se mostró como `20/10/2026`; Enter tomó el valor entre corchetes; `40022026` y `30/02/2026` se rechazaron con aviso y se volvió a pedir; un rango invertido reabrió ambas fechas. Por argumentos se aceptan `20/10/2026` y `2026-10-20`.
16. **Pregunta de alcance** (entrada simulada): opción 1 → `X_SKIP_RETWEETS=1`; opción 2 → `0`; Enter → `1`; con `X_SKIP_RETWEETS=0` ya definida no se preguntó y se informó del alcance.
17. **Autocompletado de cuentas** (entrada simulada con PTY): se sembraron cuentas, se escribió un prefijo, se eligió con `↓`/`Enter`, se completó con `Tab`, se encadenaron dos cuentas y se canceló con `Ctrl-C`; el valor devuelto fue el esperado y `accounts.json` se actualizó. Las pruebas de ranking cubren coincidencia exacta, prefijo, subcadena, recencia, frecuencia y exclusión de cuentas ya usadas en el mismo campo.
17. **Validación sin interacción**: `./xrepost.sh u1 40/13/2026` termina con «Fecha no válida» y código 1, sin abrir Chrome.
18. **Resumen de alcance**: la cabecera de cada ejecución muestra `alcance: solo publicaciones originales | respuestas: omitidas` (o la variante elegida).
19. **Repost con cita (cuenta real)**: se publicó una cita del post de `@Docker` sobre Docker Sandboxes (28/10/2026) con el comentario `#Docker` desde `@rignack_X`; la ejecución terminó con `citado con comentario`, el historial guardó `quoted` y la cita se verificó en el perfil. Antes, el dry-run con `--quote "#ETECSA"` mostró `comentario de la cita: #ETECSA`, devolvió los 2 posts con fechas DD/MM/AAAA y no publicó nada.
20. **Autocompletado de hashtags (panel real)**: el campo bajo «Cuentas» sugirió los hashtags usados, excluyó los ya escritos en el mismo campo, aceptó la elección con `↓`/`Enter` y añadió el espacio para el siguiente; `ETECSA, cuba` se normalizó a `#ETECSA #cuba` y un comentario sin hashtags válidos se rechazó con aviso.
21. **Pruebas automáticas**: 40 pruebas del panel (31 de la API web —incluye `/api/hashtags`, `/api/accounts/clear`, `/api/hashtags/clear`, validación de la cita, selección parcial y progreso en el snapshot— y 9 del motor con la lista exacta), 8 de hashtags, 7 de cuentas y 12 de historial. En conjunto: `python3 -m pytest -q` → **67 pruebas + 18 subpruebas**.
22. **Mejoras de la interfaz (Chrome headless real, motor simulado)**: se condujo el panel por CDP y se verificaron con capturas — vista previa de la cita con contador 280, error de fecha visible y accesible (`aria-invalid`), casillas por publicación con «Seleccionar todo / nada», conteo y nota de selección, filtro y orden del listado, diálogo de confirmación con conteo real (`3 de 3 seleccionadas (4 revisadas)`) y duración estimada, barra de progreso «X de Y» con estados por fila en vivo y log abierto, resultado final exacto, historial con el comentario de la cita y filtro, formulario recordado tras recarga, **reconexión a un trabajo en curso tras recargar**, deshacer con detalle de la tanda y N opcional (deshizo solo 1 de 3) y tarjetas en vista móvil (390 px).

Capturas de esas pruebas: `~/Downloads/demo-5-x-home.png`, `~/Downloads/demo-6-repost-test.png`.

---

## 13. Preguntas frecuentes

**¿Necesito la API de X?**
No. Se usa el navegador con tu sesión.

**¿Necesito un modelo de IA o una clave de OpenAI/Anthropic?**
No. Ver [sección 3.1](#31-hace-falta-un-modelo-de-ia): el programa no llama a ningún modelo, solo controla Chrome por CDP.

**¿Puedo repostear de varias cuentas a la vez?**
Sí: `./xrepost.sh cuenta1,cuenta2,cuenta3 27/10/2026`.

**¿Qué pasa si un post ya estaba reposteado?**
Se detecta y se salta; no se duplica ni se deshace. Si ya consta en el historial, ni siquiera se vuelve a abrir.

**¿Puedo deshacer un repost?**
Sí: `./xrepost.sh --undo-last` deshace la última tanda y `./xrepost.sh --undo URL|ID`, uno concreto. Solo revierte reposts hechos por la herramienta, no los que ya estaban antes.

**¿Dónde se guarda el historial? ¿Puedo borrarlo?**
En `~/.local/state/xrepost/history.jsonl`. Bórralo (o cambia `X_HISTORY`) si quieres que la herramienta olvide lo que ya reposteó; no afecta a lo que hay en tu cuenta.

**¿Cómo reposteo solo los posts que hablan de un tema?**
Con `X_MATCH="kubernetes,cloud"` (debe contener alguna) y/o `X_EXCLUDE="empleo,oferta"` (descarta si contiene alguna).

**¿Puedo repostear posts de fechas muy antiguas?**
Sí, mientras la búsqueda de X los devuelva. X limita la profundidad del histórico; si no aparecen, no están indexados para búsqueda.

**¿Funciona con cuentas protegidas?**
Solo si tu sesión ya las sigue; si no, no aparecerán en la búsqueda.

**¿Por qué no aparecen algunos de sus posts?**
Los retweets de otras cuentas y las respuestas se ignoran por defecto. En modo interactivo puedes incluir los retweets eligiendo la opción 2; para las respuestas, `X_SKIP_REPLIES=0`.

**Me equivoqué al escribir la fecha, ¿tengo que reiniciar?**
No: el campo se valida al octavo dígito. Si la fecha no existe o el rango está invertido, vuelve a pedirla. Durante la escritura, la tecla de borrado elimina el último dígito.

**¿Se puede programar?**
Sí, con `cron` o `systemd --user`, siempre con `X_LIMIT` bajo.

**¿Dónde está el límite de "demasiado"?**
Cuando X empieza a mostrar `no se pudo confirmar` de forma repetida. Ahí hay que parar y bajar el ritmo.
