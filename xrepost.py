"""
xrepost — descubre posts de usuarios concretos en un rango de fechas y,
opcionalmente, los repostea desde la sesión de Chrome controlada por browser-use.

Variables de entorno (las pone xrepost.sh):
  X_USERS   lista separada por comas: "usuario1,usuario2"  (@ opcional)
  X_FROM    fecha inicial YYYY-MM-DD
  X_TO      fecha final   YYYY-MM-DD (incluida)
  X_APPLY   0 = solo listar (dry-run) | 1 = repostear
  X_LIMIT   máximo de reposts por ejecución (default 10)
  X_DELAY   segundos entre reposts (default 20)
  X_SKIP_REPLIES 1 = ignorar respuestas (default 1)
  X_SKIP_RETWEETS 1 = ignorar retweets (default 1)
  X_MATCH   palabras que debe contener el post, separadas por comas (opcional)
  X_EXCLUDE palabras que descartan el post, separadas por comas (opcional)
  X_QUOTE   comentario del repost con cita; cada palabra se vuelve un hashtag
            ("#ETECSA" o "ETECSA, cuba" -> "#ETECSA #cuba"). Vacío = repost
  X_FORCE   "1" = ignorar el historial y volver a procesar lo ya reposteado
  X_HISTORY ruta del historial JSONL
  X_CSV     exportar el listado a CSV
  X_MD      exportar el listado a Markdown
  X_MODE    repost (default) | undo | undo_last
  X_ONLY_URLS_FILE  JSON con el listado exacto a repostear (uso interno del
                    panel web: evita volver a buscar entre preview y apply)
"""

import atexit
import csv
import json
import os
import re
import signal
import sys
import threading
import time
import datetime as dt
from urllib.parse import quote, urlparse


def _env_num(name, default, cast):
    raw = os.environ.get(name, "").strip() or str(default)
    try:
        return cast(raw)
    except ValueError:
        print(f"{name} no es un número válido: '{raw}'")
        sys.exit(2)


def _regex_safe(pattern, field):
    """Compila una expresión regular con límites (mitiga retroceso catastrófico).

    Python no permite cancelar un ``re`` en curso; por eso se rechazan las
    construcciones que suelen bloquear el hilo y se limita la longitud. El
    texto de cada publicación está acotado a 5000 caracteres.
    """
    text = str(pattern or "").strip()
    if not text:
        return None
    if len(text) > 200:
        print(f"  aviso: {field} supera 200 caracteres; se ignora")
        return None
    if re.search(r"\((?:[^)]*[+*][^)]*)\)\s*[+*]", text) or re.search(r"\([^)]*\|[^)]*\)\s*[+*]", text):
        print(f"  aviso: {field} tiene grupos repetidos (riesgo de bloqueo); se ignora")
        return None
    for match in re.finditer(r"\{\s*(\d+)", text):
        if int(match.group(1)) > 100:
            print(f"  aviso: {field} repite demasiadas veces; se ignora")
            return None
    try:
        return re.compile(text, re.IGNORECASE | re.UNICODE)
    except re.error as exc:
        print(f"  aviso: {field} no es válida ({exc}); se ignora")
        return None


USERS = [u.strip().lstrip("@") for u in os.environ.get("X_USERS", "").split(",") if u.strip()]
D_FROM = os.environ.get("X_FROM", "")
D_TO = os.environ.get("X_TO", "") or D_FROM
APPLY = os.environ.get("X_APPLY", "0") == "1"
LIMIT = _env_num("X_LIMIT", 10, int)
DELAY = _env_num("X_DELAY", 20, float)
SKIP_REPLIES = os.environ.get("X_SKIP_REPLIES", "1") == "1"
SKIP_RETWEETS = os.environ.get("X_SKIP_RETWEETS", "1") == "1"
MODE = os.environ.get("X_MODE", "repost")
FORCE = os.environ.get("X_FORCE", "0") == "1"
MATCH = [k.strip().lower() for k in os.environ.get("X_MATCH", "").split(",") if k.strip()]
EXCLUDE = [k.strip().lower() for k in os.environ.get("X_EXCLUDE", "").split(",") if k.strip()]
CSV_PATH = os.environ.get("X_CSV", "")
MD_PATH = os.environ.get("X_MD", "")
QUOTE_TEXT = os.environ.get("X_QUOTE", "").strip()
RUN_ID = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

# Filtros ampliados (los usa el panel; son opcionales en el CLI).
EXACT = [k.strip().lower() for k in os.environ.get("X_EXACT", "").split(",") if k.strip()]
LANGS = [k.strip().lower() for k in os.environ.get("X_LANG", "").split(",") if k.strip()]
HASHTAG_FILTER = [k.strip().lstrip("#").lower() for k in os.environ.get("X_HASHTAGS_FILTER", "").split(",") if k.strip()]
MIN_LEN = _env_num("X_MIN_LEN", 0, int) if os.environ.get("X_MIN_LEN", "").strip() else 0
MAX_LEN = _env_num("X_MAX_LEN", 0, int) if os.environ.get("X_MAX_LEN", "").strip() else 0
MEDIA_FILTER = os.environ.get("X_MEDIA", "").strip().lower()
VIDEO_FILTER = os.environ.get("X_VIDEO", "").strip().lower()
KIND_FILTER = os.environ.get("X_KIND", "").strip().lower()
INCLUDE_RE = _regex_safe(os.environ.get("X_INCLUDE_REGEX", ""), "X_INCLUDE_REGEX")
EXCLUDE_RE = _regex_safe(os.environ.get("X_EXCLUDE_REGEX", ""), "X_EXCLUDE_REGEX")

