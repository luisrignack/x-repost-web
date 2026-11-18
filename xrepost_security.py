#!/usr/bin/env python3
"""Autenticación, sesiones y CSRF del panel local.

Diseño:

* El token maestro (``--token`` o uno aleatorio de 32 bytes) ya **no** se usa
  como credencial permanente en cada petición. Sirve para crear una sesión.
* Cada sesión tiene un identificador aleatorio (cookie ``HttpOnly``), un token
  CSRF independiente y caducidad absoluta y por inactividad.
* Las sesiones se pueden rotar (al autenticarse de nuevo) y revocar (individual
  o todas). Se guardan solo en memoria: al cerrar el panel dejan de valer.
* Comparaciones con ``hmac.compare_digest`` para no filtrar el token por tiempo.
* Límite de intentos fallidos por IP y global (fuerza bruta) con espera
  progresiva. Un acierto limpia el contador.
* CSRF: el cliente debe enviar ``X-CSRF-Token`` en toda petición que modifica
  estado; además se valida ``Origin``/``Host`` en el servidor.

El panel sigue aceptando ``X-Token`` para clientes de línea de comandos, pero
solo para *crear* la sesión (``GET /api/session``); las operaciones de escritura
exigen el CSRF de esa sesión.
"""

from __future__ import annotations

import hmac
import secrets
import threading
import time
from dataclasses import dataclass, field


class AuthError(Exception):
    def __init__(self, message: str, *, status: int = 401, retry_after: int = 0):
        super().__init__(message)
        self.message = message
        self.status = status
        self.retry_after = retry_after


@dataclass
class Session:
    sid: str
    csrf: str
    created: float
    last_seen: float
    absolute_expiry: float
    idle_expiry: float
    client: str = ""
    user_agent: str = ""
    rotations: int = 0


@dataclass
class FailureBucket:
    count: int = 0
    first: float = 0.0
    blocked_until: float = 0.0


DEFAULT_TTL = 8 * 3600
DEFAULT_IDLE = 30 * 60
DEFAULT_MAX_FAILURES = 8
DEFAULT_WINDOW = 5 * 60
DEFAULT_BLOCK = 60


