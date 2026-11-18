# xrepost · panel web local

Panel para previsualizar, repostear y deshacer desde una interfaz web, usando el
mismo motor que el CLI (`xrepost.sh` + `xrepost.py`). Vive en la rama `web-ui`
y en su propia carpeta (`web/`); la rama `main` sigue siendo solo CLI.

## Requisitos

- Python 3.10 o superior (solo biblioteca estándar; no hay que instalar nada).
- Chrome con la sesión de X iniciada y el endpoint CDP que ya usa el CLI
  (`BU_CDP_URL`, por defecto `http://127.0.0.1:9222`).
- `xrepost.sh` y `xrepost.py` en la raíz del repositorio.

## Arranque

Desde la raíz del worktree:

```bash
./web/run.sh
```

o directamente:

```bash
python3 web/app.py
```

El servidor escucha **solo en `127.0.0.1`**, genera un token aleatorio y abre el
panel en una ventana de Chrome aparte. La terminal muestra el enlace completo:

```text
Panel: http://127.0.0.1:8765/?token=…
```

Opciones útiles:

```bash
python3 web/app.py --no-open          # no abrir el navegador
python3 web/app.py --port 9000        # puerto concreto (0 = aleatorio)
python3 web/app.py --verbose          # registrar peticiones HTTP
python3 web/app.py --token mi-token   # token fijo (solo para pruebas locales)
```

También se puede cambiar el motor, el historial, las cuentas recordadas y la
carpeta de ejecuciones:

```bash
python3 web/app.py --engine ./xrepost.sh \
  --history ~/.local/state/xrepost/history.jsonl \
  --accounts ~/.local/state/xrepost/accounts.json \
  --hashtags ~/.local/state/xrepost/hashtags.json \
  --runs ./web/.runs
```

## Autocompletado de cuentas

El campo **Cuentas** sugiere las cuentas usadas antes, tanto desde el panel como
desde el CLI. Las coincidencias se actualizan al escribir, se ordenan por
coincidencia (exacta, prefijo, subcadena), uso reciente y frecuencia, y se
pueden elegir con el ratón o con el teclado:

- `↑` / `↓` mueven la selección.
- `Enter` acepta la sugerencia resaltada.
- `Tab` completa la cuenta resaltada y añade una coma para la siguiente.
- `Esc` cierra el desplegable.

Las cuentas se guardan en `~/.local/state/xrepost/accounts.json` (o en la ruta
de `X_ACCOUNTS` / `--accounts`), junto al historial. El panel registra la cuenta
en cuanto se previsualiza una búsqueda y reutiliza el mismo archivo que el CLI.
Al arrancar, el servidor lo indica en la línea `Cuentas:`. La **papelera** a la
derecha del campo borra el historial de cuentas guardadas (con confirmación):
las sugerencias quedan vacías y las cuentas solo vuelven a aparecer cuando se
usan de nuevo. El borrado también descarta los eventos anteriores del historial
JSONL que alimentaban el autocompletado.

## Repost con cita y autocompletado de hashtags

El campo **Hashtag de la cita**, justo debajo de «Cuentas», es opcional. Si
escribes algo, cada repost de esa tanda se publica como **cita** con ese
comentario; si lo dejas vacío, el repost es normal. Cada palabra se convierte en
hashtag y se quitan los duplicados: `ETECSA, cuba` se envía como
`#ETECSA #cuba`. Un texto que no produzca ningún hashtag se rechaza con aviso.
Debajo del campo, una **vista previa en vivo** muestra el comentario ya
normalizado (`#ETECSA #cuba`) y su longitud sobre el límite de 280 caracteres
de X, para que no haya sorpresas al confirmar.

