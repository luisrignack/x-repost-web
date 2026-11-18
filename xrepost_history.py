#!/usr/bin/env python3
"""Historial JSONL: estado compartido, validación, diagnóstico y backups.

Fuente única de verdad sobre qué posts siguen reposteados y cuáles puede
deshacer la herramienta. El motor (``xrepost.py``) y el panel web importan este
módulo, de modo que ambos calculan el estado igual.

Reglas de persistencia:

* solo se añaden líneas; nunca se reescribe ni se borra un evento histórico;
* la rotación mueve el archivo a ``history-archivo-<fecha>.jsonl`` y el estado
  se reconstruye leyendo también los archivos archivados;
* cada escritura es atómica a nivel de línea (``flock`` + ``O_NOFOLLOW``);
* los backups se verifican con SHA-256 antes de restaurar y la restauración
  conserva una copia del historial anterior.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Iterable, Iterator

import xrepost_fs

ACTIONS = ("repost", "undo")
SUCCESS_RESULTS = ("reposted", "quoted")
UNDO_RESULTS = ("undone", "not_reposted")
UNKNOWN_RESULTS = ("unconfirmed", "quote_unverified")
ARCHIVE_PREFIX = "history-archivo-"
DEFAULT_MAX_BYTES = 32 * 1024 * 1024


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
            # un fallo o un resultado desconocido no cambia lo que sabíamos
        elif action == "undo" and res in UNDO_RESULTS:
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


def normalize_event(event: dict) -> dict:
    out = dict(event)
    if "id" in out:
        out["id"] = str(out["id"])
    if out.get("ts"):
        out["ts"] = iso_timestamp(out["ts"])
    return out


# --- lectura y validación ---------------------------------------------------


def validate_event(event: object) -> list[str]:
    """Devuelve la lista de problemas de un evento (vacía si es válido)."""
    if not isinstance(event, dict):
        return ["no es un objeto JSON"]
    problems: list[str] = []
    if not str(event.get("id") or "").strip():
        problems.append("falta id")
    action = event.get("action")
    if action not in ACTIONS:
        problems.append(f"acción no reconocida: {action!r}")
    if not isinstance(event.get("result"), str) or not str(event.get("result") or "").strip():
        problems.append("falta result")
    ts = str(event.get("ts") or "").strip()
    if not ts:
        problems.append("falta ts")
    elif not re.match(r"^\d{4}-\d{2}-\d{2}", ts):
        problems.append(f"ts no ISO: {ts!r}")
    url = event.get("url")
    if url not in (None, "") and not isinstance(url, str):
        problems.append("url no es texto")
    return problems


def _iter_file(path: Path) -> Iterator[tuple[int, object | None, str]]:
    """Itera (línea, evento, error) de un archivo; tolera líneas corruptas."""
    try:
        with open(path, "rb") as fh:
            for number, raw in enumerate(fh, 1):
                try:
                    line = raw.decode("utf-8")
                except UnicodeDecodeError:
                    yield number, None, "no es UTF-8"
                    continue
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except ValueError:
                    yield number, None, "JSON no válido"
                    continue
                problems = validate_event(event)
                if problems:
                    yield number, None, "; ".join(problems)
                    continue
                yield number, normalize_event(event), ""
    except OSError:
        return


def archive_paths(history: str | Path) -> list[Path]:
    base = Path(history).expanduser()
    if not base.parent.exists():
        return []
    archives = sorted(
        (p for p in base.parent.glob(f"{ARCHIVE_PREFIX}*.jsonl") if p.is_file()),
        key=lambda p: (p.stat().st_mtime, p.name),
    )
    return archives


def history_files(history: str | Path) -> list[Path]:
    """Archivos a leer, del más antiguo al más reciente (principal al final)."""
    base = Path(history).expanduser()
    files = archive_paths(base)
    if base.exists():
        files.append(base)
    return files


def read_events(
    path: str | Path,
    *,
    include_archives: bool = True,
    max_events: int = 0,
) -> list[dict]:
    entries: list[dict] = []
    files = history_files(path) if include_archives else (
        [Path(path).expanduser()] if Path(path).expanduser().exists() else []
    )
    for file in files:
        for _number, event, _error in _iter_file(file):
            if event is not None:
                entries.append(event)
    if max_events > 0:
        return entries[-max_events:]
    return entries


class HistoryScan:
    """Resultado puro de recorrer el historial (sin tocar el archivo)."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self.entries: list[dict] = []
        self.corrupt: list[dict] = []
        self.total_lines = 0
        self.archives: list[str] = []

    def run(self, *, include_archives: bool = True) -> "HistoryScan":
        files = history_files(self.path) if include_archives else (
            [self.path] if self.path.exists() else []
        )
        self.archives = [str(p) for p in archive_paths(self.path)] if include_archives else []
        for file in files:
            for number, event, error in _iter_file(file):
                self.total_lines += 1
                if event is None:
                    self.corrupt.append({"file": str(file), "line": number, "error": error})
                else:
                    self.entries.append(event)
        return self