class AuthManager:
    def __init__(
        self,
        master_token: str,
        *,
        ttl: float = DEFAULT_TTL,
        idle: float = DEFAULT_IDLE,
        max_failures: int = DEFAULT_MAX_FAILURES,
        window: float = DEFAULT_WINDOW,
        block: float = DEFAULT_BLOCK,
        clock=time.time,
    ):
        if not master_token or len(master_token) < 8:
            raise ValueError("El token maestro debe tener al menos 8 caracteres")
        self._token = master_token
        self.ttl = ttl
        self.idle = idle
        self.max_failures = max_failures
        self.window = window
        self.block = block
        self.clock = clock
        self._sessions: dict[str, Session] = {}
        self._failures: dict[str, FailureBucket] = {}
        self._lock = threading.RLock()

    # -- token maestro ---------------------------------------------------
    def master_ok(self, candidate: str | None) -> bool:
        if not candidate:
            return False
        return hmac.compare_digest(str(candidate), self._token)

    # -- fuerza bruta ----------------------------------------------------
    def _bucket(self, client: str) -> FailureBucket:
        bucket = self._failures.get(client)
        now = self.clock()
        if bucket is None or (now - bucket.first) > self.window and bucket.blocked_until <= now:
            bucket = FailureBucket(first=now)
            self._failures[client] = bucket
        return bucket

    def blocked_for(self, client: str) -> int:
        with self._lock:
            bucket = self._bucket(client)
            remaining = bucket.blocked_until - self.clock()
            return int(remaining) if remaining > 0 else 0

    def register_failure(self, client: str) -> int:
        """Anota un fallo; devuelve los segundos de bloqueo (0 si aún no)."""
        with self._lock:
            bucket = self._bucket(client)
            bucket.count += 1
            if bucket.count >= self.max_failures:
                bucket.blocked_until = self.clock() + self.block
                bucket.count = 0
                bucket.first = self.clock()
                return int(self.block)
            return 0

    def register_success(self, client: str) -> None:
        with self._lock:
            self._failures.pop(client, None)

    # -- sesiones --------------------------------------------------------
    def _new_session(self, client: str, user_agent: str = "") -> Session:
        now = self.clock()
        session = Session(
            sid=secrets.token_urlsafe(32),
            csrf=secrets.token_urlsafe(32),
            created=now,
            last_seen=now,
            absolute_expiry=now + self.ttl,
            idle_expiry=now + self.idle,
            client=client,
            user_agent=user_agent[:200],
        )
        self._sessions[session.sid] = session
        return session

    def create(self, client: str = "", user_agent: str = "") -> Session:
        with self._lock:
            self._prune()
            return self._new_session(client, user_agent)

    def get(self, sid: str | None, *, touch: bool = True) -> Session | None:
        if not sid:
            return None
        with self._lock:
            session = self._sessions.get(sid)
            if session is None:
                return None
            now = self.clock()
            if now >= session.absolute_expiry or now >= session.idle_expiry:
                self._sessions.pop(sid, None)
                return None
            if touch:
                session.last_seen = now
                session.idle_expiry = now + self.idle
            return session

    def rotate(self, sid: str | None, client: str = "") -> Session | None:
        """Invalida la sesión anterior y crea una nueva (fijación de sesión)."""
        with self._lock:
            old = self.get(sid, touch=False) if sid else None
            if old is not None:
                self._sessions.pop(old.sid, None)
                session = self._new_session(client or old.client, old.user_agent)
                session.rotations = old.rotations + 1
                return session
            return None

    def revoke(self, sid: str | None) -> bool:
        with self._lock:
            return bool(sid and self._sessions.pop(sid, None))

    def revoke_all(self) -> int:
        with self._lock:
            count = len(self._sessions)
            self._sessions.clear()
            return count

    def csrf_ok(self, session: Session | None, candidate: str | None) -> bool:
        if session is None or not candidate:
            return False
        return hmac.compare_digest(str(candidate), session.csrf)

    def count(self) -> int:
        with self._lock:
            self._prune()
            return len(self._sessions)

    def describe(self, session: Session | None) -> dict:
        if session is None:
            return {"authenticated": False}
        now = self.clock()
        return {
            "authenticated": True,
            "created": int(session.created),
            "expires_in": max(0, int(session.absolute_expiry - now)),
            "idle_expires_in": max(0, int(session.idle_expiry - now)),
            "rotations": session.rotations,
            "csrf": session.csrf,
        }

    def _prune(self) -> None:
        now = self.clock()
        expired = [
            sid
            for sid, session in self._sessions.items()
            if now >= session.absolute_expiry or now >= session.idle_expiry
        ]
        for sid in expired:
            self._sessions.pop(sid, None)
        stale = [
            client
            for client, bucket in self._failures.items()
            if bucket.blocked_until <= now and (now - bucket.first) > self.window
        ]
        for client in stale:
            self._failures.pop(client, None)


def cookie_header(sid: str, *, secure: bool = False, max_age: int = DEFAULT_TTL) -> str:
    """Cookie de sesión: HttpOnly, SameSite=Strict, sin dominio."""
    parts = [
        f"xrepost_sid={sid}",
        "Path=/",
        f"Max-Age={int(max_age)}",
        "HttpOnly",
        "SameSite=Strict",
    ]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def clear_cookie_header(*, secure: bool = False) -> str:
    parts = ["xrepost_sid=", "Path=/", "Max-Age=0", "HttpOnly", "SameSite=Strict"]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def client_id(handler) -> str:
    """Identificador de cliente para el límite de intentos (siempre loopback)."""
    try:
        return handler.client_address[0]
    except (AttributeError, IndexError, TypeError):
        return "local"


def allowed_origin(origin: str, host_header: str, *, scheme: str = "http") -> bool:
    """``Origin`` exacto (esquema, host y puerto) contra el ``Host`` recibido."""
    if not origin:
        return True
    from urllib.parse import urlparse

    parsed = urlparse(origin)
    if parsed.scheme != scheme:
        return False
    if parsed.username or parsed.password:
        return False
    host = urlparse("//" + (host_header or "")).hostname
    port = urlparse("//" + (host_header or "")).port
    if (parsed.hostname or "").lower() != (host or "").lower():
        return False
    if (parsed.port or (80 if scheme == "http" else 443)) != (
        port or (80 if scheme == "http" else 443)
    ):
        return False
    return True


def host_allowed(host_header: str, *, server_port: int | None = None) -> bool:
    """Solo loopback y, si el cliente indica puerto, el del servidor."""
    from urllib.parse import urlparse

    parsed = urlparse("//" + (host_header or ""))
    hostname = (parsed.hostname or "").lower()
    if hostname not in {"127.0.0.1", "localhost", "::1"}:
        return False
    try:
        port = parsed.port
    except ValueError:
        return False
    if port is not None and server_port is not None and port != server_port:
        return False
    return True