Igual que las cuentas, los hashtags usados se recuerdan y se sugieren al
escribir (mismo teclado: `↑`/`↓`, `Enter`, `Tab`, `Esc`). El panel registra los
hashtags al previsualizar y el CLI al ejecutar con `--quote`; el archivo es
`~/.local/state/xrepost/hashtags.json` (o `X_HASHTAGS` / `--hashtags`). Al
arrancar, el servidor lo indica en la línea `Hashtags:`. La **papelera** a la
derecha del campo borra el historial de hashtags guardados (con confirmación):
las sugerencias quedan vacías y un hashtag solo reaparece cuando se vuelve a
usar en una cita.

Una cita cuenta como acción hecha: no se repite en ejecuciones posteriores,
pero `--undo` no intenta deshacerla (X no ofrece «quitar cita» como sí ofrece
«quitar repost»).

## Flujo

Las fechas del panel se escriben en formato **DD/MM/AAAA** (las barras se
insertan solas al teclear los 8 dígitos). El icono de calendario de cada campo
abre el selector nativo del navegador y vuelca la fecha elegida en ese mismo
formato. Mientras se escribe se rechazan días mayores que 31 y meses mayores
que 12, y al completar la fecha se comprueba el calendario y el rango
2006–2100. Una fecha imposible no solo se marca en rojo: aparece un **mensaje
de error debajo del campo** (p. ej. «El 31/02/2024 no existe»), enlazado con
`aria-describedby` y `aria-invalid` para que también lo anuncie un lector de
pantalla, y el panel no deja buscar hasta corregirla. Después el panel las
convierte a ISO antes de llamar a la API, porque el motor y el historial siguen
trabajando en ISO; el listado y el historial se muestran de vuelta en
DD/MM/YYYY.

1. **Previsualizar**: busca publicaciones con el mismo motor del CLI. No toca la
   cuenta; genera un listado y archivos CSV/Markdown descargables.
2. **Revisar y elegir**: cada fila del listado tiene una **casilla** (marcada por
   defecto) y la cabecera ofrece «Seleccionar todo / nada». El contador indica
   cuántas van («3 seleccionadas») y la nota del botón recuerda la elección
   («3 de 4 publicaciones seleccionadas»). Se puede **filtrar por texto** y
   **ordenar** por fecha (más recientes o más antiguas primero) o por cuenta
   (A–Z); filtrar y ordenar no alteran la selección. En pantallas estrechas la
   tabla se convierte en tarjetas apiladas.
3. **Repostear o citar**: solo se habilita tras una previsualización completada
   y con al menos una casilla marcada. El diálogo de confirmación muestra el
   **conteo real** que se publicará —`min(límite, seleccionadas)`, con el total
   revisado como contexto—, la **duración estimada** según la pausa configurada
   y el comentario exacto de la cita. Exige marcar «Entiendo que se repostearán
   publicaciones en mi cuenta real…» y una pausa mínima de 5 s.
4. **Progreso en vivo**: durante el apply, cada fila cambia su etiqueta de
   estado (`pendiente` → `reposteado` / `citado con comentario` / error), una
   barra muestra «X de Y» y el log se abre solo para seguir la ejecución.
5. **Historial**: muestra el último estado de cada publicación y el comentario
   de la cita cuando lo hubo. Se puede **filtrar por texto** y enseña 40
   entradas con un botón «Cargar más» que amplía de 40 en 40 hasta 200. Permite
   deshacer un repost concreto.
6. **Deshacer última tanda**: el diálogo enseña **cuántos reposts se desharán y
   cuáles** (cuenta y fecha, hasta 6 y «… y N más») y acepta un número opcional
   para revertir solo los últimos N reposts vigentes.

La aplicación repostea **exactamente las publicaciones marcadas** del listado
previsualizado, no vuelve a buscar en X entre la vista previa y la confirmación.
Para ello el panel guarda el listado revisado y el motor lo consume mediante
`X_ONLY_URLS_FILE` (uso interno del panel; el CLI normal no lo necesita).

### Sobrevivir a una recarga

El formulario (cuentas, fechas, alcance, límite, pausa, filtros y cita) se
guarda en `localStorage` y se recupera al volver a abrir el panel. Si la página
se recarga **mientras hay un trabajo en curso** —una búsqueda o un apply—, el
panel lo reconecta solo: recupera el identificador guardado en `sessionStorage`,
vuelve a mostrar el progreso y adopta el resultado cuando termina. Recargar no
repostea nada dos veces: el trabajo sigue siendo el mismo en el servidor.