def diagnose(path: str | Path, *, include_archives: bool = True) -> dict:
    """Informe de integridad del historial para la CLI y el panel."""
    scan = HistoryScan(path).run(include_archives=include_archives)
    entries = scan.entries
    ids = [str(e.get("id")) for e in entries]
    unique = set(ids)
    reposted, ours = history_state(entries)
    results = [str(e.get("result") or "") for e in entries]
    actions = [str(e.get("action") or "") for e in entries]
    runs = [str(e.get("run") or "") for e in entries if e.get("run")]
    last_ts = max((str(e.get("ts") or "") for e in entries), default="")

    warnings: list[str] = []
    if scan.corrupt:
        warnings.append(f"{len(scan.corrupt)} línea(s) corrupta(s) ignorada(s)")
    if len(ids) != len(unique):
        warnings.append("hay eventos repetidos para el mismo post (normal si hubo repost y undo)")
    if any(int(str(e.get("ts") or "0000")[:4] or 0) > dt.datetime.now().year + 1 for e in entries):
        warnings.append("hay eventos con fecha futura")

    return {
        "path": str(scan.path),
        "exists": scan.path.exists(),
        "size_bytes": xrepost_fs.file_size(scan.path),
        "archives": scan.archives,
        "total_lines": scan.total_lines,
        "total_events": len(entries),
        "valid_events": len(entries),
        "corrupt_events": len(scan.corrupt),
        "corrupt": scan.corrupt[:50],
        "unique_posts": len(unique),
        "reposts_confirmed": sum(1 for a, r in zip(actions, results) if a == "repost" and r == "reposted"),
        "quotes": sum(1 for r in results if r == "quoted"),
        "undone": sum(1 for a, r in zip(actions, results) if a == "undo" and r == "undone"),
        "unknown": sum(1 for r in results if r in UNKNOWN_RESULTS),
        "errors": sum(
            1
            for a, r in zip(actions, results)
            if r and r not in SUCCESS_RESULTS and r not in UNDO_RESULTS and r not in UNKNOWN_RESULTS and r != "already"
        ),
        "still_reposted": len(reposted),
        "undoable": len(ours),
        "last_event": last_ts,
        "last_run": runs[-1] if runs else "",
        "integrity": "ok" if not warnings else "revisar",
        "warnings": warnings,
    }


# --- escritura --------------------------------------------------------------


def _rotate_if_needed(path: Path, max_bytes: int) -> Path | None:
    size = xrepost_fs.file_size(path)
    if size <= max_bytes:
        return None
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = path.with_name(f"{ARCHIVE_PREFIX}{stamp}.jsonl")
    suffix = 1
    while dest.exists():
        dest = path.with_name(f"{ARCHIVE_PREFIX}{stamp}-{suffix}.jsonl")
        suffix += 1
    with xrepost_fs.locked(str(path) + ".rotate"):
        if not path.exists() or xrepost_fs.file_size(path) <= max_bytes:
            return None
        os.replace(path, dest)
        xrepost_fs.ensure_private_file(dest)
    return dest


