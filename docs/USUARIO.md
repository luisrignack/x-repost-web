# Guía de usuario

## 1. Qué hace xrepost

Busca publicaciones de cuentas concretas de X en un rango de fechas, las
muestra para revisión y, si lo confirmas, las repostea o las cita con un
comentario. También puede deshacer reposts y mantener un historial verificable.

**Nada se publica sin tu confirmación.** La previsualización es siempre el
primer paso y la programación solo ejecuta previsualizaciones.

## 2. Arrancar

```bash
./iniciar.sh
```

Se abre el panel en el navegador. Si no se abre, usa el enlace guardado:

```bash
cat ~/.local/state/xrepost/panel-url
```

Para parar:

```bash
./iniciar.sh --stop
```

## 3. La pantalla

La cabecera muestra el estado de la sesión y un botón para cambiar entre tema
claro y oscuro. Debajo hay ocho pestañas:

| Pestaña | Para qué |
| --- | --- |
| **Buscar** | Elegir cuentas, fechas, filtros y revisar resultados. |
| **Bandeja** | Revisar, aprobar o rechazar publicaciones y ejecutar. |
| **Cuentas** | Ver cuentas usadas, alias, favoritos y grupos. |
| **Filtros** | Guardar y cargar perfiles de filtros. |
| **Programación** | Crear búsquedas que se ejecutan solas (solo previsualización). |
| **Historial** | Ver qué se publicó, deshacer y diagnosticar. |
| **Estadísticas** | Confirmaciones, fallos, actividad y tendencia. |
| **Sistema** | Motor, Chrome, CDP, red, backups y diagnóstico. |

## 4. Buscar y repostear

### 4.1 Rellenar la búsqueda

1. Escribe una o varias cuentas separadas por comas (`@foo, @bar`). Puedes
   elegir una cuenta recordada de la lista.
2. Indica las fechas `DD/MM/AAAA`. El campo se completa solo con las barras.
3. Opcional: elige un perfil de filtros o ajusta los filtros manualmente.
4. Pulsa **Previsualizar**.

La tabla muestra autor, fecha, texto y estado. El resumen indica cuántas
publicaciones hay y de qué cuentas.

### 4.2 Revisar

- Puedes desmarcar publicaciones concretas.
- El botón **Repostear seleccionadas** solo se activa cuando la
  previsualización ha terminado correctamente.
- Al pulsarlo se abre un diálogo con el resumen: cuentas, fechas, cita,
  alcance, número de publicaciones, pausa y duración estimada.

### 4.3 Confirmar

Marca la casilla de confirmación y pulsa **Repostear**. La ejecución muestra el
estado de cada publicación:

- `reposteado` o `citado con comentario`: confirmado.
- `no se pudo confirmar`: no se sabe si se publicó. **No se reintenta solo.**
- `ya estaba reposteado`: no se hizo nada.
- Un bloqueo de X (`sesión caducada`, `captcha`, `límite`) detiene la tanda.

Si algo queda sin confirmar, revisa tu perfil de X antes de volver a intentar.

### 4.4 Citas

Escribe un comentario en el campo de cita. Cada palabra se normaliza a hashtag:
`ETECSA, cuba` → `#ETECSA #cuba`. Los hashtags usados quedan sugeridos para la
próxima vez.

## 5. Bandeja de revisión

Cada previsualización añade sus publicaciones a la bandeja como **pendientes**.

- **Aprobar**: se ejecutará si lanzas la bandeja.
- **Rechazar**: se conserva con el motivo para auditoría.
- **Repostear aprobadas**: lanza una ejecución solo con las aprobadas.

Estados: `pendiente`, `aprobada`, `rechazada`, `en cola`, `ejecutada`,
`verificada`, `sin confirmar`, `fallida`.

Puedes filtrar por estado o buscar por texto, cuenta o URL. También importar un
archivo JSON con publicaciones.

## 6. Cuentas y grupos