## Seguridad

- Escucha solo en `127.0.0.1`; no lo expongas a la red.
- Token obligatorio en la URL, en cookie `HttpOnly`/`SameSite=Lax` o en la
  cabecera `X-Token`.
- Comprueba `Host` y `Origin` para bloquear peticiones de otros orígenes.
- Una sola ejecución a la vez (Chrome es una única sesión).
- Aplicar requiere `confirm: true`, una previsualización completada con los
  mismos parámetros y al menos 5 s de pausa. La selección (`selected_urls`) se
  valida en el servidor: solo admite URLs de esa previsualización y como mínimo
  una; de ella se genera el `selected.json` que consume el motor.
- El servidor no guarda contraseñas ni cookies de X: usa la sesión de Chrome.

## Navegador separado

El panel se abre con un perfil propio en
`~/.cache/xrepost-web/panel-profile`. Así no comparte pestaña ni proceso con la
instancia de Chrome que controla `browser-use` en el puerto 9222. Si usas el
mismo perfil, una ejecución puede navegar fuera del panel.

Dentro de esa instancia, el motor abre su **propia pestaña** (`about:blank`) al
empezar, navega solo ahí y la cierra al terminar o al cancelar el trabajo (el
panel cancela con `SIGTERM`). Las pestañas que dejes abiertas en ese Chrome no
se mueven; solo si el proceso muere de golpe (`SIGKILL`) puede quedar la
pestaña del motor abierta.

## Pruebas

Las pruebas usan un motor simulado: no abren Chrome, no acceden a X y no tocan
el historial real.

```bash
cd web
python3 -m unittest -v
```

Son **40 pruebas**: 31 de la API web (`test_app.py`) y 9 del motor con la lista
exacta (`test_engine_selected.py`). Comprueban autenticación, comprobaciones de
`Host`/`Origin`, validación de fechas y parámetros (incluido el comentario de la
cita), previsualización, exportaciones, confirmación, **selección parcial**
(subconjunto válido, URLs ajenas rechazadas, selección vacía rechazada), lista
exacta aplicada, **progreso en vivo** (`progress.done/total` en el snapshot),
historial con cita, deshacer, bloqueo de una sola ejecución, cancelación,
sugerencias de cuentas y de hashtags (registro al previsualizar, ranking y
exclusión) y que `X_QUOTE` llega al motor.

Además, la interfaz se verificó de punta a punta en **Chrome headless real**
con el mismo motor simulado (vía CDP): vista previa de la cita, errores de
fecha accesibles, casillas y selección parcial, filtro y orden, diálogo de
confirmación con conteo y duración, barra de progreso y estados por fila en
vivo, historial con la cita, formulario recordado tras recarga, reconexión a un
trabajo en curso, deshacer con detalle de la tanda y N opcional, filtro del
historial y tarjetas en móvil.

## Límites actuales

- La selección es post a post, pero el máximo indicado (1–50) sigue acotando
  cuántas se publican: se aplican las primeras `min(límite, seleccionadas)` del
  listado revisado.
- El historial es el mismo JSONL del CLI
  (`~/.local/state/xrepost/history.jsonl`); el panel solo deshace lo que la
  herramienta registró como suyo.
- El panel no sustituye al CLI: lo invoca como subproceso. Los valores por
  defecto siguen siendo conservadores (dry-run salvo confirmación, retweets y
  respuestas omitidos).
- La cita se publica con el comentario de hashtags indicado; no admite texto
  libre ni imágenes.

## Mantener la rama al día

`main` no se toca. Para traer cambios del CLI a `web-ui`:

```bash
git checkout web-ui
git merge main
```

Si hay conflictos en `xrepost.py`, conserva la carga de `X_ONLY_URLS_FILE` y el
resto de cambios del CLI.