def append_event(
    path: str | Path,
    event: dict,
    *,
    max_bytes: int | None = None,
) -> dict:
    """Valida y añade un evento. Devuelve el evento normalizado escrito.

    Lanza ``ValueError`` si el evento no cumple el esquema: es preferible que el
    motor lo sepa a guardar una línea que luego se ignore silenciosamente.
    """
    if max_bytes is None:
        try:
            max_bytes = int(os.environ.get("XREPOST_HISTORY_MAX_BYTES", DEFAULT_MAX_BYTES))
        except ValueError:
            max_bytes = DEFAULT_MAX_BYTES
    target = Path(path).expanduser()
    normalized = normalize_event(event)
    problems = validate_event(normalized)
    if problems:
        raise ValueError("evento de historial no válido: " + "; ".join(problems))
    xrepost_fs.ensure_dir(target.parent)
    _rotate_if_needed(target, max(0, max_bytes))
    xrepost_fs.append_line(target, json.dumps(normalized, ensure_ascii=False, sort_keys=True))
    return normalized


# --- backups ----------------------------------------------------------------


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def backup_dir(history: str | Path) -> Path:
    return Path(history).expanduser().parent / "backups"


def backup(history: str | Path, *, dest: str | Path | None = None) -> dict:
    """Copia el historial (y sus archivos rotados) en un único JSONL."""
    target = Path(history).expanduser()
    if not target.exists() and not history_files(target):
        raise FileNotFoundError(f"No hay historial que copiar: {target}")
    folder = xrepost_fs.ensure_dir(Path(dest) if dest else backup_dir(target))
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = folder / f"history-{stamp}.jsonl"
    lines: list[str] = []
    for file in history_files(target):
        try:
            with open(file, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if line.strip():
                        lines.append(line.rstrip("\n"))
        except OSError:
            continue
    xrepost_fs.atomic_write(out, "\n".join(lines) + "\n")
    checksum = _sha256(out)
    xrepost_fs.atomic_write(str(out) + ".sha256", checksum + "\n")
    return {
        "path": str(out),
        "bytes": xrepost_fs.file_size(out),
        "events": len(lines),
        "sha256": checksum,
    }


def verify_backup(path: str | Path) -> dict:
    backup_path = Path(path).expanduser()
    if not backup_path.exists():
        raise FileNotFoundError(f"No existe el backup: {backup_path}")
    expected = xrepost_fs.read_text(str(backup_path) + ".sha256", default="")
    actual = _sha256(backup_path)
    checksum_ok = not expected or expected.strip() == actual
    scan = HistoryScan(backup_path).run(include_archives=False)
    return {
        "path": str(backup_path),
        "sha256": actual,
        "checksum_ok": checksum_ok,
        "total_events": len(scan.entries),
        "corrupt_events": len(scan.corrupt),
        "ok": checksum_ok and not scan.corrupt and bool(scan.entries),
    }


def list_backups(history: str | Path) -> list[dict]:
    folder = backup_dir(history)
    if not folder.exists():
        return []
    out = []
    for path in sorted(folder.glob("history-*.jsonl"), reverse=True):
        if not path.is_file():
            continue
        expected = xrepost_fs.read_text(str(path) + ".sha256", default="")
        out.append(
            {
                "path": str(path),
                "name": path.name,
                "bytes": xrepost_fs.file_size(path),
                "sha256": expected.strip() if expected else "",
                "created": dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).isoformat(
                    timespec="seconds"
                ),
            }
        )
    return out


def restore(history: str | Path, backup_path: str | Path, *, force: bool = False) -> dict:
    """Restaura un backup verificado, conservando el historial actual."""
    target = Path(history).expanduser()
    report = verify_backup(backup_path)
    if not report["ok"] and not force:
        raise ValueError(
            "El backup no pasó la verificación (checksum o líneas corruptas); "
            "usa force solo si has revisado el archivo a mano."
        )
    previous = ""
    if target.exists():
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        previous_path = target.with_name(f"history.pre-restore-{stamp}.jsonl")
        xrepost_fs.backup_file(target, previous_path)
        previous = str(previous_path)
    data = Path(backup_path).expanduser().read_bytes()
    xrepost_fs.atomic_write(target, data)
    after = diagnose(target, include_archives=False)
    return {"restored": str(target), "previous": previous, "diagnostic": after}


def stats(entries: Iterable[dict]) -> dict:
    """Estadísticas simples reutilizables (compatibles con el panel)."""
    reposted, ours = history_state(list(entries))
    return {
        "reposted": len(reposted),
        "undoable": len(ours),
    }