HISTORY = os.environ.get("X_HISTORY") or os.path.join(
    os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")),
    "xrepost",
    "history.jsonl",
)

SKIPPED_RT = 0
SKIPPED_KW = 0
SEEN = set()  # URLs ya aceptadas; global para no duplicar entre usuarios


def _load_shared(module, attr):
    """Módulos compartidos con el CLI y el panel (xrepost_labels, xrepost_history).

    El motor llega por stdin al harness, así que no existe `__file__`: se busca
    el módulo en la carpeta que exporta xrepost.sh. Si no aparece, se usa el
    respaldo local (la ejecución sigue funcionando igual).
    """
    base = os.environ.get("X_SELF_DIR") or os.getcwd()
    try:
        if base not in sys.path:
            sys.path.append(base)
        return getattr(__import__(module), attr)
    except Exception:
        return None


LABELS = _load_shared("xrepost_labels", "LABELS") or {}
_UNCERTAIN = _load_shared("xrepost_labels", "UNCERTAIN_RESULTS") or ("unconfirmed", "quote_unverified")
_FATAL = _load_shared("xrepost_labels", "FATAL_RESULTS") or (
    "session_expired",
    "captcha",
    "rate_limited",
    "suspended",
)

# Utilidades de escritura segura (atómicas, sin seguir enlaces simbólicos).
_atomic_write = _load_shared("xrepost_fs", "atomic_write")
_append_line = _load_shared("xrepost_fs", "append_line")
_ensure_dir = _load_shared("xrepost_fs", "ensure_dir")
_assert_regular = _load_shared("xrepost_fs", "assert_regular_file")
_read_json = _load_shared("xrepost_fs", "read_json")
_read_events = _load_shared("xrepost_history", "read_events")
_csv_safe = _load_shared("xrepost_exports", "csv_safe")


def label(res):
    return LABELS.get(res, res)


def _fallback_history_state(entries):
    reposted, ours = set(), {}
    for e in entries:
        action, res = e.get("action"), e.get("result")
        if action == "repost":
            if res == "reposted":
                reposted.add(e["id"])
                ours.pop(e["id"], None)
                ours[e["id"]] = e
            elif res in ("quoted", "already"):
                reposted.add(e["id"])
        elif action == "undo" and res in ("undone", "not_reposted"):
            reposted.discard(e["id"])
            ours.pop(e["id"], None)
    return reposted, ours


_history_state = _load_shared("xrepost_history", "history_state") or _fallback_history_state
_iso_timestamp = _load_shared("xrepost_history", "iso_timestamp")


def fmt_fecha(value):
    """Fecha visible DD/MM/YYYY HH:MM.

    Acepta ISO (2026-10-28T15:38:00Z, lo que devuelve el DOM de X) o un valor
    que ya venga en DD/MM/YYYY (por ejemplo, el listado revisado del panel web).
    """
    s = str(value or "").strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?", s)
    if m:
        y, mo, d, hh, mm = m.groups()
        return f"{d}/{mo}/{y}" + (f" {hh}:{mm}" if hh else "")
    return s

# Textos de "respuesta" en varios idiomas: solo como respaldo si el DOM no basta.
REPLY_HINTS = (
    "replying to", "in reply to", "respondiendo a", "en respuesta a",
    "réponse à", "antwort auf", "risposta a", "respondendo a", "em resposta a",
    "in risposta a", "yanıt", "в ответ", "返信", "回复", "回覆",
)

COLLECT_JS = (
    "Array.from(document.querySelectorAll('article[data-testid=\"tweet\"]'))"
    ".map(function(a){"
    "var t=a.querySelector('time');"
    "var l=a.querySelector('a[href*=\"/status/\"]');"
    "var n=a.querySelector('[data-testid=\"User-Name\"]');"
    "var x=a.querySelector('[data-testid=\"tweetText\"]');"
    "var r=a.querySelector('[data-testid=\"socialContext\"]');"
    "var lines=n?n.innerText.split('\\n'):[];"
    "var handle='';"
    "for(var i=0;i<lines.length;i++){"
    "var s=lines[i].trim();"
    "if(s.charAt(0)==='@'){handle=s.slice(1).replace(/[^A-Za-z0-9_]/g,'');break;}}"
    "var reply=false;"
    "if(n){"
    "var links=a.querySelectorAll('a[href]');"
    "for(var i=0;i<links.length;i++){"
    "var lk=links[i];"
    "var h=lk.getAttribute('href')||'';"
    "var txt=(lk.innerText||'').trim();"
    "if(!/^\\/[A-Za-z0-9_]+$/.test(h)||txt.charAt(0)!=='@')continue;"
    "if(n.contains(lk))continue;"
    "if(x&&x.contains(lk))continue;"
    "if(!x||(lk.compareDocumentPosition(x)&Node.DOCUMENT_POSITION_FOLLOWING)){reply=true;break;}}}"
    "return {"
    "time: t?t.getAttribute('datetime'):'',"
    "url: l?('https://x.com'+l.getAttribute('href')):'',"
    "user: n?n.innerText.split('\\n')[0]:'',"
    "handle: handle,"
    "text: x?x.innerText.slice(0,5000):'',"
    "ctx: r?r.innerText:'',"
    "reply: reply,"
    "media: !!a.querySelector('[data-testid=\"tweetPhoto\"],img[src*=\"pbs.twimg.com/media\"]'),"
    "video: !!a.querySelector('video,[data-testid=\"videoPlayer\"]'),"
    "lang: (x&&x.getAttribute('lang'))||a.getAttribute('lang')||document.documentElement.lang||''"
    "};})"
)

