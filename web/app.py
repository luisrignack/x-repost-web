#!/usr/bin/env python3
"""
xrepost web — panel local para el motor xrepost.

No sustituye al CLI: lo invoca como subproceso. El servidor escucha solo en
127.0.0.1, exige autenticación con sesión + CSRF y permite una ejecución a la
vez (Chrome es una sola sesión). Pensado para uso personal, sin exponerlo a la
red.

Capas de seguridad (ver docs/SEGURIDAD.md):

* ``Host`` y ``Origin`` se comparan de forma exacta contra el servidor local.
* El token maestro solo sirve para crear una sesión (``/?token=…``); a partir
  de ahí la cookie de sesión es ``HttpOnly`` + ``SameSite=Strict`` y cada
  escritura exige la cabecera ``X-CSRF-Token``.
* Los clientes de línea de comandos pueden seguir usando ``X-Token``: una
  cabecera personalizada no es falsificable desde otro origen.
* Los subprocesos se lanzan sin shell, con un entorno mínimo y un grupo de
  procesos propio para poder cancelarlos.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hmac
import json
import mimetypes
import os
import re
import secrets
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

WEB_DIR = Path(__file__).resolve().parent
ROOT = WEB_DIR.parent
STATIC_DIR = WEB_DIR / "static"
DEFAULT_ENGINE = ROOT / "xrepost.sh"
DEFAULT_RUNS = WEB_DIR / ".runs"
CHROME_LAUNCHER = ROOT / "xrepost-chrome.sh"

# El motor y el archivo de cuentas viven un nivel arriba; app.py se ejecuta
# desde web/, así que su carpeta no está en sys.path por defecto.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import xrepost_accounts  # noqa: E402  (depende del sys.path anterior)
import xrepost_cdp  # noqa: E402
import xrepost_exports  # noqa: E402
import xrepost_filters  # noqa: E402
import xrepost_fs  # noqa: E402
import xrepost_groups  # noqa: E402
import xrepost_hashtags  # noqa: E402
import xrepost_history  # noqa: E402
import xrepost_inbox  # noqa: E402
import xrepost_jobs  # noqa: E402
import xrepost_labels  # noqa: E402
import xrepost_network  # noqa: E402
import xrepost_schedule  # noqa: E402
import xrepost_security  # noqa: E402
import xrepost_stats  # noqa: E402

MAX_BODY = 1_000_000
MAX_LOG = 2_000
MAX_JOBS = 20
MAX_JOB_SECONDS = 30 * 60
SESSION_TTL = 8 * 3600
SESSION_IDLE = 30 * 60

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_DMY_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
HANDLE_RE = re.compile(r"^[A-Za-z0-9_]{1,15}$")
STATUS_RE = re.compile(
    r"^https?://(?:www\.)?(?:x|twitter)\.com/(?:[A-Za-z0-9_]+|i)/status/\d+/?$"
)
# Línea de estado por publicación del motor: "  reposteado: https://x.com/…".
PROGRESS_RE = re.compile(r"^ {2}(.+?):\s+(https?://\S+/status/\d+)/?\s*$")

# Variables de entorno que un trabajo puede heredar. Deliberadamente no se
# copia todo el entorno del servidor: evita filtrar credenciales de la sesión
# del usuario a subprocesos y evita que un X_* heredado cambie el trabajo.
ENV_PASSTHROUGH = {
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "LANG",
    "LANGUAGE",
    "LC_ALL",
    "LC_CTYPE",
    "TERM",
    "TMPDIR",
    "TZ",
    "DISPLAY",
    "WAYLAND_DISPLAY",
    "DBUS_SESSION_BUS_ADDRESS",
    "NO_COLOR",
    "XDG_CACHE_HOME",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "XDG_RUNTIME_DIR",
    "XDG_STATE_HOME",
}
ENV_PREFIXES = ("XREPOST_", "BU_", "STUB_")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=(), payment=(), usb=()",
}
CSP = (
    "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; "
    "img-src 'self' data:; font-src 'self' data:; connect-src 'self'; "
    "object-src 'none'; base-uri 'none'; form-action 'self'; "
    "frame-ancestors 'none'; worker-src 'none'"
)


class HttpError(Exception):
    def __init__(self, status: int, message: str, *, retry_after: int = 0):
        super().__init__(message)
        self.status = status
        self.message = message
        self.retry_after = retry_after


def default_history() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return Path(os.environ.get("X_HISTORY") or (base / "xrepost" / "history.jsonl")).expanduser()


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def fmt_seconds(value: float) -> str:
    value = max(0, int(value))
    if value < 60:
        return f"{value}s"
    return f"{value // 60}m {value % 60:02d}s"


def chrome_ok() -> bool:
    """Compatibilidad: ¿hay un CDP de Chrome en loopback?"""
    return xrepost_cdp.quick_available()


def network_status() -> dict:
    """Preferencia de red actual + flags que se aplicarán al relanzar Chrome."""
    cfg = xrepost_network.load_config()
    try:
        flags = xrepost_network.chrome_flags(cfg)
    except ValueError:
        flags = []
    return {
        "mode": cfg["mode"],
        "modes": list(xrepost_network.MODES),
        "proxy": cfg.get("proxy", ""),
        "proxy_scheme": cfg.get("proxy_scheme", "http"),
        "pac_path": cfg.get("pac_path", ""),
        "bypass": cfg.get("bypass", ""),
        "flags": flags,
        "chrome_running": chrome_ok(),
    }


def restart_chrome() -> None:
    """Cierra y relanza Chrome con la preferencia vigente (llamada del panel)."""
    launcher = Path(CHROME_LAUNCHER)
    if not launcher.exists() or not launcher.is_file():
        raise HttpError(500, "No se encontró el lanzador de Chrome.")
    try:
        xrepost_fs.assert_regular_file(launcher)
    except xrepost_fs.UnsafePathError as exc:
        raise HttpError(500, f"Lanzador de Chrome no válido: {exc}")
    try:
        proc = subprocess.run(
            ["bash", str(launcher), "--force"],
            cwd=str(ROOT),
            env=build_env({}),
            capture_output=True,
            text=True,
            timeout=90,
        )
    except subprocess.TimeoutExpired:
        raise HttpError(504, "Chrome tardó demasiado en arrancar.")
    if proc.returncode != 0:
        print(f"[xrepost-web] restart_chrome falló: {proc.stderr[-800:]}", file=sys.stderr)
        raise HttpError(500, "No se pudo reiniciar Chrome con la nueva configuración.")


def build_env(extra: dict[str, str]) -> dict[str, str]:
    """Entorno mínimo y determinista para subprocesos."""
    env: dict[str, str] = {}
    for key, value in os.environ.items():
        if key in ENV_PASSTHROUGH or key.startswith(ENV_PREFIXES):
            env[key] = value
    env.update({"PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"})
    env.setdefault("PATH", os.defpath)
    env.update({key: "" if value is None else str(value) for key, value in extra.items()})
    return env


def normalize_users(users: str) -> str:
    handles = []
    for raw in (users or "").split(","):
        handle = raw.strip().lstrip("@")
        if handle:
            handles.append(handle)
    return ",".join(handles)


def normalize_date(value: str) -> str:
    """Convierte DD/MM/AAAA (lo que ve el usuario) a ISO. Acepta ISO también."""
    value = value.strip()
    if DATE_DMY_RE.fullmatch(value):
        day, month, year = value.split("/")
        value = f"{year}-{month}-{day}"
    if not DATE_RE.fullmatch(value):
        raise HttpError(400, "Las fechas deben tener el formato DD/MM/AAAA.")
    return value


def validate_repost_params(data: dict, *, apply: bool) -> dict:
    users = normalize_users(str(data.get("users", "")))
    frm = normalize_date(str(data.get("from", "")))
    to = normalize_date(str(data.get("to", "")).strip() or frm)
    scope = str(data.get("scope", "originals"))
    match = str(data.get("match", "")).strip()
    exclude = str(data.get("exclude", "")).strip()
    raw_quote = str(data.get("quote", "")).strip()
    quote = xrepost_hashtags.clean_text(raw_quote)

    if not users:
        raise HttpError(400, "Indica al menos una cuenta.")
    if len(users.split(",")) > 10:
        raise HttpError(400, "Como máximo se pueden indicar 10 cuentas.")
    for handle in users.split(","):
        if not HANDLE_RE.fullmatch(handle):
            raise HttpError(400, f"Cuenta no válida: @{handle}. Usa solo letras, números y guion bajo.")
    try:
        d_from = dt.date.fromisoformat(frm)
        d_to = dt.date.fromisoformat(to)
    except ValueError:
        raise HttpError(400, "Alguna de las fechas no existe en el calendario.")
    if d_from.year < 2006 or d_to.year > 2100:
        raise HttpError(400, "El rango de fechas queda fuera de lo razonable (2006–2100).")
    if d_from > d_to:
        raise HttpError(400, "La fecha inicial no puede ser posterior a la final.")
    if scope not in ("originals", "all"):
        raise HttpError(400, "Alcance no válido.")
    if len(match) > 200 or len(exclude) > 200:
        raise HttpError(400, "Los filtros de texto son demasiado largos.")
    if raw_quote and not quote:
        raise HttpError(400, "El comentario debe ser un hashtag, por ejemplo #ETECSA.")
    if len(quote) > xrepost_hashtags.MAX_TEXT:
        raise HttpError(
            400,
            f"El comentario es demasiado largo (máximo {xrepost_hashtags.MAX_TEXT} caracteres).",
        )

    try:
        limit = int(data.get("limit", 10))
    except (TypeError, ValueError):
        raise HttpError(400, "El límite no es un número.")
    try:
        delay = float(data.get("delay", 20))
    except (TypeError, ValueError):
        raise HttpError(400, "La pausa no es un número.")

    if not 1 <= limit <= 50:
        raise HttpError(400, "El límite debe estar entre 1 y 50.")
    if not 0 <= delay <= 300:
        raise HttpError(400, "La pausa debe estar entre 0 y 300 segundos.")
    if apply and delay < 5:
        raise HttpError(400, "Por seguridad, la pausa mínima al repostear es de 5 segundos.")
    if apply and data.get("confirm") is not True:
        raise HttpError(400, "Falta la confirmación explícita para repostear.")

    return {
        "users": users,
        "from": frm,
        "to": to,
        "scope": scope,
        "match": match,
        "exclude": exclude,
        "quote": quote,
        "limit": limit,
        "delay": delay,
        "profile_id": str(data.get("profile_id") or ""),
        "filters": _clean_filters(data.get("filters")),
    }


def _clean_filters(raw: object) -> dict | None:
    if not isinstance(raw, dict) or not raw:
        return None
    try:
        return xrepost_filters.normalize_spec(raw)
    except xrepost_filters.FilterError as exc:
        raise HttpError(400, str(exc))


def params_key(params: dict) -> str:
    return json.dumps(
        {
            "users": params["users"].lower(),
            "from": params["from"],
            "to": params["to"],
            "scope": params["scope"],
            "match": params["match"],
            "exclude": params["exclude"],
            "quote": params["quote"],
            "filters": params.get("filters") or {},
            "profile_id": params.get("profile_id") or "",
        },
        sort_keys=True,
    )


def read_history(path: Path, limit: int = 30) -> list[dict]:
    """Último estado por publicación, con la etiqueta y si se puede deshacer."""
    entries = xrepost_history.read_events(path)
    latest: dict[str, dict] = {}
    for item in entries:
        if isinstance(item, dict) and item.get("id"):
            latest.pop(item["id"], None)
            latest[item["id"]] = item

    # «Deshacer» se ofrece mientras el repost siga vigente según el motor,
    # no solo si el último evento fue el repost: tras un undo_failed el
    # repost sigue ahí y debe poder reintentarse.
    _, ours = xrepost_history.history_state(entries)

    out = []
    for item in reversed(list(latest.values())[-max(1, limit):]):
        result = item.get("result", "")
        undoable = item["id"] in ours and bool(item.get("url"))
        out.append(
            {
                "ts": item.get("ts", ""),
                "action": item.get("action", ""),
                "result": result,
                "result_label": xrepost_labels.label(result),
                "undoable": undoable,
                "id": item.get("id", ""),
                "url": item.get("url", ""),
                "handle": item.get("handle", ""),
                "author": item.get("author", ""),
                "posted_at": item.get("posted_at", ""),
                "quote": item.get("quote", ""),
                "run": item.get("run", ""),
            }
        )
    return out


class Job:
    """Ejecución del motor con estado en memoria y su registro persistente."""

    def __init__(self, kind: str, params: dict, runs: Path):
        self.id = secrets.token_hex(8)
        self.kind = kind
        self.params = params
        self.status = "running"
        self.state = xrepost_jobs.QUEUED
        self.started = time.time()
        self.ended: float | None = None
        self.returncode: int | None = None
        self.cancelled = False
        self.error = ""
        self.lines: list[str] = []
        self.posts: list[dict] = []
        self.progress_done = 0
        self.dir = Path(runs) / self.id
        self.csv_path = self.dir / "posts.csv"
        self.md_path = self.dir / "posts.md"
        self.proc: subprocess.Popen | None = None
        self.lock = threading.Lock()

    def add(self, line: str) -> None:
        with self.lock:
            self.lines.append(line)
            if len(self.lines) > MAX_LOG:
                self.lines = self.lines[-MAX_LOG:]

    def set_state(self, state: str) -> None:
        self.state = state
        self.status = xrepost_jobs.STATUS_FOR_STATE.get(state, self.status)

    def snapshot(self, tail: int = 500) -> dict:
        with self.lock:
            lines = self.lines[-tail:]
            posts = list(self.posts)
            progress_done = self.progress_done
        elapsed = (self.ended or time.time()) - self.started
        return {
            "id": self.id,
            "kind": self.kind,
            "state": self.state,
            "status": self.status,
            "started": self.started,
            "ended": self.ended,
            "elapsed": round(elapsed, 1),
            "elapsed_label": fmt_seconds(elapsed),
            "returncode": self.returncode,
            "cancelled": self.cancelled,
            "error": self.error,
            "lines": lines,
            "posts": posts,
            "progress": (
                {"done": progress_done, "total": len(posts)}
                if self.kind == "apply"
                else None
            ),
            "exports": {
                "csv": self.csv_path.exists() and bool(self.posts),
                "md": self.md_path.exists() and bool(self.posts),
            },
            "params": {
                key: value
                for key, value in self.params.items()
                if key not in ("confirm", "key", "preview_id", "only_urls_file")
            },
        }


class App:
    def __init__(
        self,
        *,
        engine: Path,
        history: Path,
        runs: Path,
        token: str,
        accounts: Path | None = None,
        hashtags: Path | None = None,
        verbose: bool = False,
    ):
        self.engine = Path(engine).expanduser()
        self.history = Path(history).expanduser()
        self.runs = xrepost_fs.ensure_dir(Path(runs).expanduser())
        self.accounts, _ = xrepost_accounts.resolve_paths(accounts, self.history)
        self.hashtags = xrepost_hashtags.resolve_path(hashtags, self.history)
        self.token = token
        self.verbose = verbose
        self.auth = xrepost_security.AuthManager(
            token, ttl=SESSION_TTL, idle=SESSION_IDLE
        )
        self.jobs: dict[str, Job] = {}
        self.current: Job | None = None
        self.lock = threading.RLock()
        self._scheduler_stop = threading.Event()
        self._scheduler_thread: threading.Thread | None = None

        state_dir = self.history.parent
        self.job_store = xrepost_jobs.JobStore(self.runs)
        self.profiles = xrepost_filters.ProfileStore(state_dir / "profiles.json")
        self.groups = xrepost_groups.GroupStore(state_dir / "groups.json")
        self.account_meta = xrepost_groups.AccountMetaStore(state_dir / "accounts_meta.json")
        self.inbox = xrepost_inbox.InboxStore(state_dir / "inbox.json")
        self.schedules = xrepost_schedule.ScheduleStore(state_dir / "schedules.json")

        # Los trabajos que quedaron a medias se marcan como interrumpidos; nunca
        # se reanudan solos porque el resultado en X es desconocido.
        self.job_store.recover()
        self.job_store.prune()
        self._prune_jobs()

    # -- autocompletado ------------------------------------------------------
    def suggest_accounts(
        self,
        query: str = "",
        exclude: set[str] | list[str] | tuple[str, ...] = (),
        limit: int = 8,
    ) -> list[dict]:
        return xrepost_accounts.suggest(
            query,
            accounts=self.accounts,
            history=self.history,
            limit=max(1, min(int(limit), 20)),
            exclude=exclude,
        )

    def record_accounts(self, users: str) -> None:
        """Recuerda las cuentas usadas para el autocompletado (sin romper la búsqueda)."""
        try:
            xrepost_accounts.add_accounts(users, self.accounts)
        except OSError:
            pass

    def suggest_hashtags(
        self,
        query: str = "",
        exclude: set[str] | list[str] | tuple[str, ...] = (),
        limit: int = 8,
    ) -> list[dict]:
        return xrepost_hashtags.suggest(
            query,
            hashtags=self.hashtags,
            history=self.history,
            limit=max(1, min(int(limit), 20)),
            exclude=exclude,
        )

    def record_hashtags(self, quote: str) -> None:
        """Recuerda los hashtags del comentario para el autocompletado."""
        if not quote:
            return
        try:
            xrepost_hashtags.add_hashtags(quote, self.hashtags)
        except OSError:
            pass

    def clear_accounts(self) -> bool:
        """Borra las cuentas recordadas (el historial viejo ya no las sugiere)."""
        try:
            return xrepost_accounts.clear_accounts(self.accounts, self.history)
        except OSError:
            return False

    def clear_hashtags(self) -> bool:
        """Borra los hashtags recordados para las citas."""
        try:
            return xrepost_hashtags.clear_hashtags(self.hashtags, self.history)
        except OSError:
            return False

    def resolve_filters(self, params: dict) -> dict:
        """Completa el filtro de un perfil y valida su forma."""
        try:
            if params.get("profile_id") and not params.get("filters"):
                profile = self.profiles.get(str(params["profile_id"]))
                if not profile:
                    raise HttpError(400, "El perfil de filtros ya no existe.")
                params["filters"] = xrepost_filters.normalize_spec(profile.get("filters") or {})
            if params.get("filters"):
                params["filters"] = xrepost_filters.normalize_spec(params["filters"])
        except xrepost_filters.FilterError as exc:
            raise HttpError(400, str(exc))
        return params

    # -- trabajos ------------------------------------------------------------
    def running(self) -> bool:
        with self.lock:
            return bool(self.current is not None and self.current.status == "running")

    def start_job(self, kind: str, params: dict) -> Job:
        with self.lock:
            if self.running():
                raise HttpError(409, "Ya hay una ejecución en curso. Espera o cancélala.")
            self._validate_cdp_endpoint()
            job = Job(kind, params, self.runs)
            self.jobs[job.id] = job
            self.current = job
        self.job_store.create(job.id, kind, params)
        self._prune_jobs()
        threading.Thread(target=self._run_job, args=(job,), daemon=True).start()
        return job

    @staticmethod
    def _validate_cdp_endpoint() -> None:
        """Nunca se lanza el motor contra un CDP remoto o mal formado."""
        try:
            endpoint = xrepost_cdp.parse_endpoint()
        except xrepost_cdp.CdpSecurityError as exc:
            raise HttpError(400, str(exc))
        if endpoint.problems:
            raise HttpError(400, "CDP no válido: " + "; ".join(endpoint.problems))

    def cancel(self) -> bool:
        with self.lock:
            job = self.current
        if not job or job.status != "running":
            return False
        job.cancelled = True
        self._terminate(job)
        return True

    def shutdown(self) -> None:
        """Al cerrar el panel, no dejar el motor (ni Chrome) trabajando solo."""
        self._scheduler_stop.set()
        with self.lock:
            job = self.current
        if not job or job.status != "running":
            return
        job.cancelled = True
        self._terminate(job)
        proc = job.proc
        if proc is None:
            return
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass

    def _command(self, job: Job) -> list[str]:
        if job.kind == "undo":
            if job.params.get("mode") == "url":
                return [str(self.engine), "--undo", job.params["url"]]
            n = int(job.params.get("n") or 0)
            return [str(self.engine), "--undo-last"] + ([str(n)] if n else [])

        p = job.params
        return [
            str(self.engine),
            "--csv",
            str(job.csv_path),
            "--md",
            str(job.md_path),
            p["users"],
            p["from"],
            p["to"],
        ]

    def _environment(self, job: Job) -> dict[str, str]:
        extra = {
            "X_HISTORY": str(self.history),
            "X_ACCOUNTS": str(self.accounts),
            "X_HASHTAGS": str(self.hashtags),
            "X_MODE": "repost",
            "X_FORCE": "0",
            "X_ONLY_URLS_FILE": "",
            "X_UNDO_TARGET": "",
            "X_UNDO_N": "",
            "X_QUOTE": "",
            "NO_COLOR": "1",
            "TERM": "dumb",
        }
        if job.kind == "undo":
            extra["X_DELAY"] = "20"
            return build_env(extra)

        p = job.params
        extra.update(
            {
                "X_USERS": p["users"],
                "X_FROM": p["from"],
                "X_TO": p["to"],
                "X_SKIP_RETWEETS": "0" if p["scope"] == "all" else "1",
                "X_APPLY": "1" if job.kind == "apply" else "0",
                "X_LIMIT": str(p["limit"]),
                "X_DELAY": str(p["delay"]),
                "X_MATCH": p["match"],
                "X_EXCLUDE": p["exclude"],
                "X_QUOTE": p.get("quote", ""),
                "X_CSV": str(job.csv_path),
                "X_MD": str(job.md_path),
            }
        )
        if job.kind == "apply" and p.get("only_urls_file"):
            # Aplicar exactamente lo que el usuario revisó, sin volver a buscar.
            extra["X_ONLY_URLS_FILE"] = str(p["only_urls_file"])
        filters = p.get("filters")
        if filters:
            extra.update(xrepost_filters.to_env(filters))
        return build_env(extra)

    def _run_job(self, job: Job) -> None:
        job.dir.mkdir(parents=True, exist_ok=True)
        job.set_state(xrepost_jobs.RUNNING)
        self.job_store.update(job.id, state=xrepost_jobs.RUNNING, started=job.started)
        try:
            self._validate_engine()
            cmd = self._command(job)
            env = self._environment(job)
            job.add("$ " + " ".join(shlex.quote(part) for part in cmd))
            proc = subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                start_new_session=True,
            )
            job.proc = proc
            if job.cancelled:
                # Se pulsó Cancelar antes de que el proceso llegara a arrancar.
                self._terminate(job)
            threading.Thread(target=self._watchdog, args=(job,), daemon=True).start()

            assert proc.stdout is not None
            for raw in proc.stdout:
                line = ANSI_RE.sub("", raw.rstrip("\n")).replace("\r", "")
                job.add(line)
                if job.kind == "apply":
                    self._track_progress(job, line)
            rc = proc.wait()
            job.returncode = rc

            if job.kind in ("preview", "apply"):
                self._load_posts(job)
                self._sync_inbox(job)

            if job.cancelled:
                job.set_state(xrepost_jobs.CANCELLED)
            elif rc == 0:
                job.set_state(xrepost_jobs.COMPLETED)
            else:
                job.set_state(xrepost_jobs.FAILED)
                job.error = f"El motor terminó con código {rc}."
        except FileNotFoundError as exc:
            job.set_state(xrepost_jobs.FAILED)
            job.error = str(exc)
            job.add(f"Error: {exc}")
        except Exception as exc:  # pragma: no cover - salvaguarda
            job.set_state(xrepost_jobs.FAILED)
            job.error = f"Fallo inesperado: {exc}"
            job.add(job.error)
        finally:
            job.ended = time.time()
            if job.status == "running":
                job.set_state(xrepost_jobs.FAILED)
                job.error = job.error or "La ejecución no terminó correctamente."
            self.job_store.update(
                job.id,
                state=job.state,
                ended=job.ended,
                returncode=job.returncode,
                error=job.error,
                post_count=len(job.posts),
            )
            if job.proc and job.proc.stdout:
                try:
                    job.proc.stdout.close()
                except Exception:
                    pass

    def _validate_engine(self) -> None:
        path = Path(self.engine)
        if not path.exists():
            raise FileNotFoundError(f"No existe el motor: {path}")
        try:
            xrepost_fs.assert_regular_file(path)
        except xrepost_fs.UnsafePathError as exc:
            raise FileNotFoundError(f"Motor no válido: {exc}")

    def _load_posts(self, job: Job) -> None:
        if not job.csv_path.exists():
            return
        try:
            with open(job.csv_path, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                job.posts = [dict(row) for row in reader if row.get("url")]
        except Exception as exc:
            job.add(f"Aviso: no se pudo leer el CSV ({exc}).")

    def _sync_inbox(self, job: Job) -> None:
        """Sincroniza la bandeja con el resultado real de la ejecución.

        Una previsualización añade publicaciones pendientes. Una ejecución
        actualiza el estado de lo aprobado: confirmado → ``verified``, incierto
        → ``unconfirmed`` (no se reintenta solo) y fallo → ``failed``.
        """
        if not job.posts:
            return
        try:
            if job.kind != "apply":
                self.inbox.upsert_from_posts(job.posts, job.params, job.id)
                return

            inverse = {text: code for code, text in xrepost_labels.LABELS.items()}
            confirmed: list[str] = []
            uncertain: list[str] = []
            failed: list[str] = []
            for post in job.posts:
                item_id = xrepost_history.tweet_id(str(post.get("url") or ""))
                if not item_id:
                    continue
                estado = str(post.get("estado") or "").strip().lower()
                result = inverse.get(estado, "")
                if result in ("reposted", "quoted", "already"):
                    confirmed.append(item_id)
                elif result in xrepost_labels.UNCERTAIN_RESULTS or result == "skipped_uncertain":
                    uncertain.append(item_id)
                elif estado.startswith(("no procesado", "pendiente", "solo listado")):
                    continue
                else:
                    failed.append(item_id)

            if confirmed:
                self.inbox.mark(confirmed, xrepost_inbox.VERIFIED, "confirmado en X")
            if uncertain:
                self.inbox.mark(
                    uncertain,
                    xrepost_inbox.UNCONFIRMED,
                    "sin confirmar; revisa tu perfil antes de reintentar",
                )
            if failed:
                self.inbox.mark(failed, xrepost_inbox.FAILED, "el motor no pudo completarlo")
        except (OSError, ValueError) as exc:
            job.add(f"Aviso: no se pudo actualizar la bandeja ({exc}).")

    def _track_progress(self, job: Job, line: str) -> None:
        """Estado por publicación mientras el motor trabaja (apply).

        El motor escribe el CSV inicial («pendiente») antes de empezar y una
        línea «  <estado>: <url>» por cada post procesado: con eso la tabla
        del panel se actualiza en vivo sin esperar al final.
        """
        if not job.posts and job.csv_path.exists():
            self._load_posts(job)
        match = PROGRESS_RE.match(line)
        if not match:
            return
        state, url = match.group(1), match.group(2).rstrip("/")
        with job.lock:
            for post in job.posts:
                if post.get("url", "").rstrip("/") == url:
                    post["estado"] = state
                    break
            job.progress_done += 1

    def _watchdog(self, job: Job) -> None:
        while job.status == "running":
            if time.time() - job.started > MAX_JOB_SECONDS:
                job.add("Tiempo máximo alcanzado; cancelando la ejecución.")
                job.cancelled = True
                job.set_state(xrepost_jobs.TIMED_OUT)
                self._terminate(job)
                return
            time.sleep(1)

    @staticmethod
    def _terminate(job: Job) -> None:
        proc = job.proc
        if not proc or proc.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            return
        threading.Thread(target=App._hard_kill, args=(proc,), daemon=True).start()

    @staticmethod
    def _hard_kill(proc: subprocess.Popen, wait: float = 3.0) -> None:
        time.sleep(wait)
        if proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass

    def _prune_jobs(self) -> None:
        """Conserva los últimos MAX_JOBS trabajos (memoria y disco).

        Nunca toca el trabajo en curso ni la previsualización en la que se
        apoya un ``apply`` en marcha (su ``selected.json`` vive en ese
        directorio). Los directorios huérfanos de sesiones anteriores se
        recortan por fecha de modificación.
        """
        with self.lock:
            ordered = sorted(self.jobs.values(), key=lambda j: j.started, reverse=True)
            keep_ids = {j.id for j in ordered[:MAX_JOBS]}
            if self.current is not None:
                keep_ids.add(self.current.id)
                preview_id = self.current.params.get("preview_id")
                if preview_id:
                    keep_ids.add(preview_id)
            doomed = [j for j in self.jobs.values() if j.id not in keep_ids]
            for job in doomed:
                self.jobs.pop(job.id, None)
            keep_dirs = {j.dir.name for j in self.jobs.values()}
            try:
                dirs = sorted(
                    (p for p in self.runs.iterdir() if p.is_dir()),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
            except OSError:
                dirs = []
            extra = [p for p in dirs[MAX_JOBS:] if p.name not in keep_dirs]
        for job in doomed:
            self._remove_run_dir(job.dir)
        for path in extra:
            self._remove_run_dir(path)

    def _remove_run_dir(self, path: Path) -> None:
        try:
            xrepost_fs.remove_tree(path, self.runs)
        except (OSError, xrepost_fs.UnsafePathError):
            shutil.rmtree(path, ignore_errors=True)

    # -- exportaciones y respaldo -------------------------------------------
    def export_rows(self, rows: list[dict], fmt: str, *, title: str = "Informe de xrepost") -> tuple[bytes, str, str]:
        fmt = fmt.lower()
        if fmt == "csv":
            return xrepost_exports.rows_to_csv(rows).encode("utf-8"), "text/csv; charset=utf-8", "csv"
        if fmt == "md":
            return xrepost_exports.rows_to_markdown(rows, title=title).encode("utf-8"), "text/markdown; charset=utf-8", "md"
        if fmt == "json":
            payload = json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
            return payload.encode("utf-8"), "application/json; charset=utf-8", "json"
        if fmt == "html":
            return xrepost_exports.rows_to_html(rows, title=title).encode("utf-8"), "text/html; charset=utf-8", "html"
        if fmt == "pdf":
            return xrepost_exports.rows_to_pdf(rows, title=title), "application/pdf", "pdf"
        raise HttpError(400, f"Formato de exportación no válido: {fmt}")

    def history_backups(self) -> list[dict]:
        return xrepost_history.list_backups(self.history)

    def make_backup(self, mode: str = "history") -> dict:
        if mode == "bundle":
            target = xrepost_exports.new_backup_path(self.history.parent)
            return xrepost_exports.backup_bundle(self.history.parent, target)
        return xrepost_history.backup(self.history)

    def restore_backup(self, path: str, *, force: bool = False) -> dict:
        candidate = Path(path).expanduser()
        allowed = [Path(item["path"]) for item in self.history_backups()]
        allowed.append(self.history)
        resolved = candidate.resolve()
        if not any(resolved == item.resolve() for item in allowed if item.exists()):
            raise HttpError(400, "Solo se pueden restaurar backups creados por xrepost.")
        if candidate.suffix == ".gz":
            return xrepost_exports.restore_bundle(candidate, self.history.parent)
        return xrepost_history.restore(self.history, candidate, force=force)

    # -- diagnóstico ---------------------------------------------------------
    def cdp_report(self) -> dict:
        try:
            return xrepost_cdp.status()
        except Exception as exc:  # pragma: no cover - salvaguarda
            return {"secure": False, "reachable": False, "problems": [str(exc)]}

    def diagnostics(self) -> dict:
        history = xrepost_history.diagnose(self.history)
        cdp = self.cdp_report()
        engine = Path(self.engine)
        return {
            "history": history,
            "cdp": cdp,
            "engine": {
                "path": str(engine),
                "exists": engine.exists(),
                "regular": engine.is_file() and not engine.is_symlink(),
                "executable": os.access(engine, os.X_OK),
            },
            "storage": {
                "state_dir": str(self.history.parent),
                "runs": str(self.runs),
                "journal_mode": "append-only",
            },
            "auth": {"sessions": self.auth.count()},
            "jobs": {
                "runtime": len(self.jobs),
                "persistent": len(self.job_store.list()),
            },
        }

    # -- programación --------------------------------------------------------
    def run_due_schedules(self) -> list[dict]:
        """Ejecuta previsualizaciones programadas (nunca repostea solo)."""
        started: list[dict] = []
        for item in self.schedules.due():
            try:
                params = validate_repost_params({**item.get("params", {}), "confirm": False}, apply=False)
                params["key"] = params_key(params)
                self.record_accounts(params["users"])
                job = self.start_job("preview", params)
                self.schedules.mark_run(item["id"], job_id=job.id, result="preview started")
                started.append({"schedule": item["id"], "job": job.id})
            except Exception as exc:
                self.schedules.update(
                    item["id"], last_run=now_iso(), last_result=f"error: {exc}"
                )
        return started

    def start_scheduler(self) -> None:
        if self._scheduler_thread is not None:
            return
        self._scheduler_stop.clear()

        def loop() -> None:
            while not self._scheduler_stop.wait(30):
                try:
                    self.run_due_schedules()
                except Exception as exc:  # pragma: no cover - salvaguarda
                    print(f"[xrepost-web] programación: {exc}", file=sys.stderr)

        self._scheduler_thread = threading.Thread(target=loop, daemon=True)
        self._scheduler_thread.start()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "xrepost-web/2.0"
    application: App

    # --- registro ----------------------------------------------------------
    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        if not self.application.verbose:
            return
        message = fmt % args if args else fmt
        message = re.sub(r"(token|csrf)=[^&\s\"']+", r"\1=***", message)
        super().log_message("%s", message)

    def _internal_error(self, exc: Exception) -> None:
        """500 genérico al cliente; el detalle queda solo en el log local (M7)."""
        print(
            f"[xrepost-web] {self.command} {self.path}: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        traceback.print_exc(file=sys.stderr)
        self._send_json({"error": "Error interno del servidor."}, 500)

    # --- autenticación -----------------------------------------------------
    def _cookie(self, name: str) -> str:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        morsel = cookie.get(name)
        return morsel.value if morsel else ""

    def _session(self) -> xrepost_security.Session | None:
        return self.application.auth.get(self._cookie("xrepost_sid") or None)

    def _auth_kind(self) -> str:
        """``header`` (X-Token), ``session`` (cookie + CSRF) o ``cookie`` (legado)."""
        header = self.headers.get("X-Token", "")
        if header and self.application.auth.master_ok(header):
            return "header"
        if self._session() is not None:
            return "session"
        legacy = self.headers.get("Cookie", "")
        if legacy and self.application.auth.master_ok(self._cookie("xrepost_token")):
            return "cookie"
        return ""

    def _token_ok(self) -> bool:
        return bool(self._auth_kind())

    def _require_auth(self) -> str:
        kind = self._auth_kind()
        if kind:
            return kind
        client = xrepost_security.client_id(self)
        wait = self.application.auth.blocked_for(client)
        if wait:
            raise HttpError(429, f"Demasiados intentos fallidos. Espera {wait} s.", retry_after=wait)
        self.application.auth.register_failure(client)
        raise HttpError(401, "No autorizado.")

    def _require_csrf(self) -> str:
        kind = self._require_auth()
        if kind == "header":
            # Una cabecera personalizada no se puede enviar desde otro origen
            # sin un preflight CORS que este servidor no concede.
            return kind
        session = self._session()
        candidate = self.headers.get("X-CSRF-Token", "")
        if kind == "session" and session is not None and self.application.auth.csrf_ok(session, candidate):
            return kind
        raise HttpError(
            403,
            "Falta el token CSRF de la sesión. Recarga el panel o vuelve a iniciar sesión.",
        )

    def _host_ok(self) -> bool:
        port = self.server.server_address[1] if getattr(self, "server", None) else None
        return xrepost_security.host_allowed(self.headers.get("Host", ""), server_port=port)

    def _origin_ok(self) -> bool:
        return xrepost_security.allowed_origin(
            self.headers.get("Origin", ""), self.headers.get("Host", "")
        )

    # --- utilidades HTTP ---------------------------------------------------
    def _security_headers(self) -> None:
        for key, value in SECURITY_HEADERS.items():
            self.send_header(key, value)

    def _send_json(
        self,
        payload: dict,
        status: int = 200,
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if self.close_connection:
            self.send_header("Connection", "close")
        self._security_headers()
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(
        self,
        body: bytes,
        content_type: str,
        status: int = 200,
        *,
        extra: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._security_headers()
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str, *, download: str = "") -> None:
        try:
            body = path.read_bytes()
        except OSError:
            raise HttpError(404, "Archivo no encontrado.")
        extra = {"Content-Disposition": f'attachment; filename="{download}"'} if download else None
        self._send_bytes(body, content_type, extra=extra)

    def _error_page(self, status: int, title: str, detail: str) -> None:
        body = f"""<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;background:#0B1220;color:#F1F5F9;
