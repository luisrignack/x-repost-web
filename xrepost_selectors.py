#!/usr/bin/env python3
"""Selectores y sondas JS de X centralizados para el motor.

Antes vivían repartidos en ``xrepost.py``. Aquí se declaran una sola vez para
que un cambio de la interfaz de X se arregle en un sitio y para poder probarlos
sin navegador. Se mantienen selectores semánticos (``data-testid``) frente a
clases CSS generadas, que cambian a menudo.

El motor se ejecuta por stdin dentro del harness de browser-use y no tiene
``__file__``; ``xrepost.sh`` exporta ``X_SELF_DIR`` para poder importar este
módulo. Si no estuviera disponible, ``xrepost.py`` conserva una copia mínima.
"""

from __future__ import annotations

# Selectores primarios. Los alternativos se usan solo cuando el primario no
# existe y son semánticamente equivalentes (nunca "el primer botón que haya").
SELECTORS: dict[str, tuple[str, ...]] = {
    "article": ('article[data-testid="tweet"]',),
    "time": ("time[datetime]", "time"),
    "status_link": ('a[href*="/status/"]',),
    "user_name": ('[data-testid="User-Name"]',),
    "tweet_text": ('[data-testid="tweetText"]', '[lang] div[dir="auto"]'),
    "social_context": ('[data-testid="socialContext"]',),
    "retweet": ('[data-testid="retweet"]', '[aria-label*="Repost"]', '[aria-label*="Retweet"]'),
    "unretweet": ('[data-testid="unretweet"]', '[aria-label*="Undo Repost"]', '[aria-label*="Deshacer"]'),
    "retweet_confirm": ('[data-testid="retweetConfirm"]',),
    "unretweet_confirm": ('[data-testid="unretweetConfirm"]',),
    "quote_menu": ('a[role="menuitem"][href*="/compose/post"]', 'a[role="menuitem"][href*="/compose/tweet"]'),
    "toast": ('[data-testid="toast"]',),
    "tweet_textarea": ('[data-testid="tweetTextarea_0"]',),
    "tweet_button": ('[data-testid="tweetButton"]', '[data-testid="tweetButtonInline"]'),
    "login": ('[data-testid="loginButton"]', 'a[href="/login"]'),
    "error_detail": ('[data-testid="error-detail"]',),
    "empty_state": ('[data-testid="emptyState"]',),
    "primary_column": ('[data-testid="primaryColumn"]',),
}

# Frases que X muestra cuando bloquea o limita la sesión. Se comparan en
# minúsculas contra el texto visible de la columna principal, nunca contra
# todo el documento (evita falsos positivos con el contenido de los posts).
PROBLEM_HINTS: dict[str, tuple[str, ...]] = {
    "captcha": (
        "verify you are human",
        "verifica que eres una persona",
        "arkose",
        "captcha",
    ),
    "rate_limited": (
        "rate limit",
        "too many requests",
        "límite de velocidad",
        "demasiadas solicitudes",
        "try again later",
        "inténtalo de nuevo más tarde",
    ),
    "suspended": (
        "account suspended",
        "cuenta suspendida",
        "temporarily restricted",
        "restricción temporal",
    ),
    "login": (
        "sign in to x",
        "inicia sesión en x",
        "log in to x",
        "join x today",
    ),
    "unavailable": (
        "this post is unavailable",
        "esta publicación no está disponible",
        "this page doesn’t exist",
        "this page doesn't exist",
        "algo salió mal",
        "something went wrong",
    ),
}


def selector(name: str) -> tuple[str, ...]:
    return SELECTORS[name]


def primary(name: str) -> str:
    return SELECTORS[name][0]


def _or(names: str) -> str:
    """Une selectores alternativos en una expresión CSS válida."""
    parts = [part for name in names.split("|") for part in SELECTORS[name]]
    return ",".join(parts)


# --- piezas JS --------------------------------------------------------------

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
    "var ctx=r?r.innerText:'';"
    "var rt=/repost|retweet|reposte|retuite/i.test(ctx);"
    "var media=!!a.querySelector('[data-testid=\"tweetPhoto\"],img[src*=\"pbs.twimg.com/media\"]');"
    "var video=!!a.querySelector('video,[data-testid=\"videoPlayer\"]');"
    "var lang=(x&&x.getAttribute('lang'))||a.getAttribute('lang')||document.documentElement.lang||'';"
    "return {"
    "time: t?t.getAttribute('datetime'):'',"
    "url: l?('https://x.com'+l.getAttribute('href')):'',"
    "user: n?n.innerText.split('\\n')[0]:'',"
    "handle: handle,"
    "text: x?x.innerText.slice(0,500):'',"
    "ctx: ctx,"
    "reply: reply,"
    "retweet: rt,"
    "media: media,"
    "video: video,"
    "lang: lang"
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

# Sonda de bloqueos de X. Devuelve "" si la página parece normal y un código
# (captcha, rate_limited, suspended, login, unavailable, error) si no.
PAGE_PROBLEM_JS = (
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
    "txt.indexOf('temporarily restricted')>=0)return 'suspended';"
    "var err=document.querySelector('[data-testid=\"error-detail\"]');"
    "if(err&&err.offsetParent!==null)return 'unavailable';"
    "if(txt.indexOf('this post is unavailable')>=0||"
    "txt.indexOf('esta publicación no está disponible')>=0||"
    "txt.indexOf('this page doesn')>=0||txt.indexOf('algo salió mal')>=0)return 'unavailable';"
    "return '';})()"
)

# Marca de la pestaña en la que corre el motor, para no cerrar la del usuario.
TAB_TITLE_JS = "document.title"

# Diagnóstico ligero cuando falta un elemento: qué selectores existen y cuántos
# artículos hay. No incluye texto de publicaciones ni datos de la sesión.
DIAGNOSTIC_JS = (
    "(function(){return {"
    "articles:document.querySelectorAll('article[data-testid=\"tweet\"]').length,"
    "retweet:document.querySelectorAll('[data-testid=\"retweet\"]').length,"
    "unretweet:document.querySelectorAll('[data-testid=\"unretweet\"]').length,"
    "dialog:document.querySelectorAll('[role=\"dialog\"]').length,"
    "url:(location.origin||'')+(location.pathname||'')"
    "};})()"
)


def alternatives(name: str) -> list[str]:
    """Lista de selectores alternativos declarados para un elemento."""
    return list(SELECTORS[name])