N_ARTICLES = "document.querySelectorAll('article[data-testid=\"tweet\"]').length"

# Se actúa solo sobre el artículo del post abierto, nunca sobre las respuestas
# que X carga debajo: un botón de una respuesta daría falsos «ya estaba
# reposteado», «no confirmado» o «deshecho». Se busca por el ID de la URL
# (una respuesta muestra el tweet padre arriba, también como artículo) y se
# cae al primero si no aparece.
FOCAL = (
    "(function(){"
    "var m=location.pathname.match(/\\/status\\/(\\d+)/);"
    "var id=m?m[1]:'';"
    "var arts=document.querySelectorAll('article[data-testid=\"tweet\"]');"
    "if(!id)return arts[0]||null;"
    "for(var i=0;i<arts.length;i++){"
    "var ls=arts[i].querySelectorAll('a[href*=\"/status/\"]');"
    "for(var j=0;j<ls.length;j++){"
    "if(ls[j].getAttribute('href').indexOf('/status/'+id)>=0)return arts[i];}}"
    "return arts[0]||null;})()"
)
N_RETWEET = (
    "(function(){var a=" + FOCAL + ";"
    "return a?a.querySelectorAll('[data-testid=\"retweet\"]').length:0})()"
)
N_UNRETWEET = (
    "(function(){var a=" + FOCAL + ";"
    "return a?a.querySelectorAll('[data-testid=\"unretweet\"]').length:0})()"
)
FIRST_RETWEET = (
    "(function(){var a=" + FOCAL + ";"
    "return a?a.querySelector('[data-testid=\"retweet\"]'):null})()"
)
FIRST_UNRETWEET = (
    "(function(){var a=" + FOCAL + ";"
    "return a?a.querySelector('[data-testid=\"unretweet\"]'):null})()"
)
HAS_CONFIRM = "!!document.querySelector('[data-testid=\"retweetConfirm\"]')"
HAS_UNDO = "!!document.querySelector('[data-testid=\"unretweetConfirm\"]')"

# Menú de repost: la opción de cita es el enlace a /compose/post.
QUOTE_MENU = "document.querySelector('a[role=\"menuitem\"][href*=\"/compose/post\"]')"
HAS_QUOTE_MENU = "!!document.querySelector('a[role=\"menuitem\"][href*=\"/compose/post\"]')"

# X confirma la publicación con un toast que enlaza al post nuevo («Ver»).
HAS_POST_TOAST = "!!document.querySelector('[data-testid=\"toast\"] a[href*=\"/status/\"]')"

# El modal de la cita, no el compositor de respuesta que X muestra arriba en la
# página del post: se busca el último editor de texto dentro de un diálogo.
QUOTE_DIALOG = (
    "(function(){"
    "var ts=document.querySelectorAll('[data-testid=\"tweetTextarea_0\"]');"
    "for(var i=ts.length-1;i>=0;i--){"
    "var d=ts[i].closest('[role=\"dialog\"],[aria-modal=\"true\"]');"
    "if(d&&d.querySelector('[data-testid=\"tweetButton\"]'))return d;}"
    "return null;})()"
)
HAS_QUOTE_COMPOSER = "!!(" + QUOTE_DIALOG + ")"
QUOTE_POST_DISABLED = (
    "(function(){var d=" + QUOTE_DIALOG + ";"
    "var b=d?d.querySelector('[data-testid=\"tweetButton\"]'):null;"
    "return !b||b.getAttribute('aria-disabled')==='true';})()"
)
FOCUS_QUOTE_EDITOR = (
    "(function(){var d=" + QUOTE_DIALOG + ";"
    "if(!d)return false;"
    "var t=d.querySelector('[data-testid=\"tweetTextarea_0\"]');"
    "if(!t)return false;t.focus();return true;})()"
)
CLICK_QUOTE_POST = (
    "(function(){var d=" + QUOTE_DIALOG + ";"
    "var b=d?d.querySelector('[data-testid=\"tweetButton\"]'):null;"
    "if(!b)return false;b.click();return true;})()"
)

