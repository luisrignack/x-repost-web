#!/usr/bin/env python3
"""Validación del endpoint CDP de Chrome.

Chrome DevTools Protocol da control total sobre una sesión autenticada de X. El
panel y el motor solo deben hablar con un Chrome *local*, arrancado con el
perfil de la aplicación y escuchando en loopback.

Este módulo comprueba, sin depender de terceros:

* la URL es ``http://`` + host de loopback literal + puerto explícito, sin
  credenciales ni rutas;
* ``/json/version`` responde y se identifica como Chrome/Chromium;
* el ``webSocketDebuggerUrl`` anunciado también apunta a loopback;
* el puerto aparece escuchando solo en loopback (``/proc/net/tcp``);
* existe un proceso Chrome con ``--remote-debugging-port=<puerto>`` y el
  ``--user-data-dir`` esperado (el perfil privado de xrepost), y no varios;
* el perfil no es el perfil personal habitual de Chrome.

Si algo falla, ``status()`` lo explica y las operaciones que actúan sobre X se
bloquean. Nunca se sigue una redirección HTTP hacia otro host.
"""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DEFAULT_CDP = "http://127.0.0.1:9222"
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
FORBIDDEN_PROFILES = (
    "~/.config/google-chrome",
    "~/.config/chromium",
    "~/.config/chromium-browser",
    "~/snap/chromium",
)
MAX_PROBE_BYTES = 256 * 1024


class CdpSecurityError(RuntimeError):
    """El endpoint CDP no cumple las condiciones de seguridad."""


@dataclass
class Endpoint:
    url: str
    host: str
    port: int
    problems: list[str] = field(default_factory=list)

    @property
    def base(self) -> str:
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"http://{host}:{self.port}"


def default_profile() -> Path:
    raw = os.environ.get("XREPOST_CHROME_PROFILE", "")
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.home() / ".local" / "state" / "xrepost" / "chrome-profile").resolve()


def parse_endpoint(value: str | None = None) -> Endpoint:
    raw = (value if value is not None else os.environ.get("BU_CDP_URL", DEFAULT_CDP)).strip()
    problems: list[str] = []
    try:
        parsed = urlparse(raw)
    except ValueError as exc:
        raise CdpSecurityError(f"URL CDP no válida: {exc}") from exc
    if parsed.scheme != "http":
        problems.append("el esquema debe ser http (no https, ws ni file)")
    if parsed.username or parsed.password:
        problems.append("la URL no puede llevar credenciales")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        problems.append("la URL no puede llevar ruta, query ni fragmento")
    host = (parsed.hostname or "").lower()
    if host not in LOOPBACK_HOSTS:
        problems.append(f"el host {host!r} no es loopback (usa 127.0.0.1, localhost o ::1)")
    port = parsed.port or 0
    if parsed.port is None:
        problems.append("falta el puerto explícito")
    elif not 1 <= port <= 65535:
        problems.append(f"puerto fuera de rango: {port}")
    return Endpoint(url=raw, host=host, port=port, problems=problems)