display:grid;place-items:center;min-height:100vh;margin:0;padding:24px}}
main{{max-width:560px;background:#111C2E;border:1px solid #1B293D;border-radius:16px;padding:28px}}
h1{{font-size:20px;margin:0 0 8px}}p{{color:#94A3B8;margin:0}}
a{{color:#38BDF8}}</style>
<main><h1>{title}</h1><p>{detail}</p><p style="margin-top:16px"><a href="/">Volver al panel</a></p></main></html>"""
        self._send_bytes(body.encode("utf-8"), "text/html; charset=utf-8", status)

    def _read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self.close_connection = True
            raise HttpError(400, "Longitud no válida.")
        length = max(0, length)
        if "application/json" not in (self.headers.get("Content-Type") or "").lower():
            self._drain_body(length)
            raise HttpError(415, "Se esperaba application/json.")
        if length == 0:
            return {}
        if length > MAX_BODY:
            self._drain_body(MAX_BODY)
            self.close_connection = True
            raise HttpError(413, "Petición demasiado grande.")
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise HttpError(400, "JSON no válido.")
        if not isinstance(data, dict):
            raise HttpError(400, "El cuerpo debe ser un objeto JSON.")
        return data

    def _drain_body(self, length: int) -> None:
        """Consume el cuerpo declarado para no desincronizar el keep-alive."""
        remaining = length
        while remaining > 0:
            chunk = self.rfile.read(min(remaining, 65536))
            if not chunk:
                self.close_connection = True
                return
            remaining -= len(chunk)

    # --- rutas -------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        try:
            if not self._host_ok():
                raise HttpError(403, "Host no permitido.")
            path = urlparse(self.path).path
            if path == "/":
                return self._index()
            if path == "/favicon.ico":
                self.send_response(HTTPStatus.NO_CONTENT)
                self.send_header("Content-Length", "0")
                self._security_headers()
                self.end_headers()
                return
            if path.startswith("/static/"):
                self._require_auth()
                return self._static(path[len("/static/"):])
            if path.startswith("/api/"):
                self._require_auth()
                return self._api_get(path)
            raise HttpError(404, "Ruta no encontrada.")
        except HttpError as exc:
            if exc.status == 401 and not self.path.startswith("/api/"):
                self._error_page(401, "Panel bloqueado", "Abre el enlace con token que se mostró en la terminal.")
            else:
                self._send_json({"error": exc.message}, exc.status)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:  # pragma: no cover - salvaguarda
            self._internal_error(exc)

    def _handle_write(self) -> None:
        try:
            # Rechazos antes de leer el cuerpo: sin drenarlo, los bytes que
            # queden se interpretarían como la siguiente petición keep-alive.
            if not self._host_ok():
                self.close_connection = True
                raise HttpError(403, "Host no permitido.")
            if not self._origin_ok():
                self.close_connection = True
                raise HttpError(403, "Origen no permitido.")
            if not self._auth_kind():
                # Si se rechaza antes de leer el cuerpo, la conexión no puede
                # reutilizarse: los bytes pendientes se interpretarían como
                # una petición nueva.
                self.close_connection = True
            self._require_csrf()
            path = urlparse(self.path).path
            data = self._read_json()
            self._api_post(path, data)
        except HttpError as exc:
            payload = {"error": exc.message}
            if exc.retry_after:
                payload["retry_after"] = exc.retry_after
            self._send_json(payload, exc.status)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:  # pragma: no cover - salvaguarda
            self._internal_error(exc)

    def do_POST(self) -> None:  # noqa: N802
        self._handle_write()

    def do_PATCH(self) -> None:  # noqa: N802
        self._handle_write()

    def do_DELETE(self) -> None:  # noqa: N802
        self._handle_write()

    def _index(self) -> None:
        query = parse_qs(urlparse(self.path).query)
        token = (query.get("token") or [""])[0]
        if token:
            client = xrepost_security.client_id(self)
            wait = self.application.auth.blocked_for(client)
            if wait:
                raise HttpError(429, f"Demasiados intentos fallidos. Espera {wait} s.", retry_after=wait)
            if not self.application.auth.master_ok(token):
                self.application.auth.register_failure(client)
                raise HttpError(401, "Enlace no válido.")
            self.application.auth.register_success(client)
            session = self.application.auth.create(
                client=client, user_agent=self.headers.get("User-Agent", "")
            )
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header(
                "Set-Cookie",
                xrepost_security.cookie_header(session.sid, max_age=SESSION_TTL),
            )
            # Compatibilidad con clientes/versiones anteriores: cookie maestra
            # HttpOnly. Las escrituras con esta cookie exigen X-Token o sesión.
            self.send_header(
                "Set-Cookie",
                f"xrepost_token={self.application.token}; Path=/; Max-Age={SESSION_TTL}; "
                "HttpOnly; SameSite=Strict",
            )
            self.send_header("Location", "/")
            self.send_header("Content-Length", "0")
            self._security_headers()
            self.end_headers()
            return
        self._require_auth()
        self._serve_static("index.html", "text/html; charset=utf-8")

    def _static(self, name: str) -> None:
        safe = Path(unquote(name))
        if safe.is_absolute() or ".." in safe.parts:
            raise HttpError(404, "Ruta no encontrada.")
        content_type = mimetypes.guess_type(str(safe))[0] or "application/octet-stream"
        self._serve_static(str(safe), content_type)

    def _serve_static(self, name: str, content_type: str) -> None:
        path = (STATIC_DIR / name).resolve()
        if not path.is_relative_to(STATIC_DIR.resolve()) or not path.is_file():
            raise HttpError(404, "Archivo no encontrado.")
        body = path.read_bytes()
        extra = {"Content-Security-Policy": CSP}
        self._send_bytes(body, content_type, extra=extra)

    # --- GET ---------------------------------------------------------------
    def _api_get(self, path: str) -> None:
        query = parse_qs(urlparse(self.path).query)
        if path == "/api/network":
            return self._send_json(network_status())
        if path == "/api/session":
            session = self._session()
            if session is None:
                session = self.application.auth.create(
                    client=xrepost_security.client_id(self),
                    user_agent=self.headers.get("User-Agent", ""),
                )
                cookie = {"Set-Cookie": xrepost_security.cookie_header(session.sid, max_age=SESSION_TTL)}
            else:
                cookie = None
            return self._send_json(
                {
                    "ok": True,
                    **self.application.auth.describe(session),
                    "token_ok": True,
                },
                extra_headers=cookie,
            )
        if path == "/api/health":
            return self._send_json(
                {
                    "ok": True,
                    "engine": str(self.application.engine),
                    "engine_ok": self.application.engine.exists(),
                    "chrome": chrome_ok(),
                    "history": str(self.application.history),
                    "busy": self.application.running(),
                    "state_dir": str(self.application.history.parent),
                    "version": "2.0",
                }
            )
        if path == "/api/history":
            try:
                limit = int((query.get("n") or ["30"])[0])
            except ValueError:
                limit = 30
            limit = max(1, min(limit, 200))
            return self._send_json({"entries": read_history(self.application.history, limit)})

        if path == "/api/history/diagnostic":
            return self._send_json(xrepost_history.diagnose(self.application.history))

        if path == "/api/hashtags":
            text = (query.get("q") or [""])[0].strip()
            try:
                limit = int((query.get("limit") or ["8"])[0])
            except ValueError:
                limit = 8
            exclude = (query.get("exclude") or [""])[0]
            items = self.application.suggest_hashtags(
                text,
                exclude=xrepost_hashtags.split_tags(exclude),
                limit=limit,
            )
            return self._send_json({"hashtags": items})

        if path == "/api/accounts/all":
            entries = xrepost_accounts.load_accounts(self.application.accounts, self.application.history)
            meta = self.application.account_meta.all()
            stats = {
                str(item.get("handle") or "").lstrip("@").lower(): item
                for item in xrepost_groups.account_stats(self.application.history)
            }
            items = []
            for key, item in entries.items():
                extra = meta.get(key) or {}
                activity = stats.get(key) or {}
                items.append(
                    {
                        "handle": item.get("handle") or key,
                        "count": int(item.get("count") or 0),
                        "last_used": item.get("last_used") or "",
                        "alias": extra.get("alias", ""),
                        "favorite": bool(extra.get("favorite")),
                        "reposts": int(activity.get("reposts") or 0),
                        "quotes": int(activity.get("quotes") or 0),
                        "undone": int(activity.get("undone") or 0),
                        "errors": int(activity.get("errors") or 0),
                        "last_activity": activity.get("last") or "",
                    }
                )
            items.sort(
                key=lambda item: (
                    item["favorite"],
                    item["last_activity"] or item["last_used"] or "",
                    item["count"],
                ),
                reverse=True,
            )
            return self._send_json({"accounts": items})

        if path == "/api/accounts":
            text = (query.get("q") or [""])[0].strip()
            try:
                limit = int((query.get("limit") or ["8"])[0])
            except ValueError:
                limit = 8
            exclude = (query.get("exclude") or [""])[0]
            items = self.application.suggest_accounts(
                text,
                exclude=xrepost_accounts.split_handles(exclude),
                limit=limit,
            )
            meta = self.application.account_meta.all()
            for item in items:
                handle = str(item.get("usuario") or item.get("handle") or "").lstrip("@").lower()
                extra = meta.get(handle)
                if extra:
                    item["alias"] = extra.get("alias", "")
                    item["favorite"] = extra.get("favorite", False)
            return self._send_json({"accounts": items})

        if path == "/api/stats":
            try:
                days = int((query.get("days") or ["30"])[0])
            except ValueError:
                days = 30
            return self._send_json(
                xrepost_stats.compute(
                    self.application.history,
                    jobs=self.application.job_store.list(),
                    inbox=self.application.inbox.list(limit=5000),
                    schedules=self.application.schedules.list(),
                    days=max(1, min(days, 365)),
                )
            )

        if path == "/api/profiles":
            return self._send_json({"profiles": self.application.profiles.list()})

        if path == "/api/groups":
            groups = self.application.groups.list()
            return self._send_json(
                {"groups": groups, "counts": {item["id"]: len(item.get("members", [])) for item in groups}}
            )

        if path == "/api/inbox":
            status = (query.get("status") or [""])[0]
            text = (query.get("q") or [""])[0]
            try:
                limit = int((query.get("limit") or ["200"])[0])
            except ValueError:
                limit = 200
            return self._send_json(
                {
                    "items": self.application.inbox.list(status=status, query=text, limit=limit),
                    "counts": self.application.inbox.counts(),
                }
            )

        if path == "/api/schedules":
            return self._send_json({"schedules": self.application.schedules.list()})

        if path == "/api/backups":
            return self._send_json(
                {"backups": self.application.history_backups()}
            )

        if path == "/api/diagnostics":
            return self._send_json(self.application.diagnostics())

        if path == "/api/cdp":
            return self._send_json(self.application.cdp_report())

        if path == "/api/jobs":
            runtime = {job.id: job for job in self.application.jobs.values()}
            records = self.application.job_store.list(limit=100)
            out = []
            for record in records:
                job = runtime.get(record["id"])
                out.append(job.snapshot(tail=20) if job else record)
            for job in runtime.values():
                if not any(item.get("id") == job.id for item in out):
                    out.append(job.snapshot(tail=20))
            out.sort(key=lambda item: float(item.get("started") or item.get("created") or 0), reverse=True)
            return self._send_json({"jobs": out})

        match = re.fullmatch(r"/api/jobs/([0-9a-f]+)", path)
        if match:
            job = self.application.jobs.get(match.group(1))
            if job:
                return self._send_json(job.snapshot())
            record = self.application.job_store.get(match.group(1))
            if record:
                return self._send_json(record)
            raise HttpError(404, "Ejecución no encontrada.")

        match = re.fullmatch(r"/api/jobs/([0-9a-f]+)/export/(csv|md|json|html|pdf)", path)
        if match:
            job_id, fmt = match.group(1), match.group(2)
            folder = self.application.runs / job_id
            if not xrepost_fs.is_within(self.application.runs, folder):
                raise HttpError(404, "Ejecución no encontrada.")
            job = self.application.jobs.get(job_id)
            rows = job.posts if job else []
            if not rows:
                csv_path = folder / "posts.csv"
                if csv_path.exists():
                    with open(csv_path, newline="", encoding="utf-8") as fh:
                        rows = [dict(row) for row in csv.DictReader(fh) if row.get("url")]
            if not rows:
                raise HttpError(404, "Esa ejecución no generó exportación.")
            body, ctype, ext = self.application.export_rows(rows, fmt, title=f"Ejecución {job_id}")
            return self._send_bytes(
                body,
                ctype,
                extra={"Content-Disposition": f'attachment; filename="xrepost-{job_id}.{ext}"'},
            )

        match = re.fullmatch(r"/api/groups/([0-9a-f]+)/export", path)
        if match:
            group = self.application.groups.get(match.group(1))
            if not group:
                raise HttpError(404, "Grupo no encontrado.")
            fmt = (query.get("format") or ["csv"])[0]
            if fmt == "json":
                payload = json.dumps(group, ensure_ascii=False, indent=2) + "\n"
                return self._send_bytes(
                    payload.encode("utf-8"),
                    "application/json; charset=utf-8",
                    extra={"Content-Disposition": f'attachment; filename="grupo-{group["id"]}.json"'},
                )
            body = xrepost_groups.GroupStore(self.application.groups.path).export_csv(group["id"])
            return self._send_bytes(
                body.encode("utf-8"),
                "text/csv; charset=utf-8",
                extra={"Content-Disposition": f'attachment; filename="grupo-{group["id"]}.csv"'},
            )

        raise HttpError(404, "Ruta no encontrada.")

    # --- POST / PATCH / DELETE --------------------------------------------
    def _api_post(self, path: str, data: dict) -> None:
        if path == "/api/session/rotate":
            session = self._session()
            if session is None:
                raise HttpError(401, "No hay sesión que rotar.")
            fresh = self.application.auth.rotate(session.sid, client=xrepost_security.client_id(self))
            if fresh is None:
                raise HttpError(401, "La sesión ya no es válida.")
            self._send_json(
                {"ok": True, **self.application.auth.describe(fresh)},
                extra_headers={"Set-Cookie": xrepost_security.cookie_header(fresh.sid, max_age=SESSION_TTL)},
            )
            return
        if path == "/api/session/logout":
            session = self._session()
            self.application.auth.revoke(session.sid if session else None)
            self._send_json(
                {"ok": True},
                extra_headers={"Set-Cookie": xrepost_security.clear_cookie_header()},
            )
            return

        if path == "/api/network":
            return self._api_network_set(data)
        if path == "/api/network/restart":
            return self._api_network_restart()
        if path == "/api/preview":
            return self._api_preview(data)
        if path == "/api/apply":
            return self._api_apply(data)
        if path == "/api/undo":
            return self._api_undo(data)
        if path == "/api/cancel":
            return self._api_cancel()
        if path == "/api/accounts/clear":
            return self._api_clear_accounts()
        if path == "/api/hashtags/clear":
            return self._api_clear_hashtags()
        if path == "/api/export":
            return self._api_export(data)
        if path == "/api/filters/validate":
            return self._api_validate_filter(data)
        if path == "/api/profiles":
            return self._api_profile_save(data)
        match = re.fullmatch(r"/api/profiles/([0-9a-f]+)/duplicate", path)
        if match:
            profile = self.application.profiles.duplicate(match.group(1), str(data.get("name") or ""))
            return self._send_json({"ok": True, "profile": profile})
        match = re.fullmatch(r"/api/profiles/([0-9a-f]+)", path)
        if match:
            removed = self.application.profiles.delete(match.group(1))
            if not removed:
                raise HttpError(404, "Perfil no encontrado.")
            return self._send_json({"ok": True, "deleted": True})
        if path == "/api/profiles/import":
            try:
                saved = self.application.profiles.import_data(data)
            except xrepost_filters.FilterError as exc:
                raise HttpError(400, str(exc))
            return self._send_json({"ok": True, "profiles": saved})

        if path == "/api/groups":
            try:
                group = self.application.groups.create(
                    str(data.get("name") or ""),
                    str(data.get("description") or ""),
                    data.get("members") or [],
                )
            except (ValueError, xrepost_filters.FilterError) as exc:
                raise HttpError(400, str(exc))
            return self._send_json({"ok": True, "group": group}, 201)
        match = re.fullmatch(r"/api/groups/([0-9a-f]+)/members", path)
        if match:
            return self._api_group_members(match.group(1), data)
        match = re.fullmatch(r"/api/groups/([0-9a-f]+)/import", path)
        if match:
            try:
                parsed = self.application.groups.import_into(
                    match.group(1), str(data.get("text") or ""), replace=bool(data.get("replace"))
                )
            except KeyError:
                raise HttpError(404, "Grupo no encontrado.")
            except ValueError as exc:
                raise HttpError(400, str(exc))
            return self._send_json({"ok": True, **parsed})
        match = re.fullmatch(r"/api/groups/([0-9a-f]+)", path)
        if match:
            fields = {
                key: data[key]
                for key in ("name", "description", "members")
                if key in data
            }
            try:
                group = self.application.groups.update(match.group(1), **fields)
            except KeyError:
                raise HttpError(404, "Grupo no encontrado.")
            except ValueError as exc:
                raise HttpError(400, str(exc))
            return self._send_json({"ok": True, "group": group})
        match = re.fullmatch(r"/api/groups/([0-9a-f]+)/delete", path)
        if match:
            if not self.application.groups.delete(match.group(1)):
                raise HttpError(404, "Grupo no encontrado.")
            return self._send_json({"ok": True, "deleted": True})

        if path == "/api/accounts/meta":
            handle = str(data.get("handle") or "")
            try:
                item = self.application.account_meta.set(
                    handle,
                    alias=data.get("alias") if "alias" in data else None,
                    favorite=data.get("favorite") if "favorite" in data else None,
                )
            except ValueError as exc:
                raise HttpError(400, str(exc))
            return self._send_json({"ok": True, "account": item})

        if path == "/api/inbox/decide":
            ids = data.get("ids")
            if not isinstance(ids, list) or not all(isinstance(item, (str, int)) for item in ids):
                raise HttpError(400, "Lista de publicaciones no válida.")
            try:
                result = self.application.inbox.decide([str(item) for item in ids], str(data.get("status") or ""))
            except ValueError as exc:
                raise HttpError(400, str(exc))
            return self._send_json({"ok": True, **result})
        if path == "/api/inbox/apply":
            return self._api_inbox_apply(data)
        if path == "/api/inbox/import":
            items = data.get("items")
            if not isinstance(items, list):
                raise HttpError(400, "El archivo no contiene una lista de elementos.")
            count = self.application.inbox.import_items(items)
            return self._send_json({"ok": True, "imported": count})

        if path == "/api/schedules":
            try:
                item = self.application.schedules.create(
                    str(data.get("name") or ""),
                    data.get("params") or {},
                    frequency=str(data.get("frequency") or ""),
                    run_at=str(data.get("run_at") or ""),
                    enabled=bool(data.get("enabled", True)),
                    notify=bool(data.get("notify", True)),
                )
            except ValueError as exc:
                raise HttpError(400, str(exc))
            return self._send_json({"ok": True, "schedule": item}, 201)
        match = re.fullmatch(r"/api/schedules/([0-9a-f]+)/run", path)
        if match:
            item = self.application.schedules.get(match.group(1))
            if not item:
                raise HttpError(404, "Programación no encontrada.")
            params = validate_repost_params({**item.get("params", {}), "confirm": False}, apply=False)
            params["key"] = params_key(params)
            self.application.record_accounts(params["users"])
            job = self.application.start_job("preview", params)
            self.application.schedules.mark_run(item["id"], job_id=job.id, result="manual")
            return self._send_json({"ok": True, "id": job.id}, 202)
        match = re.fullmatch(r"/api/schedules/([0-9a-f]+)", path)
        if match:
            fields = {
                key: data[key]
                for key in ("name", "enabled", "notify", "frequency", "run_at", "params")
                if key in data
            }
            try:
                item = self.application.schedules.update(match.group(1), **fields)
            except KeyError:
                raise HttpError(404, "Programación no encontrada.")
            except ValueError as exc:
                raise HttpError(400, str(exc))
            return self._send_json({"ok": True, "schedule": item})
        match = re.fullmatch(r"/api/schedules/([0-9a-f]+)/delete", path)
        if match:
            if not self.application.schedules.delete(match.group(1)):
                raise HttpError(404, "Programación no encontrada.")
            return self._send_json({"ok": True, "deleted": True})

        if path == "/api/backup":
            mode = str(data.get("mode") or "history")
            try:
                return self._send_json({"ok": True, "backup": self.application.make_backup(mode)})
            except (OSError, ValueError) as exc:
                raise HttpError(400, f"No se pudo crear el backup: {exc}")
        if path == "/api/restore":
            try:
                return self._send_json(
                    {
                        "ok": True,
                        "restore": self.application.restore_backup(
                            str(data.get("path") or ""), force=bool(data.get("force"))
                        ),
                    }
                )
            except FileNotFoundError as exc:
                raise HttpError(404, str(exc))
            except (OSError, ValueError, xrepost_fs.UnsafePathError) as exc:
                raise HttpError(400, f"No se pudo restaurar: {exc}")

        if path == "/api/history/backup":
            try:
                return self._send_json({"ok": True, "backup": self.application.make_backup("history")})
            except (OSError, ValueError) as exc:
                raise HttpError(400, f"No se pudo crear el backup: {exc}")

        raise HttpError(404, "Ruta no encontrada.")

    # --- endpoints concretos ------------------------------------------------
    def _api_network_set(self, data: dict) -> None:
        try:
            cfg = xrepost_network.save_config(data)
        except ValueError as exc:
            raise HttpError(400, str(exc))
        print(f"[xrepost-web] red → {cfg['mode']}", file=sys.stderr)
        self._send_json(network_status())

    def _api_network_restart(self) -> None:
        if self.application.running():
            raise HttpError(409, "Hay una ejecución en curso. Espera antes de cambiar de red.")
        restart_chrome()
        self._send_json({"success": True, **network_status()})

    def _api_preview(self, data: dict) -> None:
        params = validate_repost_params(data, apply=False)
        self.application.resolve_filters(params)
        params["key"] = params_key(params)
        self.application.record_accounts(params["users"])
        self.application.record_hashtags(params["quote"])
        job = self.application.start_job("preview", params)
        self._send_json({"id": job.id, "state": job.state}, 202)

    def _api_apply(self, data: dict) -> None:
        params = validate_repost_params(data, apply=True)
        self.application.resolve_filters(params)
        preview_id = str(data.get("preview_id", ""))
        preview = self.application.jobs.get(preview_id)
        if not preview or preview.kind != "preview":
            raise HttpError(400, "Primero debes previsualizar el listado.")
        if preview.status != "done":
            raise HttpError(400, "La previsualización no ha terminado correctamente.")
        if preview.params.get("key") != params_key(params):
            raise HttpError(400, "Los datos cambiaron desde la previsualización. Vuelve a previsualizar.")
        if not preview.posts:
            raise HttpError(400, "La previsualización no tiene publicaciones para repostear.")

        chosen = preview.posts
        if "selected_urls" in data:
            raw_urls = data.get("selected_urls")
            if not isinstance(raw_urls, list) or not all(isinstance(u, str) for u in raw_urls):
                raise HttpError(400, "La selección de publicaciones no es válida.")
            wanted = {u.rstrip("/") for u in raw_urls}
            available = {p.get("url", "").rstrip("/") for p in preview.posts}
            if wanted - available:
                raise HttpError(400, "Hay publicaciones seleccionadas que no están en la previsualización.")
            chosen = [p for p in preview.posts if p.get("url", "").rstrip("/") in wanted]
            if not chosen:
                raise HttpError(400, "Selecciona al menos una publicación para repostear.")

        preview.dir.mkdir(parents=True, exist_ok=True)
        selected = preview.dir / "selected.json"
        xrepost_fs.write_json(selected, chosen)
        params["only_urls_file"] = str(selected)
        job = self.application.start_job("apply", params)
        job.params["preview_id"] = preview_id
        self._send_json({"id": job.id, "state": job.state}, 202)

    def _api_inbox_apply(self, data: dict) -> None:
        ids = data.get("ids")
        if ids is not None and (
            not isinstance(ids, list) or not all(isinstance(item, (str, int)) for item in ids)
        ):
            raise HttpError(400, "Selección de bandeja no válida.")
        selected = self.application.inbox.list(status=xrepost_inbox.APPROVED, limit=5000)
        if ids:
            wanted = {str(item) for item in ids}
            selected = [item for item in selected if str(item.get("id")) in wanted]
        if not selected:
            raise HttpError(400, "No hay publicaciones aprobadas para ejecutar.")

        searches = [item.get("search") or {} for item in selected]
        base = dict(searches[0])
        users = str(base.get("users") or "")
        if not users:
            users = ",".join(sorted({str(item.get("handle") or "") for item in selected if item.get("handle")}))
        if not users:
            raise HttpError(400, "Las publicaciones no tienen cuenta asociada.")
        payload = {
            "users": users,
            "from": base.get("from") or "2006-01-01",
            "to": base.get("to") or dt.date.today().isoformat(),
            "scope": "all",
            "limit": max(1, min(len(selected), 50)),
            "delay": float(data.get("delay") or 20),
            "quote": base.get("quote") or "",
            "confirm": True,
        }
        params = validate_repost_params(payload, apply=True)
        folder = xrepost_fs.ensure_dir(self.application.runs / f"inbox-{secrets.token_hex(4)}")
        selected_file = folder / "selected.json"
        rows = [
            {
                "fecha": item.get("date", ""),
                "autor": item.get("author", ""),
                "usuario": "@" + str(item.get("handle", "")),
                "texto": item.get("text", ""),
                "url": item.get("url", ""),
                "estado": "aprobado",
            }
            for item in selected
        ]
        xrepost_fs.write_json(selected_file, rows)
        params["only_urls_file"] = str(selected_file)
        job = self.application.start_job("apply", params)
        self.application.inbox.mark([str(item.get("id")) for item in selected], xrepost_inbox.QUEUED)
        self._send_json({"id": job.id, "state": job.state, "count": len(selected)}, 202)

    def _api_undo(self, data: dict) -> None:
        mode = str(data.get("mode", ""))
        if mode == "url":
            url = str(data.get("url", "")).strip()
            if not STATUS_RE.fullmatch(url):
                raise HttpError(400, "URL de post no válida.")
            params = {"mode": "url", "url": url}
        elif mode == "last":
            try:
                n = int(data.get("n") or 0)
            except (TypeError, ValueError):
                raise HttpError(400, "Número de reposts no válido.")
            if not 0 <= n <= 50:
                raise HttpError(400, "El número debe estar entre 0 y 50.")
            params = {"mode": "last", "n": n}
        else:
            raise HttpError(400, "Modo de deshacer no válido.")

        job = self.application.start_job("undo", params)
        self._send_json({"id": job.id, "state": job.state}, 202)

    def _api_cancel(self) -> None:
        cancelled = self.application.cancel()
        self._send_json({"ok": True, "cancelled": cancelled})

    def _api_clear_accounts(self) -> None:
        if not self.application.clear_accounts():
            raise HttpError(500, "No se pudo borrar el historial de cuentas.")
        self._send_json({"ok": True})

    def _api_clear_hashtags(self) -> None:
        if not self.application.clear_hashtags():
            raise HttpError(500, "No se pudo borrar el historial de hashtags.")
        self._send_json({"ok": True})

    def _api_export(self, data: dict) -> None:
        fmt = str(data.get("format") or "csv").lower()
        rows = data.get("rows")
        if rows is None and data.get("job_id"):
            job = self.application.jobs.get(str(data["job_id"]))
            rows = job.posts if job else []
        if rows is None:
            rows = read_history(self.application.history, 200)
        if not isinstance(rows, list):
            raise HttpError(400, "Las filas de exportación no son válidas.")
        clean = [row for row in rows if isinstance(row, dict)]
        body, ctype, ext = self.application.export_rows(
            clean, fmt, title=str(data.get("title") or "Informe de xrepost")
        )
        self._send_bytes(
            body,
            ctype,
            extra={"Content-Disposition": f'attachment; filename="xrepost-export.{ext}"'},
        )

    def _api_validate_filter(self, data: dict) -> None:
        try:
            spec = xrepost_filters.normalize_spec(data.get("filters") or data)
        except xrepost_filters.FilterError as exc:
            raise HttpError(400, str(exc))
        return self._send_json({"ok": True, "filters": spec, "env": xrepost_filters.to_env(spec)})

    def _api_profile_save(self, data: dict) -> None:
        try:
            profile = self.application.profiles.save(
                str(data.get("name") or ""),
                data.get("filters") or {},
                profile_id=str(data.get("id") or ""),
            )
        except xrepost_filters.FilterError as exc:
            raise HttpError(400, str(exc))
        return self._send_json({"ok": True, "profile": profile}, 201)

    def _api_group_members(self, group_id: str, data: dict) -> None:
        handles = data.get("handles") or data.get("members") or []
        if not isinstance(handles, list):
            raise HttpError(400, "Lista de cuentas no válida.")
        try:
            if data.get("action") == "remove":
                group = self.application.groups.remove_members(group_id, handles)
            else:
                group = self.application.groups.add_members(group_id, handles)
        except KeyError:
            raise HttpError(404, "Grupo no encontrado.")
        except ValueError as exc:
            raise HttpError(400, str(exc))
        return self._send_json({"ok": True, "group": group})


def make_handler(app: App):
    class BoundHandler(Handler):
        application = app

    return BoundHandler


def create_server(app: App, port: int, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), make_handler(app))
    httpd.daemon_threads = True
    return httpd


def open_panel(url: str) -> None:
    """Abre el panel en una instancia de Chrome aparte (no la de CDP)."""
    profile = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "xrepost-web" / "panel-profile"
    try:
        profile.mkdir(parents=True, exist_ok=True)
    except OSError:
        profile = Path.home() / ".xrepost-web-panel"

    for name in ("google-chrome", "chromium", "chromium-browser"):
        exe = shutil.which(name)
        if not exe:
            continue
        try:
            subprocess.Popen(
                [
                    exe,
                    f"--user-data-dir={profile}",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-sync",
                    "--new-window",
                    url,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return
        except OSError:
            continue

    try:
        webbrowser.open(url)
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Panel web local para xrepost (escucha solo en 127.0.0.1)."
    )
    parser.add_argument("--port", type=int, default=8765, help="Puerto (0 = aleatorio; por defecto 8765).")
    parser.add_argument("--host", default="127.0.0.1", help="Interfaz de escucha (no la expongas a la red).")
    parser.add_argument("--token", default="", help="Token fijo (por defecto se genera uno aleatorio).")
    parser.add_argument(
        "--token-file",
        default="",
        help="Archivo 0600 con el token (se crea si no existe). Evita el token en el log.",
    )
    parser.add_argument(
        "--bootstrap-file",
        default="",
        help="Archivo 0600 donde escribir el enlace de arranque con token.",
    )
    parser.add_argument(
        "--engine",
        default=os.environ.get("XREPOST_ENGINE", str(DEFAULT_ENGINE)),
        help="Ruta a xrepost.sh.",
    )
    parser.add_argument(
        "--history",
        default=str(default_history()),
        help="Ruta al historial JSONL.",
    )
    parser.add_argument(
        "--accounts",
        default=os.environ.get("X_ACCOUNTS", ""),
        help="Ruta de las cuentas recordadas (por defecto, junto al historial).",
    )
    parser.add_argument(
        "--hashtags",
        default=os.environ.get("X_HASHTAGS", ""),
        help="Ruta de los hashtags recordados (por defecto, junto al historial).",
    )
    parser.add_argument("--runs", default=str(DEFAULT_RUNS), help="Carpeta de ejecuciones y exportaciones.")
    parser.add_argument("--no-open", action="store_true", help="No abrir el navegador automáticamente.")
    parser.add_argument("--no-scheduler", action="store_true", help="No ejecutar la programación.")
    parser.add_argument("--verbose", action="store_true", help="Registrar cada petición HTTP (sin secretos).")
    args = parser.parse_args(argv)

    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print(
            "Error: el panel solo puede escuchar en loopback "
            "(127.0.0.1, localhost o ::1); no se expone a la red.",
            file=sys.stderr,
        )
        return 2

    token = args.token
    if not token and args.token_file:
        token_path = Path(args.token_file).expanduser()
        token = (xrepost_fs.read_text(token_path, default="") or "").strip()
        if not token:
            token = secrets.token_urlsafe(32)
            xrepost_fs.atomic_write(token_path, token + "\n")
    if not token:
        token = secrets.token_urlsafe(32)
    try:
        app = App(
            engine=Path(args.engine),
            history=Path(args.history),
            runs=Path(args.runs),
            accounts=Path(args.accounts) if args.accounts else None,
            hashtags=Path(args.hashtags) if args.hashtags else None,
            token=token,
            verbose=args.verbose,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    ports = [args.port] if args.port == 0 else ([args.port] if args.port != 8765 else [8765, 8766, 8767, 8768, 8769])
    httpd: ThreadingHTTPServer | None = None
    last_error: OSError | None = None
    for port in ports:
        try:
            httpd = create_server(app, port, args.host)
            break
        except OSError as exc:
            last_error = exc
    if httpd is None:
        print(f"No se pudo abrir el puerto: {last_error}", file=sys.stderr)
        return 1

    if not args.no_scheduler:
        app.start_scheduler()

    port = httpd.server_address[1]
    url = f"http://127.0.0.1:{port}/?token={token}"
    shown = url
    if args.bootstrap_file:
        xrepost_fs.atomic_write(Path(args.bootstrap_file).expanduser(), url + "\n")
        shown = f"http://127.0.0.1:{port}/"
    print()
    print("  xrepost · panel local")
    print(f"  Panel:     {shown}")
    print(f"  Motor:     {app.engine}")
    print(f"  Historial: {app.history}")
    print(f"  Cuentas:   {app.accounts}")
    print(f"  Hashtags:  {app.hashtags}")
    print("  Solo escucha en 127.0.0.1. Ctrl-C para detener.")
    print("  El enlace de arriba caduca en cuanto se abre: después se usa una sesión.")
    print()

    if not args.no_open:
        open_panel(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nCerrando panel…")
    finally:
        app.shutdown()
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
