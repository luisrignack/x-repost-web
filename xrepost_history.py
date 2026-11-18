#!/usr/bin/env python3
"""Estado del historial compartido por el motor (xrepost.py) y el panel web.

Fuente única de verdad sobre qué posts siguen reposteados y cuáles puede
deshacer la herramienta: si el motor y el panel calculan esto por separado,
se desincronizan (p. ej. tras un «undo_failed» el repost sigue vigente y el
panel debe seguir ofreciendo deshacerlo).

El motor se ejecuta por stdin en el harness y sin `__file__`: xrepost.sh
exporta X_SELF_DIR y el motor añade esa carpeta a sys.path antes de importar
este archivo (igual que con xrepost_labels.py).
"""

from __future__ import annotations

import datetime as dt
import re


def tweet_id(url_or_id: str) -> str:
    s = (url_or_id or "").strip()
    m = re.search(r"/status/(\d+)", s)
    return m.group(1) if m else s


def history_state(entries: list[dict]) -> tuple[set[str], dict[str, dict]]:
    """Devuelve (reposteados, nuestros).

    reposteados: IDs cuyo último estado conocido es "reposteado".
    nuestros:    id -> evento del último repost hecho por la herramienta
                 que sigue vigente (para poder deshacerlo). Un intento de
                 deshacer fallido no cambia ese estado.
    """
    reposted: set[str] = set()
    ours: dict[str, dict] = {}
    for e in entries:
        action, res = e.get("action"), e.get("result")
        if action == "repost":
            if res == "reposted":
                reposted.add(e["id"])
                ours.pop(e["id"], None)  # que la última acción quede al final
                ours[e["id"]] = e
            elif res == "quoted":
                # Una cita no se deshace con «unretweet», pero sí cuenta como
                # hecha: no se vuelve a citar el mismo post en otra ejecución.
                reposted.add(e["id"])
            elif res == "already":
                reposted.add(e["id"])
                # si ya era nuestro, sigue siéndolo; si no, no lo reclamamos
            # un fallo no cambia lo que sabíamos del estado
        elif action == "undo" and res in ("undone", "not_reposted"):
            reposted.discard(e["id"])
            ours.pop(e["id"], None)
    return reposted, ours


def iso_timestamp(value: object) -> str:
    """Normaliza a ISO (YYYY-MM-DDTHH:MM) lo que venga del DOM o del panel.

    El listado revisado del panel trae fechas DD/MM/AAAA HH:MM; el historial
    guarda siempre ISO para que ordenar y comparar sea fiable.
    """
    s = str(value or "").strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?", s)
    if m:
        y, mo, d, hh, mm = m.groups()
        return f"{y}-{mo}-{d}" + (f"T{hh}:{mm}" if hh else "")
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})(?:[ T](\d{2}):(\d{2}))?", s)
    if m:
        d, mo, y, hh, mm = m.groups()
        return f"{y}-{mo}-{d}" + (f"T{hh}:{mm}" if hh else "")
    return s