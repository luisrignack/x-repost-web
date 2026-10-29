#!/usr/bin/env python3
"""Hashtags usados antes en xrepost: almacenamiento, ranking y sugerencias.

El archivo por defecto es ``hashtags.json`` junto al historial
(``~/.local/state/xrepost/hashtags.json``). Se comparte entre el CLI y el panel
web. ``X_HASHTAGS`` permite usar otra ruta.

Uso como helper del CLI:

  python3 xrepost_hashtags.py add "#ETECSA #Cuba"
  python3 xrepost_hashtags.py list [texto]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

MAX_STORED = 200
DEFAULT_LIMIT = 8
VERSION = 1
MAX_TAG = 50
MAX_TEXT = 280

# Un hashtag: sin espacios, sin '#' inicial, sin comas. Se admite unicode
# (X permite acentos, ñ, etc.).
TAG_RE = re.compile(r"^[^\s#,]{1,%d}$" % MAX_TAG)
SEPARATORS_RE = re.compile(r"[\s,]+")


def default_history() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return Path(os.environ.get("X_HISTORY") or (base / "xrepost" / "history.jsonl")).expanduser()


def resolve_path(
    hashtags: str | Path | None = None,
    history: str | Path | None = None,
) -> Path:
    """Devuelve la ruta de hashtags.json respetando X_HASHTAGS/X_HISTORY."""
    hist = Path(history).expanduser() if history else default_history()
    env = os.environ.get("X_HASHTAGS")
    if hashtags:
        return Path(hashtags).expanduser()
    if env:
        return Path(env).expanduser()
    return hist.parent / "hashtags.json"


def normalize_tag(value: object) -> str:
    """'#Etecsa' -> 'Etecsa' (sin '#' ni espacios)."""
    return str(value or "").strip().lstrip("#").strip()


def _valid_tag(tag: str) -> bool:
    return bool(TAG_RE.fullmatch(tag)) and any(ch.isalnum() for ch in tag)


def split_tags(values: str | list[str] | tuple[str, ...]) -> list[str]:
    """Separa por espacios o comas y devuelve tags válidos, sin duplicados."""
    if isinstance(values, str):
        raw = SEPARATORS_RE.split(values.strip())
    else:
        raw = [str(item) for item in values]

    out: list[str] = []
    seen: set[str] = set()
    for value in raw:
        tag = normalize_tag(value)
        if not _valid_tag(tag):
            continue
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(tag)
    return out


def clean_text(value: object) -> str:
    """Texto del comentario: cada palabra se convierte en hashtag.

    "ETECSA, cuba" -> "#ETECSA #cuba". Devuelve "" si no hay nada válido.
    """
    tags = split_tags(str(value or ""))
    return " ".join("#" + tag for tag in tags)


def _parse_ts(value: object) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _read_file(path: Path) -> dict[str, dict]:
    entries: dict[str, dict] = {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return entries

    items = data.get("hashtags") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return entries

    for item in items:
        if isinstance(item, str):
            tag, count, last = item, 1, ""
        elif isinstance(item, dict):
            tag = item.get("tag")
            try:
                count = max(0, int(item.get("count") or 1))
            except (TypeError, ValueError):
                count = 1
            last = str(item.get("last_used") or "")
        else:
            continue
        tag = normalize_tag(tag)
        if not _valid_tag(tag):
            continue
        key = tag.lower()
        current = entries.get(key)
        if current is None:
            entries[key] = {"tag": tag, "count": count, "last_used": last}
        else:
            current["count"] = max(current["count"], count)
            if _parse_ts(last) > _parse_ts(current["last_used"]):
                current["last_used"] = last
                current["tag"] = tag
    return entries


def load_hashtags(hashtags: str | Path | None = None, history: str | Path | None = None) -> dict[str, dict]:
    return _read_file(resolve_path(hashtags, history))


def _write_file(path: Path, entries: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(
        entries.values(),
        key=lambda e: (_parse_ts(e.get("last_used")), int(e.get("count") or 0)),
        reverse=True,
    )[:MAX_STORED]
    payload = {
        "version": VERSION,
        "hashtags": [
            {
                "tag": item["tag"],
                "count": int(item.get("count") or 1),
                "last_used": item.get("last_used") or "",
            }
            for item in ordered
        ],
    }
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def add_hashtags(
    values: str | list[str] | tuple[str, ...],
    hashtags: str | Path | None = None,
) -> bool:
    """Suma uno o varios hashtags al archivo. Devuelve False si no se pudo."""
    tags = split_tags(values)
    if not tags:
        return False
    path = resolve_path(hashtags, None)
    lock_path = path.with_name(path.name + ".lock")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        lock = open(lock_path, "a+", encoding="utf-8")
    except OSError:
        return False

    try:
        try:
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass

        entries = _read_file(path)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for tag in tags:
            key = tag.lower()
            current = entries.get(key)
            if current is None:
                entries[key] = {"tag": tag, "count": 1, "last_used": now}
            else:
                current["tag"] = tag
                current["count"] = int(current.get("count") or 1) + 1
                current["last_used"] = now
        _write_file(path, entries)
        return True
    except OSError:
        return False
    finally:
        try:
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        except (ImportError, OSError):
            pass
        lock.close()


def rank_hashtags(
    query: str,
    entries: dict[str, dict],
    limit: int = DEFAULT_LIMIT,
    exclude: set[str] | list[str] | tuple[str, ...] = (),
) -> list[dict]:
    q = normalize_tag(query).lower()
    blocked = {normalize_tag(item).lower() for item in exclude}
    ranked: list[tuple] = []

    for entry in entries.values():
        tag = str(entry.get("tag") or "")
        low = tag.lower()
        if not low or low in blocked:
            continue
        if q:
            if low == q:
                kind = 3
            elif low.startswith(q):
                kind = 2
            elif q in low:
                kind = 1
            else:
                continue
        else:
            kind = 0
        ranked.append(
            (
                kind,
                _parse_ts(entry.get("last_used")),
                int(entry.get("count") or 0),
                -len(tag),
                tag,
                entry,
            )
        )

    ranked.sort(key=lambda item: item[4].lower())
    ranked.sort(key=lambda item: item[:4], reverse=True)
    out = []
    for *_, tag, entry in ranked[: max(0, limit)]:
        out.append(
            {
                "tag": tag,
                "count": int(entry.get("count") or 0),
                "last_used": entry.get("last_used") or "",
            }
        )
    return out


def suggest(
    query: str = "",
    hashtags: str | Path | None = None,
    history: str | Path | None = None,
    limit: int = DEFAULT_LIMIT,
    exclude: set[str] | list[str] | tuple[str, ...] = (),
) -> list[dict]:
    entries = load_hashtags(hashtags, history)
    return rank_hashtags(query, entries, limit=limit, exclude=exclude)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hashtags recordados por xrepost.")
    parser.add_argument("--hashtags", default="", help="ruta de hashtags.json")
    sub = parser.add_subparsers(dest="command")

    add = sub.add_parser("add", help="recordar uno o varios hashtags")
    add.add_argument("values", nargs="+")

    lst = sub.add_parser("list", help="listar coincidencias")
    lst.add_argument("query", nargs="?", default="")
    lst.add_argument("--limit", type=int, default=DEFAULT_LIMIT)

    clean = sub.add_parser("clean", help="normalizar un comentario a hashtags")
    clean.add_argument("values", nargs="+")

    args = parser.parse_args(argv)
    path = Path(args.hashtags).expanduser() if args.hashtags else None

    if args.command == "add":
        ok = add_hashtags(" ".join(args.values), path)
        return 0 if ok else 1
    if args.command == "list":
        for item in suggest(args.query, hashtags=path, limit=args.limit):
            print("#" + item["tag"], item["count"], item["last_used"])
        return 0
    if args.command == "clean":
        print(clean_text(" ".join(args.values)))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
