#!/usr/bin/env python3
"""Configuración de red (proxy) compartida por el panel y el lanzador de Chrome.

La preferencia se guarda en ``~/.local/state/xrepost/network.json`` y se
traduce a flags de Chrome. Cambiar el proxy requiere RELANZAR Chrome: CDP no
permite modificarlo en caliente de forma fiable. Por eso este módulo solo
calcula los flags; el reinicio lo hace ``xrepost-chrome.sh``.

Modos:
  direct  → --no-proxy-server
  pac     → --proxy-pac-url=file:///.../proxy_empresa.pac
  auto    → --proxy-pac-url=file:///.../proxy_auto.pac  (decide con dnsResolve)
  server  → --proxy-server=<scheme>://<host:port> [--proxy-bypass-list=...]

Uso desde línea de comandos (lo usan los scripts shell):
  python3 xrepost_network.py get
  python3 xrepost_network.py flags
  python3 xrepost_network.py set direct
  python3 xrepost_network.py set server --proxy proxy.ejemplo.cu:8080 --scheme http
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODES = ("direct", "pac", "auto", "server")
DEFAULT_PAC = ROOT / "proxy_empresa.pac"
AUTO_PAC = ROOT / "proxy_auto.pac"
DEFAULT_BYPASS = "localhost,127.0.0.1,.etecsa.cu,.etecsa.net,.fdc.com,pamarillas.cu"

# ``proxy`` se guarda como host:puerto, sin esquema ni credenciales. Se admiten
# nombres DNS, IPv4 e IPv6 entre corchetes. El puerto se valida aparte.
PROXY_RE = re.compile(
    r"^(?:[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?|\[[0-9A-Fa-f:.]+\]):(\d{1,5})$"
)
BYPASS_ITEM_RE = re.compile(r"^[A-Za-z0-9*._:\[\]/-]+$")


def validate_proxy(value: object) -> str:
    """Valida ``host:puerto`` y rechaza esquemas, credenciales y controles."""
    text = str(value or "").strip()
    if not text or any(ch in text for ch in "\r\n\t\x00 "):
        raise ValueError("el proxy debe tener el formato host:puerto")
    match = PROXY_RE.fullmatch(text)
    if not match:
        raise ValueError(
            "el proxy debe tener el formato host:puerto (sin esquema ni credenciales)"
        )
    port = int(match.group(1))
    if not 1 <= port <= 65535:
        raise ValueError("el puerto del proxy debe estar entre 1 y 65535")
    return text


def validate_bypass(value: object) -> str:
    """Valida la lista de bypass: elementos separados por coma, sin flags."""
    text = str(value or "").strip()
    if not text:
        return ""
    items = [item.strip() for item in text.split(",")]
    for item in items:
        if not item or item.startswith("-") or not BYPASS_ITEM_RE.fullmatch(item):
            raise ValueError(f"elemento de bypass no válido: {item!r}")
    return ",".join(items)


def validate_pac(value: object) -> str:
    """Exige una ruta absoluta, existente y con extensión .pac."""
    pac = Path(str(value or "").strip()).expanduser()
    if not pac.is_absolute():
        raise ValueError("la ruta del PAC debe ser absoluta")
    if pac.suffix.lower() != ".pac":
        raise ValueError("el PAC debe tener extensión .pac")
    if not pac.is_file():
        raise ValueError(f"no existe el archivo PAC: {pac}")
    return str(pac.resolve())


def config_path() -> Path:
    """Ruta del fichero de preferencias ( ``XREPOST_NETWORK_CONFIG`` la override)."""
    custom = os.environ.get("XREPOST_NETWORK_CONFIG", "")
    return Path(custom).expanduser() if custom else (
        Path.home() / ".local" / "state" / "xrepost" / "network.json"
    )


def default_config() -> dict:
    return {
        "mode": "direct",
        "proxy": "",
        "proxy_scheme": "http",
        "pac_path": str(DEFAULT_PAC),
        "bypass": DEFAULT_BYPASS,
    }


def load_config() -> dict:
    """Lee la preferencia tolerando JSON roto; siempre devuelve una config válida."""
    cfg = default_config()
    try:
        raw = json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return cfg
    if not isinstance(raw, dict):
        return cfg
    for key in cfg:
        if key in raw:
            cfg[key] = raw[key]
    if cfg["mode"] not in MODES:
        cfg["mode"] = "direct"
    return cfg


def save_config(data: dict) -> dict:
    """Valida y guarda la preferencia de forma atómica. Devuelve la config final."""
    cfg = default_config()
    for key in cfg:
        if key in data:
            cfg[key] = data[key]
    if cfg["mode"] not in MODES:
        raise ValueError(f"modo no válido: {cfg['mode']!r} ( usa {', '.join(MODES)} )")
    cfg["proxy_scheme"] = str(cfg["proxy_scheme"]).lower()
    if cfg["proxy_scheme"] not in ("http", "https"):
        raise ValueError("proxy_scheme debe ser 'http' o 'https'")
    for key in ("proxy", "pac_path", "bypass"):
        cfg[key] = str(cfg[key]).strip()
    if cfg["mode"] == "server":
        if not cfg["proxy"]:
            raise ValueError("el modo 'server' necesita un proxy (host:puerto)")
        cfg["proxy"] = validate_proxy(cfg["proxy"])
        cfg["bypass"] = validate_bypass(cfg["bypass"])
    if cfg["mode"] == "pac":
        if not cfg["pac_path"]:
            raise ValueError("el modo 'pac' necesita la ruta al fichero .pac")
        cfg["pac_path"] = validate_pac(cfg["pac_path"])

    dest = config_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(dest.parent), prefix=".network-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp, dest)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return cfg


def chrome_flags(cfg: dict | None = None) -> list[str]:
    """Traduce la preferencia a flags de Chrome (sin espacios en los valores)."""
    cfg = cfg or load_config()
    mode = cfg.get("mode", "direct")
    if mode == "direct":
        return ["--no-proxy-server"]
    if mode in ("pac", "auto"):
        pac = cfg.get("pac_path") or str(DEFAULT_PAC)
        if mode == "auto":
            pac = str(AUTO_PAC)
        return [f"--proxy-pac-url={Path(pac).expanduser().resolve().as_uri()}"]
    if mode == "server":
        scheme = str(cfg.get("proxy_scheme", "http")).lower()
        if scheme not in ("http", "https"):
            raise ValueError("proxy_scheme debe ser 'http' o 'https'")
        proxy = validate_proxy(cfg.get("proxy", ""))
        flags = [f"--proxy-server={scheme}://{proxy}"]
        bypass = validate_bypass(cfg.get("bypass", ""))
        if bypass:
            flags.append(f"--proxy-bypass-list={bypass}")
        return flags
    raise ValueError(f"modo no válido: {mode!r}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Preferencia de red de xrepost")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("get", help="muestra la configuración en JSON")
    sub.add_parser("flags", help="imprime los flags de Chrome, uno por línea")
    pset = sub.add_parser("set", help="cambia la preferencia")
    pset.add_argument("mode", choices=MODES)
    pset.add_argument("--proxy", default="", help="host:puerto para modo server")
    pset.add_argument("--scheme", default="http", choices=("http", "https"))
    pset.add_argument("--pac", default="", help="ruta .pac para modo pac")
    args = ap.parse_args(argv)

    if args.cmd == "get":
        print(json.dumps(load_config(), ensure_ascii=False))
    elif args.cmd == "flags":
        for flag in chrome_flags():
            print(flag)
    else:
        data = {"mode": args.mode}
        if args.proxy:
            data["proxy"] = args.proxy
        if args.scheme:
            data["proxy_scheme"] = args.scheme
        if args.pac:
            data["pac_path"] = args.pac
        save_config(data)
        print(json.dumps(load_config(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
