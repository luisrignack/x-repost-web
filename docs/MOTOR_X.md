# Motor de X

El motor vive en `xrepost.py` y se ejecuta dentro del harness de `browser-use`,
que lee el script por `stdin`. Por eso no tiene `__file__`: `xrepost.sh`
exporta `X_SELF_DIR` para que pueda importar los módulos compartidos
(`xrepost_labels`, `xrepost_history`, `xrepost_cdp`).

## 1. Principios

1. **Verificar, no asumir.** Una acción solo se marca como hecha si la
   interfaz muestra el estado esperado.
2. **Lo desconocido no es éxito ni fallo reintentable.** Un resultado incierto
   se registra como `unconfirmed` y no se vuelve a intentar sin `--force`.
3. **Detenerse ante un bloqueo.** Captcha, sesión caducada, límite de
   solicitudes o cuenta suspendida detienen la tanda.
4. **No inventar datos.** Si un selector no aparece, se devuelve un código de
   fallo concreto; no se rellena el historial con un éxito supuesto.

## 2. Flujo

```
validar entorno
  ↓
por cada cuenta:
  buscar (from:usuario since:… until:…)
  leer artículos y filtrar
  ↓
unir, deduplicar y aplicar historial
  ↓
si APPLY:
  por cada publicación:
    abrir, comprobar página
    repost o cita
    verificar
    registrar evento
  ↓
si no APPLY:
  listar y exportar
```

## 3. Búsqueda

La consulta es:

```
https://x.com/search?q=from:<usuario> since:<desde> until:<día_siguiente>&f=live
```

- `until` es exclusivo en X, por eso se suma un día.
- Se leen hasta 8 páginas de scroll por cuenta y se corta al superar 40
  resultados.
- Se deduplica por URL y globalmente entre cuentas (`SEEN`).
- Se descartan respuestas y retweets según `X_SKIP_REPLIES` y
  `X_SKIP_RETWEETS`.
- Los retweets detectados se descartan comparando el autor del artículo con la
  cuenta buscada.

## 4. Filtros

`post_ok()` aplica, en orden:

| Filtro | Variable | Comportamiento |
| --- | --- | --- |
| Palabras incluidas | `X_MATCH` | Debe contener alguna. |
| Palabras excluidas | `X_EXCLUDE` | Si contiene alguna, se descarta. |
| Coincidencia exacta | `X_EXACT` | Compara palabras completas. |
| Idioma | `X_LANG` | Usa el atributo `lang` del texto. |
| Multimedia | `X_MEDIA` | `yes` exige imagen/vídeo; `no` lo prohíbe. |
| Vídeo | `X_VIDEO` | `yes`/`no`. |
| Tipo | `X_KIND` | `original`, `reply`, `retweet`. |
| Longitud | `X_MIN_LEN`, `X_MAX_LEN` | Sobre el texto normalizado. |
| Regex incluye | `X_INCLUDE_REGEX` | Debe coincidir. |
| Regex excluye | `X_EXCLUDE_REGEX` | Si coincide, se descarta. |
| Hashtags | `X_HASHTAGS_FILTER` | Debe contener alguno. |

Las expresiones regulares se validan con `_regex_safe()`:

- Longitud máxima 200.
- Se rechazan grupos repetidos (`(a+)+`) y repeticiones `{n}` con `n > 100`.
- Si la expresión no compila, se ignora con un aviso (no se bloquea la
  ejecución).

## 5. Verificación de repost

```python
goto_url(url)
wait_for_load()
problem = page_guard()          # captcha, sesión, límite, suspendida
if problem: return problem
if N_UNRETWEET > 0: return "already"
if N_RETWEET == 0: return "no_button"
click(retweet)
if not confirm_menu: return "no_menu"
click(retweetConfirm)
if N_UNRETWEET > 0: return "reposted"
problem = page_guard()
return problem or "unconfirmed"
```

La única prueba de éxito es que aparezca el botón `unretweet` (estado
"reposteado"). Si no aparece, el resultado es incierto, nunca `reposted`.

## 6. Verificación de cita

1. Abre el menú de repost y elige "Citar".
2. Espera al editor; si no aparece → `no_composer`.
3. Escribe el comentario (hashtags normalizados).
4. Espera a que el botón de publicar se habilite; si no → `quote_failed`.
5. Pulsa publicar y espera a que el editor se cierre.
6. Solo el toast con enlace al post nuevo confirma la cita → `quoted`.
7. Sin toast → `quote_unverified`.