def _is_loopback_ip(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return value in LOOPBACK_HOSTS


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        raise urllib.error.HTTPError(req.full_url, code, "redirección rechazada", headers, fp)


def probe(endpoint: Endpoint, timeout: float = 1.5) -> dict:
    """Consulta /json/version sin seguir redirecciones y con límite de tamaño."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)
    result: dict[str, Any] = {"ok": False, "browser": "", "websocket": "", "problems": []}
    try:
        request = urllib.request.Request(
            endpoint.base + "/json/version",
            headers={"Accept": "application/json", "User-Agent": "xrepost-cdp-check/1"},
        )
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200:
                result["problems"].append(f"/json/version respondió {response.status}")
                return result
            raw = response.read(MAX_PROBE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        result["problems"].append(f"/json/version rechazó la petición ({exc.code})")
        return result
    except (urllib.error.URLError, OSError, ValueError) as exc:
        result["problems"].append(f"no se pudo conectar con CDP: {exc}")
        return result
    if len(raw) > MAX_PROBE_BYTES:
        result["problems"].append("respuesta de CDP demasiado grande")
        return result
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        result["problems"].append("/json/version no devolvió JSON")
        return result
    if not isinstance(data, dict):
        result["problems"].append("/json/version no devolvió un objeto")
        return result
    browser = str(data.get("Browser") or "")
    websocket = str(data.get("webSocketDebuggerUrl") or "")
    result["browser"] = browser
    result["websocket"] = websocket
    if "chrome" not in browser.lower() and "chromium" not in browser.lower():
        result["problems"].append(f"el navegador no parece Chrome/Chromium: {browser!r}")
    if not browser:
        result["problems"].append("la respuesta no identifica el navegador")
    if websocket:
        ws = urlparse(websocket)
        if ws.scheme not in ("ws", "wss") or (ws.hostname or "").lower() not in LOOPBACK_HOSTS:
            result["problems"].append("webSocketDebuggerUrl no apunta a loopback")
        if ws.port and ws.port != endpoint.port:
            result["problems"].append("webSocketDebuggerUrl usa otro puerto")
    else:
        result["problems"].append("la respuesta no incluye webSocketDebuggerUrl")
    result["ok"] = not result["problems"]
    return result


def _listening_addresses(
    port: int, *, files: tuple[str, ...] = ("/proc/net/tcp", "/proc/net/tcp6")
) -> list[str]:
    """Direcciones locales en escucha para el puerto (de /proc/net/tcp*)."""
    found: list[str] = []
    for name in files:
        try:
            with open(name, encoding="ascii", errors="replace") as fh:
                next(fh, None)
                for line in fh:
                    fields = line.split()
                    if len(fields) < 4 or fields[3] != "0A":  # 0A = LISTEN
                        continue
                    local, _, port_hex = fields[1].partition(":")
                    if int(port_hex, 16) != port:
                        continue
                    if name.endswith("tcp6"):
                        chunks = [local[i : i + 8] for i in range(0, len(local), 8)]
                        addr = ":".join(
                            reversed(
                                [
                                    ".".join(str(int(chunk[i : i + 2], 16)) for i in (6, 4, 2, 0))
                                    for chunk in chunks
                                ]
                            )
                        )
                        found.append(addr)
                    else:
                        addr = ".".join(str(int(local[i : i + 2], 16)) for i in (6, 4, 2, 0))
                        found.append(addr)
        except OSError:
            continue
    return sorted(set(found))


def chrome_processes(
    port: int, profile: Path | None = None, *, proc_root: Path | None = None
) -> list[dict]:
    """Procesos Chrome que usan el puerto CDP (y, si se indica, el perfil)."""
    wanted_profile = profile.resolve() if profile else None
    out: list[dict] = []
    proc = proc_root or Path("/proc")
    if not proc.exists():
        return out
    try:
        entries = list(proc.iterdir())
    except OSError:
        return out
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        if not raw:
            continue
        args = [part.decode("utf-8", "replace") for part in raw.split(b"\0") if part]
        port_flag = f"--remote-debugging-port={port}"
        if port_flag not in args:
            continue
        exe = Path(args[0]).name.lower()
        if "chrome" not in exe and "chromium" not in exe:
            continue
        profile_arg = ""
        for arg in args:
            if arg.startswith("--user-data-dir="):
                profile_arg = arg.split("=", 1)[1]
                break
        profile_path = Path(profile_arg).expanduser().resolve() if profile_arg else None
        out.append(
            {
                "pid": int(entry.name),
                "exe": args[0],
                "profile": str(profile_path) if profile_path else "",
                "profile_ok": bool(
                    profile_path and (wanted_profile is None or profile_path == wanted_profile)
                ),
            }
        )
    return out


def _profile_is_personal(profile: Path) -> bool:
    value = str(profile.expanduser().resolve())
    for raw in FORBIDDEN_PROFILES:
        try:
            if Path(raw).expanduser().resolve() == Path(value):
                return True
        except OSError:
            continue
    return False


def status(
    url: str | None = None,
    *,
    profile: str | Path | None = None,
    timeout: float = 1.5,
) -> dict:
    """Informe completo; ``secure`` es la única señal que deben mirar los flujos."""
    profile_path = Path(profile).expanduser().resolve() if profile else default_profile()
    problems: list[str] = []
    try:
        endpoint = parse_endpoint(url)
    except CdpSecurityError as exc:
        return {
            "url": url or os.environ.get("BU_CDP_URL", DEFAULT_CDP),
            "secure": False,
            "reachable": False,
            "problems": [str(exc)],
        }
    problems.extend(endpoint.problems)

    listening = _listening_addresses(endpoint.port) if endpoint.port else []
    for addr in listening:
        if not _is_loopback_ip(addr):
            problems.append(f"el puerto CDP escucha en {addr}, que no es loopback")

    processes = chrome_processes(endpoint.port, profile_path) if endpoint.port else []
    if len(processes) > 1:
        problems.append(f"hay {len(processes)} procesos Chrome con el mismo puerto CDP")
    if not processes:
        problems.append("no se encontró el proceso Chrome del perfil de xrepost")
    for item in processes:
        if item["profile"] and not item["profile_ok"]:
            problems.append(
                "el proceso Chrome usa otro perfil: " + (item["profile"] or "(sin perfil)")
            )
        if not item["profile"]:
            problems.append("el proceso Chrome no declara --user-data-dir")
    if _profile_is_personal(profile_path):
        problems.append("el perfil configurado es el perfil personal de Chrome; usa uno dedicado")

    info = probe(endpoint, timeout=timeout) if endpoint.port else {
        "ok": False,
        "browser": "",
        "websocket": "",
        "problems": ["sin puerto"],
    }
    problems.extend(info["problems"])
    return {
        "url": endpoint.url,
        "endpoint": endpoint.base,
        "host": endpoint.host,
        "port": endpoint.port,
        "profile": str(profile_path),
        "listening": listening,
        "processes": processes,
        "browser": info["browser"],
        "websocket": info["websocket"],
        "reachable": bool(info.get("ok")),
        "secure": not problems,
        "problems": problems,
    }


def require_ready(url: str | None = None, *, profile: str | Path | None = None) -> dict:
    """Lanza ``CdpSecurityError`` si el endpoint no es seguro para operar."""
    report = status(url, profile=profile)
    if not report["secure"]:
        detail = "; ".join(report["problems"]) or "comprobación CDP fallida"
        raise CdpSecurityError(f"CDP no seguro: {detail}")
    return report


def quick_available(url: str | None = None, timeout: float = 0.8) -> bool:
    """¿Hay un CDP de Chrome en loopback? (sin exigir proceso/perfil)."""
    try:
        endpoint = parse_endpoint(url)
    except CdpSecurityError:
        return False
    if endpoint.problems:
        return False
    return bool(probe(endpoint, timeout=timeout).get("ok"))


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Comprobación de seguridad de CDP para xrepost")
    parser.add_argument("--url", default=None, help="Endpoint CDP (por defecto BU_CDP_URL)")
    parser.add_argument("--profile", default=None, help="Perfil de Chrome esperado")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    args = parser.parse_args(argv)
    report = status(args.url, profile=args.profile)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"CDP:      {report['url']}")
        print(f"Perfil:   {report.get('profile', '')}")
        print(f"Seguro:   {'sí' if report['secure'] else 'NO'}")
        print(f"Alcanzable: {'sí' if report['reachable'] else 'no'}")
        for problem in report["problems"]:
            print(f"  · {problem}")
    return 0 if report["secure"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