# Sonda de bloqueos de X: devuelve "" si la página parece normal o un código
# (login, captcha, rate_limited, suspended, unavailable) si no. Se limita a la
# columna principal para no confundir el texto de una publicación con un aviso.
PAGE_PROBLEM_JS = _load_shared("xrepost_selectors", "PAGE_PROBLEM_JS") or (
    "(function(){"
    "var path=location.pathname||'';"
    "if(path.indexOf('/i/flow/login')===0||path.indexOf('/login')===0)return 'login';"
    "if(document.querySelector('[data-testid=\"loginButton\"]'))return 'login';"
    "if(document.querySelector('iframe[src*=\"arkose\"],iframe[title*=\"captcha\" i],"
    "[data-testid=\"captcha\"]'))return 'captcha';"
    "var col=document.querySelector('[data-testid=\"primaryColumn\"]')||document.body;"
    "var txt=(col?col.innerText:'').slice(0,3000).toLowerCase();"
    "if(txt.indexOf('verify you are human')>=0||txt.indexOf('verifica que eres una persona')>=0)return 'captcha';"
    "if(txt.indexOf('rate limit')>=0||txt.indexOf('too many requests')>=0||"
    "txt.indexOf('demasiadas solicitudes')>=0)return 'rate_limited';"
    "if(txt.indexOf('account suspended')>=0||txt.indexOf('cuenta suspendida')>=0||"
    "txt.indexOf('temporarily restricted')>=0||txt.indexOf('restricción temporal')>=0)return 'suspended';"
    "if(txt.indexOf('this post is unavailable')>=0||"
    "txt.indexOf('esta publicación no está disponible')>=0||"
    "txt.indexOf('this page doesn')>=0||txt.indexOf('algo salió mal')>=0)return 'unavailable';"
    "return '';})()"
)

FATAL_BLOCK = ""


def page_problem():
    """Código de bloqueo visible en la página, o "" si todo parece normal."""
    try:
        return str(js(PAGE_PROBLEM_JS) or "")
    except Exception:
        return ""


def page_guard():
    """Traduce un bloqueo de X a un resultado estable; "" si se puede seguir."""
    global FATAL_BLOCK
    problem = page_problem()
    if not problem:
        return ""
    if problem == "unavailable":
        return "page_unavailable"
    mapping = {
        "login": "session_expired",
        "captcha": "captcha",
        "rate_limited": "rate_limited",
        "suspended": "suspended",
    }
    result = mapping.get(problem, "page_unavailable")
    if result in _FATAL:
        FATAL_BLOCK = result
    print(f"  BLOQUEO DE X: {label(result)}")
    return result


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def next_day(d):
    return (dt.date.fromisoformat(d) + dt.timedelta(days=1)).isoformat()


def handle_from_url(url):
    m = re.search(r"x\.com/([^/?#]+)/status/", url or "")
    return m.group(1) if m else ""


def tweet_id(url_or_id):
    s = (url_or_id or "").strip()
    m = re.search(r"/status/(\d+)", s)
    return m.group(1) if m else s


def text_ok(text):
    low = (text or "").lower()
    if MATCH and not any(k in low for k in MATCH):
        return False
    if EXCLUDE and any(k in low for k in EXCLUDE):
        return False
    if EXACT and not any(k in low for k in EXACT):
        return False
    if INCLUDE_RE and not INCLUDE_RE.search(text or ""):
        return False
    if EXCLUDE_RE and EXCLUDE_RE.search(text or ""):
        return False
    if MIN_LEN and len(text or "") < MIN_LEN:
        return False
    if MAX_LEN and len(text or "") > MAX_LEN:
        return False
    if HASHTAG_FILTER:
        present = {t.lower() for t in re.findall(r"#([^\s#,]{1,50})", text or "")}
        if not any(tag in present for tag in HASHTAG_FILTER):
            return False
    return True


def post_ok(post):
    """Filtros que necesitan metadatos que no están en el texto."""
    text = post.get("text") or ""
    if not text_ok(text):
        return False
    lang = str(post.get("lang") or "").lower()
    if LANGS and not any(lang == item or lang.startswith(item + "-") for item in LANGS):
        return False
    if MEDIA_FILTER:
        if (MEDIA_FILTER == "yes") != bool(post.get("media")):
            return False
    if VIDEO_FILTER:
        if (VIDEO_FILTER == "yes") != bool(post.get("video")):
            return False
    if KIND_FILTER:
        is_reply = bool(post.get("reply"))
        is_retweet = bool(post.get("retweet")) or "repost" in str(post.get("ctx") or "").lower() or "retweet" in str(post.get("ctx") or "").lower()
        if KIND_FILTER == "reply" and not is_reply:
            return False
        if KIND_FILTER == "original" and (is_reply or is_retweet):
            return False
        if KIND_FILTER == "retweet" and not is_retweet:
            return False
    return True


def load_selected_posts(path):
    """Carga el listado exacto revisado en el panel web (X_ONLY_URLS_FILE).

    Evita que entre la previsualización y la aplicación cambie el conjunto de
    publicaciones: se repostea exactamente lo que el usuario vio.
    """
    try:
        if _assert_regular:
            _assert_regular(path)
        if _read_json:
            data = _read_json(path, default=None)
        else:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
    except (OSError, ValueError) as e:
        print(f"  error al leer el listado revisado: {e}")
        return []
    if data is None:
        print("  error al leer el listado revisado: archivo vacío o no válido")
        return []
    if not isinstance(data, list):
        print("  el listado revisado no tiene el formato esperado")
        return []

    posts, seen = [], set()
    for item in data:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url or url in seen:
            continue
        parsed = urlparse(url)
        if (
            parsed.scheme not in ("http", "https")
            or (parsed.hostname or "").lower()
            not in ("x.com", "www.x.com", "twitter.com", "www.twitter.com")
            or "/status/" not in parsed.path
        ):
            print(f"  aviso: URL no válida en el listado revisado: {url}")
            continue
        seen.add(url)
        handle = str(item.get("usuario") or item.get("handle") or "").lstrip("@")
        posts.append({
            "url": url,
            "time": str(item.get("fecha") or item.get("posted_at") or item.get("time") or ""),
            "user": str(item.get("autor") or item.get("user") or handle),
            "handle": handle or handle_from_url(url),
            "text": str(item.get("texto") or item.get("text") or ""),
            "search_user": str(item.get("search_user") or ""),
        })
    return posts