- La pestaña **Cuentas** lista las cuentas usadas, con su actividad.
- Puedes poner un alias (`@foo` → "Medios") y marcarla como favorita.
- Los **grupos** agrupan cuentas para reutilizarlas en una búsqueda.
- Los grupos se pueden importar desde texto (`handle;alias` por línea) y
  exportar a CSV o JSON.

## 7. Perfiles de filtros

Un perfil guarda un conjunto de filtros con nombre. Puedes:

- Crear, editar, duplicar y borrar perfiles.
- Validar los filtros antes de guardar.
- Importar y exportar perfiles en JSON.
- Aplicar un perfil a una búsqueda.

Filtros disponibles: palabras incluidas/excluidas, expresiones regulares,
idioma, presencia de multimedia, tipo (original, respuesta, retweet),
longitud mínima/máxima y coincidencia exacta.

## 8. Programación

Crea una programación con nombre, frecuencia (`una vez`, `diaria`, `semanal`,
`mensual`) y fecha de inicio. Las programaciones:

- Solo ejecutan **previsualizaciones**; nunca publican.
- Añaden los resultados a la bandeja.
- Se pueden ejecutar a mano, pausar o borrar.

Si el panel está cerrado a la hora prevista, la programación se ejecuta al
volver a arrancar si sigue vencida.

## 9. Historial y deshacer

La pestaña **Historial** muestra los eventos: reposts, citas, deshacer y
resultados. Puedes:

- **Deshacer la última tanda**: revierte los reposts confirmados de la última
  ejecución.
- **Deshacer uno**: revierte una publicación concreta.
- **Diagnosticar**: cuenta líneas corruptas y verifica el archivo.
- **Exportar**: CSV, Markdown, JSON, HTML o PDF.

Deshacer también se verifica: si no se puede confirmar, se muestra como fallo y
no se marca como deshecho.

## 10. Estadísticas

Las cifras salen del historial real:

- Confirmados (reposts + citas).
- Reposts, citas y deshechos.
- Sin confirmar y fallos, por separado.
- Tasa de confirmación con el denominador visible.
- Actividad por cuenta y por día.

Un resultado desconocido nunca cuenta como éxito.

## 11. Sistema

- **Red**: modo directo, PAC o proxy; relanzar Chrome.
- **Sesión**: caducidad, rotaciones, cerrar sesión.
- **Diagnóstico**: motor, Chrome, CDP, historial, permisos.
- **Backups**: crear una copia del historial o del estado completo y restaurar
  una copia verificada.

## 12. Atajos y accesibilidad

- `Tab` recorre los controles; el foco es siempre visible.
- `Esc` cierra los diálogos.
- El enlace "Saltar al contenido" aparece al enfocar con `Tab`.
- Los temas claro y oscuro respetan `prefers-reduced-motion`.
- Los mensajes de estado usan regiones `aria-live`.

## 13. Buenas prácticas

1. Revisa siempre la previsualización antes de ejecutar.
2. No ejecutes tandas largas sin supervisión.
3. Deja una pausa entre reposts (20 s por defecto).
4. Si X pide captcha o cierra la sesión, detente y resuélvelo a mano.
5. Haz backups antes de cambios importantes.
6. No compartas el enlace del panel ni el perfil de Chrome.

## 14. Problemas frecuentes

| Problema | Solución |
| --- | --- |
| "Panel bloqueado" | Abre el enlace de `panel-url` o reinicia `iniciar.sh`. |
| "La sesión de X caducó" | Inicia sesión en la ventana de Chrome de xrepost. |
| "No encontré el botón de repost" | X cambió la interfaz o la publicación no permite repost. Revisa el diagnóstico. |
| "No se pudo confirmar" | Revisa tu perfil antes de reintentar; no se reintenta solo. |
| "Los datos cambiaron desde la previsualización" | Vuelve a previsualizar con los mismos filtros. |
| Chrome no responde | `./iniciar.sh --stop` y vuelve a arrancar. |
| El panel no carga | Comprueba `./iniciar.sh --status` y el puerto. |