Una cita no confirmada no se reintenta automáticamente porque podría duplicar
la publicación.

## 7. Deshacer

```python
goto_url(url)
if N_UNRETWEET == 0: return "not_reposted"
click(unretweet)
if confirm_dialog: click(unretweetConfirm)
elif still_unretweet: return "undo_failed"
if N_UNRETWEET == 0: return "undone"
return "undo_failed"
```

`run_undo()` selecciona candidatos del historial:

- `--undo URL|ID`: una publicación concreta.
- `--undo-last [N]`: los N reposts confirmados más recientes de la última
  tanda.
- Solo considera eventos `reposted` cuyo último estado sigue vigente.

## 8. Guardia de página

`PAGE_PROBLEM_JS` inspecciona la columna principal y devuelve:

| Código | Texto detectado | Resultado |
| --- | --- | --- |
| `login` | "iniciar sesión", "log in" | `session_expired` |
| `captcha` | "verifica que eres humano", "captcha" | `captcha` |
| `rate_limited` | "rate limit", "too many requests" | `rate_limited` |
| `suspended` | "account suspended", "temporarily restricted" | `suspended` |
| `unavailable` | "post is unavailable", "algo salió mal" | `page_unavailable` |

Los cuatro primeros son `FATAL_RESULTS`: se detiene la tanda entera. El último
solo afecta a esa publicación.

## 9. Historial

Cada acción genera un evento:

```json
{
  "ts": "2026-11-18T10:00:00+00:00",
  "run": "20261118T100000Z",
  "action": "repost",
  "result": "reposted",
  "id": "1234567890",
  "url": "https://x.com/foo/status/1234567890",
  "user": "foo",
  "search_user": "foo",
  "author": "Foo",
  "text": "…",
  "date": "2024-01-01",
  "quote": ""
}
```

- `save_event()` usa `xrepost_fs.append_line()` (atómico y 0600).
- Se rota el archivo al superar `XREPOST_HISTORY_MAX_BYTES`.
- Las líneas corruptas se ignoran al leer, pero se conservan.
- `history_state()` calcula qué está reposteado y qué se puede deshacer.

## 10. Deduplicación e idempotencia

Antes de ejecutar, `_filter_history()` elimina:

- Publicaciones ya reposteadas (`skipped_history`).
- Publicaciones con un intento incierto (`skipped_uncertain`), salvo
  `--force`.

El panel puede enviar `X_ONLY_URLS_FILE` con la lista exacta aprobada, de modo
que entre previsualización y ejecución no se vuelve a buscar ni se amplía el
conjunto.

## 11. Pestaña propia

El motor puede abrir una pestaña dedicada (`use_own_tab()`), registrada para
cerrarse al terminar. Esto evita interferir con la pestaña que el usuario esté
usando y permite que el modal de cita se monte correctamente.

## 12. Errores y salida

- Código `0`: ejecución completada.
- Código `1`: validación o error de entorno.
- Código `2`: argumento numérico inválido.

Cada publicación imprime una línea:

```
  <resultado>: <url>
```

El panel la interpreta con `PROGRESS_RE`. Las líneas no reconocidas se guardan
en el log del trabajo.

## 13. Cómo adaptarse a cambios de X

Los selectores están en `xrepost_selectors.py`:

- Se prefieren `data-testid` y atributos semánticos.
- Hay alternativas para textos en inglés y español.
- `xrepost.py` conserva una copia mínima si el módulo no está disponible.
- Las pruebas de `web/test_engine_selected.py` verifican las sondas sin abrir
  Chrome.

Si X cambia un selector:

1. Reproduce el fallo con una publicación de prueba.
2. Actualiza `SELECTORS` o la sonda JS.
3. Ejecuta `python3 -m pytest -q`.
4. Verifica manualmente con una cuenta de prueba.

## 14. Limitaciones conocidas

- Depende de la interfaz web de X; no usa la API oficial.
- No puede garantizar el resultado si X responde con latencia extrema: en ese
  caso devuelve `unconfirmed`.
- No reintenta automáticamente resultados inciertos.
- Requiere una sesión válida en el perfil de Chrome.
- El límite de 10 cuentas y 50 reposts por ejecución es deliberado.