# --- historial --------------------------------------------------------------

def load_history():
    entries = []
    if _read_events:
        try:
            return [e for e in _read_events(HISTORY) if isinstance(e, dict) and e.get("id")]
        except Exception as exc:
            print(f"  (aviso: no se pudo leer el historial: {exc})")
            return []
    try:
        with open(HISTORY, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if isinstance(e, dict) and e.get("id"):
                    entries.append(e)
    except FileNotFoundError:
        pass
    except OSError as e:
        print(f"  (aviso: no se pudo leer el historial: {e})")
    return entries


def save_event(action, result, post=None, entry=None):
    base = entry or post or {}
    posted_at = base.get("posted_at") or base.get("time", "")
    if _iso_timestamp:
        posted_at = _iso_timestamp(posted_at)
    rec = {
        "ts": now(),
        "run": RUN_ID,
        "action": action,
        "result": result,
        "id": base.get("id") or tweet_id(base.get("url", "")),
        "url": base.get("url", ""),
        "search_user": base.get("search_user", ""),
        "author": base.get("author") or base.get("user", ""),
        "handle": base.get("handle", ""),
        "posted_at": posted_at,
    }
    if action == "repost" and QUOTE_TEXT:
        rec["quote"] = QUOTE_TEXT
    if not rec["id"]:
        print("  (aviso: evento sin id; no se guarda en el historial)")
        return
    try:
        if _append_line:
            _append_line(HISTORY, json.dumps(rec, ensure_ascii=False, sort_keys=True))
        else:
            d = os.path.dirname(HISTORY)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(HISTORY, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"  (aviso: no se pudo guardar el historial: {e})")


def history_state(entries):
    """Devuelve (reposteados, nuestros); ver xrepost_history.history_state."""
    return _history_state(entries)


def reposted_ids(entries):
    """IDs cuyo último estado conocido indica que están reposteados."""
    return history_state(entries)[0]


def uncertain_ids(entries):
    """IDs con un intento cuyo resultado nunca se confirmó.

    Se omiten en ejecuciones posteriores salvo ``--force``: reintentar a ciegas
    puede duplicar un repost o una cita que sí se publicó.
    """
    reposted, ours = history_state(entries)
    pending = set()
    for event in entries:
        if event.get("result") in _UNCERTAIN and event.get("id"):
            pending.add(str(event["id"]))
        elif event.get("action") == "repost" and event.get("result") in ("reposted", "quoted", "already"):
            pending.discard(str(event.get("id")))
    return pending - reposted


def undo_candidates(entries, target="", n=0):
    """Reposts hechos por la herramienta que siguen vigentes."""
    cand = list(history_state(entries)[1].values())
    if target:
        tid = tweet_id(target)
        return [e for e in cand if e["id"] == tid or (e.get("url") or "").rstrip("/") == target.rstrip("/")]
    if n:
        return cand[-n:]
    if not cand:
        return []
    last_run = cand[-1].get("run")
    return [e for e in cand if e.get("run") == last_run]


# --- navegador --------------------------------------------------------------

def wait_articles(timeout=12):
    for _ in range(timeout):
        if js(N_ARTICLES) > 0:
            return True
        time.sleep(1)
    return False


def collect(user, d_from, d_to):
    global SKIPPED_RT, SKIPPED_KW
    q = f"from:{user} since:{d_from} until:{next_day(d_to)}"
    url = "https://x.com/search?q=" + quote(q) + "&f=live"
    print(f"\n[{user}] buscando {fmt_fecha(d_from)} .. {fmt_fecha(d_to)}")
    goto_url(url)
    wait_for_load()
    problem = page_guard()
    if problem:
        return []
    if not wait_articles():
        print("  sin resultados (o no cargó)")
        return []

    seen, out = set(), []
    for _ in range(8):
        if FATAL_BLOCK:
            return out
        for r in (js(COLLECT_JS) or []):
            url = r.get("url") or ""
            if not url or url in seen:
                continue
            seen.add(url)
            day = (r.get("time") or "")[:10]
            if not day or not (d_from <= day <= d_to):
                continue
            author = (r.get("handle") or handle_from_url(url)).lstrip("@").lower()
            if SKIP_RETWEETS and author and author != user.lower():
                SKIPPED_RT += 1
                continue
            ctx = (r.get("ctx") or "").lower()
            if SKIP_REPLIES and (r.get("reply") or any(k in ctx for k in REPLY_HINTS)):
                continue
            if not post_ok(r):
                SKIPPED_KW += 1
                continue
            if url in SEEN:
                continue
            SEEN.add(url)
            r["user"] = r.get("user") or user
            r["search_user"] = user
            out.append(r)
        if len(out) >= 40:
            break
        js("window.scrollBy(0, 1600)")
        time.sleep(1.8)
    return out


def repost(url):
    if QUOTE_TEXT:
        return quote_repost(url, QUOTE_TEXT)
    goto_url(url)
    wait_for_load()
    time.sleep(1.5)
    problem = page_guard()
    if problem:
        return problem
    if js(N_UNRETWEET) > 0:
        return "already"
    if js(N_RETWEET) == 0:
        return "no_button"
    js(FIRST_RETWEET + ".click()")
    time.sleep(1.3)
    if not js(HAS_CONFIRM):
        problem = page_guard()
        return problem or "no_menu"
    js("document.querySelector('[data-testid=\"retweetConfirm\"]').click()")
    time.sleep(2.5)
    if js(N_UNRETWEET) > 0:
        return "reposted"
    # Sin el estado «unretweet» no hay confirmación real: puede ser un fallo de
    # X o que la acción no se aplicó. Nunca se marca como éxito.
    problem = page_guard()
    return problem or "unconfirmed"


def bring_tab_front():
    """X no monta el modal de cita si la pestaña está en segundo plano."""
    try:
        tab = current_tab()
        target = tab.get("targetId") or tab.get("target_id")
        if target:
            activate_tab(target)
            time.sleep(0.5)
    except Exception:
        pass


def quote_repost(url, text):
    """Repost con cita: abre «Quote», escribe el comentario y publica."""
    bring_tab_front()
    goto_url(url)
    wait_for_load()
    time.sleep(1.5)
    problem = page_guard()
    if problem:
        return problem

    button = FIRST_RETWEET if js(N_RETWEET) > 0 else FIRST_UNRETWEET
    if js(N_RETWEET) == 0 and js(N_UNRETWEET) == 0:
        return "no_button"
    js(button + ".click()")
    time.sleep(1.3)
    if not js(HAS_QUOTE_MENU):
        problem = page_guard()
        return problem or "no_quote_option"
    js(QUOTE_MENU + ".click()")

    for _ in range(15):
        if js(HAS_QUOTE_COMPOSER):
            break
        time.sleep(1)
    else:
        problem = page_guard()
        return problem or "no_composer"

    if not js(FOCUS_QUOTE_EDITOR):
        return "no_composer"
    time.sleep(0.4)
    type_text(text)
    time.sleep(0.8)

    for _ in range(10):
        if not js(QUOTE_POST_DISABLED):
            break
        time.sleep(0.5)
    else:
        return "quote_failed"

    if not js(CLICK_QUOTE_POST):
        return "quote_failed"
    for _ in range(24):
        time.sleep(0.5)
        if not js(HAS_QUOTE_COMPOSER):
            break
    else:
        return "quote_failed"
    # El editor puede cerrarse sin publicar (navegación, error de X): solo el
    # toast con enlace al post nuevo confirma la cita. Sin él no se marca como
    # hecha, porque una cita falsa en el historial bloquea el reintento.
    for _ in range(10):
        if js(HAS_POST_TOAST):
            return "quoted"
        time.sleep(0.5)
    problem = page_guard()
    return problem or "quote_unverified"


def undo_one(url):
    goto_url(url)
    wait_for_load()
    time.sleep(1.5)
    problem = page_guard()
    if problem:
        return problem
    if js(N_UNRETWEET) == 0:
        return "not_reposted"
    js(FIRST_UNRETWEET + ".click()")
    time.sleep(1.2)
    if js(HAS_UNDO):
        js("document.querySelector('[data-testid=\"unretweetConfirm\"]').click()")
        time.sleep(2.0)
    elif js(N_UNRETWEET) > 0:
        # Sin diálogo de confirmación la acción no se completó; no se puede
        # afirmar que se deshizo.
        return "undo_failed"
    if js(N_UNRETWEET) == 0:
        return "undone"
    problem = page_guard()
    return problem or "undo_failed"


# --- exportación ------------------------------------------------------------

def build_rows(posts, statuses, default_status):
    rows = []
    for p in posts:
        rows.append({
            "fecha": fmt_fecha(p.get("time")),
            "autor": p.get("user", ""),
            "usuario": ("@" + p["handle"]) if p.get("handle") else "",
            "texto": (p.get("text") or "").replace("\n", " ").strip(),
            "url": p.get("url", ""),
            "estado": label(statuses.get(p.get("url", ""), default_status)),
        })
    return rows


def write_csv(rows, path):
    import io

    buffer = io.StringIO()
    w = csv.DictWriter(
        buffer, fieldnames=["fecha", "autor", "usuario", "texto", "url", "estado"], lineterminator="\n"
    )
    w.writeheader()
    for row in rows:
        clean = {}
        for key, value in row.items():
            text = "" if value is None else str(value)
            if _csv_safe:
                text = _csv_safe(text)
            elif text.startswith(("=", "+", "-", "@", "\t", "\r")):
                text = "'" + text
            clean[key] = text
        w.writerow(clean)
    text = buffer.getvalue()
    if _atomic_write:
        _atomic_write(path, text)
    else:
        d = os.path.dirname(os.path.abspath(path))
        os.makedirs(d, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write(text)


def write_md(rows, path):
    def esc(s):
        return str(s).replace("|", "\\|").replace("\n", " ")

    lines = ["| Fecha | Autor | Texto | Enlace | Estado |", "|---|---|---|---|---|"]
    for r in rows:
        lines.append(
            f"| {esc(r['fecha'])} | {esc(r['autor'])} {esc(r['usuario'])} | "
            f"{esc(r['texto'])} | [post]({r['url']}) | {esc(r['estado'])} |"
        )
    text = "\n".join(lines) + "\n"
    if _atomic_write:
        _atomic_write(path, text)
    else:
        d = os.path.dirname(os.path.abspath(path))
        os.makedirs(d, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


def do_export(posts, statuses=None, default_status="solo listado"):
    if not (CSV_PATH or MD_PATH):
        return
    rows = build_rows(posts, statuses or {}, default_status)
    if CSV_PATH:
        write_csv(rows, CSV_PATH)
        print(f"  CSV guardado en {CSV_PATH}")
    if MD_PATH:
        write_md(rows, MD_PATH)
        print(f"  Markdown guardado en {MD_PATH}")


# --- deshacer ---------------------------------------------------------------

def run_undo():
    entries = load_history()
    target = os.environ.get("X_UNDO_TARGET", "").strip()
    try:
        n = int(os.environ.get("X_UNDO_N") or 0)
    except ValueError:
        n = 0

    cand = undo_candidates(entries, target=target, n=n)
    if not cand:
        if target:
            print(f"No encuentro ese repost en el historial: {target}")
        elif n:
            print("No hay reposts que deshacer en el historial.")
        else:
            print("No hay reposts de la última ejecución que deshacer.")
        return 0

    print(f"Deshaciendo {len(cand)} repost(s)...\n")
    done = 0
    for e in cand:
        url = e.get("url") or f"https://x.com/i/status/{e['id']}"
        res = undo_one(url)
        print(f"  {label(res)}: {url}")
        save_event("undo", res, entry=e)
        if res == "undone":
            done += 1
            time.sleep(DELAY)
    print(f"\nTotal deshecho: {done}")
    return 0


# --- pestaña propia ----------------------------------------------------------

def _close_quietly(target: str) -> None:
    try:
        close_tab(target)
    except Exception:
        pass


def _guard_own_tab(target: str) -> None:
    """Cierra la pestaña propia también si el trabajo se cancela.

    El panel cancela con SIGTERM al grupo de procesos y, a los 3 s, con
    SIGKILL; por eso se cierra en un hilo con espera máxima y se sale sin
    esperar a nada más.
    """

    def handler(signum, _frame):
        closer = threading.Thread(target=_close_quietly, args=(target,), daemon=True)
        closer.start()
        closer.join(2.0)
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        os._exit(128 + signum)

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, handler)
        except (ValueError, OSError):
            pass


def use_own_tab() -> None:
    """Trabaja en una pestaña propia y la cierra al terminar.

    El motor comparte Chrome con la persona: sin esto, la primera navegación
    se lleva por delante la pestaña que tenga activa. Solo se cierra la
    pestaña que hemos abierto nosotros; si el CLI no ofrece los helpers, se
    mantiene el comportamiento anterior.
    """
    try:
        before = {t.get("targetId") for t in list_tabs()}
        new_tab("about:blank")
        own = [t for t in list_tabs() if t.get("targetId") not in before]
    except Exception:
        return
    target = own[-1].get("targetId") if own else ""
    if target:
        atexit.register(_close_quietly, target)
        _guard_own_tab(target)


# --- principal --------------------------------------------------------------

def _validate_run():
    """Validación previa: evita actuar con datos fuera de rango."""
    if not USERS or not D_FROM:
        print("faltan X_USERS o X_FROM")
        return False
    if len(USERS) > 10:
        print("demasiadas cuentas: como máximo 10")
        return False
    for user in USERS:
        if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", user):
            print(f"cuenta no válida: @{user}")
            return False
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", D_FROM or "") or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}", D_TO or ""
    ):
        print("las fechas deben ser YYYY-MM-DD")
        return False
    try:
        d_from = dt.date.fromisoformat(D_FROM)
        d_to = dt.date.fromisoformat(D_TO)
    except ValueError:
        print("alguna fecha no existe en el calendario")
        return False
    if d_from > d_to:
        print("la fecha inicial no puede ser posterior a la final")
        return False
    if d_from.year < 2006 or d_to.year > 2100:
        print("el rango de fechas queda fuera de lo razonable (2006–2100)")
        return False
    if not 1 <= LIMIT <= 50:
        print("X_LIMIT debe estar entre 1 y 50")
        return False
    if not 0 <= DELAY <= 300:
        print("X_DELAY debe estar entre 0 y 300 segundos")
        return False
    if len(QUOTE_TEXT) > 280:
        print("el comentario de la cita supera 280 caracteres")
        return False
    parse_endpoint = _load_shared("xrepost_cdp", "parse_endpoint")
    if parse_endpoint:
        try:
            endpoint = parse_endpoint()
        except Exception as exc:
            print(f"CDP no válido: {exc}")
            return False
        if endpoint.problems:
            print("CDP no válido: " + "; ".join(endpoint.problems))
            return False
    return True


def _filter_history(found):
    """Quita lo ya hecho y lo que quedó sin confirmar (salvo --force)."""
    if FORCE:
        return found, 0, 0
    entries = load_history()
    already = reposted_ids(entries)
    uncertain = uncertain_ids(entries)
    before = len(found)
    pending = []
    skipped_uncertain = 0
    for p in found:
        tid = tweet_id(p.get("url", ""))
        if tid in uncertain:
            skipped_uncertain += 1
            continue
        if tid in already:
            continue
        pending.append(p)
    skipped_hist = before - len(pending) - skipped_uncertain
    return pending, skipped_hist, skipped_uncertain


def main():
    if MODE in ("undo", "undo_last"):
        use_own_tab()
        return run_undo()

    if not _validate_run():
        return 2

    use_own_tab()
    selected_file = os.environ.get("X_ONLY_URLS_FILE", "").strip()

    if selected_file:
        found = load_selected_posts(selected_file)
        found, skipped_hist, skipped_uncertain = _filter_history(found)
        print(
            f"modo: {'APLICAR reposts' if APPLY else 'DRY-RUN (solo listar)'} "
            f"sobre {len(found)} publicaciones revisadas | límite={LIMIT} | delay={DELAY}s"
        )
        print("origen: listado de la previsualización (no se vuelve a buscar en X)")
        if QUOTE_TEXT:
            print(f"comentario de la cita: {QUOTE_TEXT}")
        if skipped_hist:
            print(
                f"({skipped_hist} ya reposteados o citados en ejecuciones "
                "anteriores; usa --force para incluirlos)"
            )
        if skipped_uncertain:
            print(
                f"({skipped_uncertain} omitidos: un intento anterior quedó sin confirmar; "
                "revisa tu perfil y usa --force si quieres reintentarlos)"
            )
        if not found:
            if skipped_hist or skipped_uncertain:
                print("\nNada pendiente: todo el listado consta como hecho o pendiente de revisión.")
                do_export([])
                return 0
            print("\nNo hay publicaciones seleccionadas.")
            do_export([])
            return 2
    else:
        print(f"modo: {'APLICAR reposts' if APPLY else 'DRY-RUN (solo listar)'} | límite={LIMIT} | delay={DELAY}s")
        print(
            "alcance: "
            + ("solo publicaciones originales" if SKIP_RETWEETS else "incluye retweets de otras cuentas")
            + " | respuestas: "
            + ("omitidas" if SKIP_REPLIES else "incluidas")
        )
        if QUOTE_TEXT:
            print(f"comentario de la cita: {QUOTE_TEXT}")
        if MATCH or EXCLUDE:
            print(f"filtros de texto: incluir={MATCH or '—'} | excluir={EXCLUDE or '—'}")

        found = []
        for u in USERS:
            if FATAL_BLOCK:
                break
            try:
                found.extend(collect(u, D_FROM, D_TO))
            except Exception as e:
                print(f"  error con {u}: {e}")

        if SKIPPED_RT:
            print(f"\n({SKIPPED_RT} retweets de otras cuentas ignorados; X_SKIP_RETWEETS=0 para incluirlos)")
        if SKIPPED_KW:
            print(f"({SKIPPED_KW} descartados por los filtros)")

        found, skipped_hist, skipped_uncertain = _filter_history(found)
        if skipped_hist:
            print(f"({skipped_hist} ya reposteados en ejecuciones anteriores; usa --force para incluirlos)")
        if skipped_uncertain:
            print(
                f"({skipped_uncertain} omitidos por intentos sin confirmar; "
                "revisa tu perfil antes de reintentar)"
            )

    if not found:
        print("\nSin posts en ese rango.")
        do_export([])
        return 0

    print(f"\n{len(found)} posts encontrados:\n")
    for i, p in enumerate(found, 1):
        print(f"{i:3}. {fmt_fecha(p['time'])} | {p['user']}")
        print(f"     {p['text'][:150].replace(chr(10), ' ')}")
        print(f"     {p['url']}")

    statuses = {}
    do_export(found, default_status="solo listado" if not APPLY else "pendiente")

    if not APPLY:
        print("\nDRY-RUN: no se ha reposteado nada. Usa X_APPLY=1 para ejecutar.")
        return 0

    if QUOTE_TEXT:
        print(f"\nCitando con «{QUOTE_TEXT}» (máx {LIMIT})...\n")
    else:
        print(f"\nReposteando (máx {LIMIT})...\n")
    done = 0
    failures = 0
    for p in found:
        if done >= LIMIT:
            print(f"límite de {LIMIT} alcanzado")
            break
        if FATAL_BLOCK:
            print(f"tanda detenida por un bloqueo de X ({label(FATAL_BLOCK)})")
            break
        res = repost(p["url"])
        statuses[p["url"]] = res
        print(f"  {label(res)}: {p['url']}")
        save_event("repost", res, post=p)
        if res in ("reposted", "quoted"):
            done += 1
            failures = 0
            time.sleep(DELAY)
        elif res in _FATAL:
            # Un bloqueo de sesión, captcha o límite no se reintenta: seguir
            # solo empeora la situación.
            break
        else:
            failures += 1
            # El límite cuenta solo éxitos: sin este corte, una tanda donde
            # todo falla seguiría actuando sobre los 40 posts por usuario.
            if failures >= 3:
                print("3 fallos seguidos; se detiene la tanda por seguridad")
                break
    do_export(found, statuses, default_status="no procesado")
    print(f"\nTotal {'citado' if QUOTE_TEXT else 'reposteado'}: {done}")
    if FATAL_BLOCK:
        print(f"Incidente: {label(FATAL_BLOCK)}")
    return 0


sys.exit(main())
