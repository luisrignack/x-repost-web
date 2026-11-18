#!/usr/bin/env python3
"""Filtros de publicaciones y perfiles reutilizables.

Los filtros se aplican tanto en el panel (para previsualizar) como en el motor
(``xrepost.py``, mediante variables de entorno). Las expresiones regulares se
validan antes de usarse: longitud máxima, ausencia de construcciones con
retroceso catastrófico conocidas y compilación previa. Python no ofrece un
timeout de ``re``, así que la mitigación es estática y conservadora; el texto de
cada publicación está limitado a 5000 caracteres.

Un perfil es un documento JSON con un nombre y un conjunto de filtros. No
contiene credenciales ni rutas absolutas, por lo que se puede exportar e
importar sin filtrar datos del sistema.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import xrepost_store

MAX_PATTERN = 200
MAX_VALUE = 400
MAX_TEXT = 5000
MAX_PROFILES = 100
MEDIA_CHOICES = ("", "yes", "no")
KIND_CHOICES = ("", "original", "reply", "retweet")

# Heurísticas de retroceso catastrófico: grupos cuantificados anidados
# (a+)+, (a*)*, (a|aa)+ y repeticiones muy grandes. No es perfecto, pero
# rechaza los patrones que bloquean el hilo de la interfaz.
_NESTED_QUANT = re.compile(r"\((?:\?:)?[^)]*[+*][^)]*\)\s*[+*]")
_BIG_REPEAT = re.compile(r"\{\s*(\d+)\s*(?:,\s*\d*)?\}")
_ALTERNATION_REPEAT = re.compile(r"\(([^)]*\|[^)]*)\)\s*[+*]")


class FilterError(ValueError):
    pass


def compile_safe(pattern: str, *, field: str = "regex") -> re.Pattern[str] | None:
    text = str(pattern or "").strip()
    if not text:
        return None
    if len(text) > MAX_PATTERN:
        raise FilterError(f"{field}: la expresión regular supera {MAX_PATTERN} caracteres")
    if _NESTED_QUANT.search(text) or _ALTERNATION_REPEAT.search(text):
        raise FilterError(f"{field}: la expresión regular tiene grupos repetidos (riesgo de bloqueo)")
    for match in _BIG_REPEAT.finditer(text):
        if int(match.group(1)) > 100:
            raise FilterError(f"{field}: repetición demasiado grande ({match.group(1)})")
    try:
        return re.compile(text, re.IGNORECASE | re.UNICODE)
    except re.error as exc:
        raise FilterError(f"{field}: expresión regular no válida ({exc})") from exc


def split_terms(value: object) -> list[str]:
    if isinstance(value, (list, tuple)):
        raw = [str(item) for item in value]
    else:
        raw = str(value or "").split(",")
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        term = item.strip().lower()
        if not term or term in seen:
            continue
        seen.add(term)
        out.append(term[:MAX_VALUE])
    return out


def normalize_spec(data: dict | None) -> dict:
    """Valida y normaliza un filtro; lanza ``FilterError`` si no sirve."""
    data = data if isinstance(data, dict) else {}
    spec: dict[str, Any] = {
        "include": split_terms(data.get("include", data.get("match", ""))),
        "exclude": split_terms(data.get("exclude", "")),
        "exact": split_terms(data.get("exact", "")),
        "regex": str(data.get("regex", "") or "").strip(),
        "exclude_regex": str(data.get("exclude_regex", "") or "").strip(),
        "lang": split_terms(data.get("lang", "")),
        "hashtags": split_terms(data.get("hashtags", "")),
        "min_len": _int_range(data.get("min_len"), 0, 10000, "min_len"),
        "max_len": _int_range(data.get("max_len"), 0, 10000, "max_len"),
        "media": _choice(data.get("media"), MEDIA_CHOICES, "media"),
        "video": _choice(data.get("video"), MEDIA_CHOICES, "video"),
        "kind": _choice(data.get("kind"), KIND_CHOICES, "kind"),
    }
    if spec["max_len"] and spec["min_len"] and spec["min_len"] > spec["max_len"]:
        raise FilterError("min_len no puede ser mayor que max_len")
    compile_safe(spec["regex"], field="regex")
    compile_safe(spec["exclude_regex"], field="exclude_regex")
    return spec


def _int_range(value: object, low: int, high: int, field: str) -> int:
    if value in (None, "", 0, "0"):
        return 0
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise FilterError(f"{field} debe ser un número") from None
    if not low <= number <= high:
        raise FilterError(f"{field} debe estar entre {low} y {high}")
    return number


def _choice(value: object, choices: tuple[str, ...], field: str) -> str:
    text = str(value or "").strip().lower()
    if text in ("true", "1", "si", "sí"):
        text = "yes"
    elif text in ("false", "0"):
        text = "no"
    if text not in choices:
        raise FilterError(f"{field} no válido: {text!r} (usa {', '.join(c or '—' for c in choices)})")
    return text


def hashtags_in(text: str) -> set[str]:
    return {tag.lower() for tag in re.findall(r"#([^\s#,]{1,50})", text or "", flags=re.UNICODE)}


def post_matches(post: dict, spec: dict | None) -> bool:
    """Aplica un filtro ya normalizado a una publicación."""
    if not spec:
        return True
    text = str(post.get("text") or post.get("texto") or "")[:MAX_TEXT]
    low = text.lower()
    ctx = str(post.get("ctx") or post.get("context") or "").lower()
    lang = str(post.get("lang") or post.get("language") or "").lower()

    if spec["include"] and not any(term in low for term in spec["include"]):
        return False
    if any(term in low for term in spec["exclude"]):
        return False
    if spec["exact"] and not any(term in low for term in spec["exact"]):
        return False
    if spec["regex"] and not compile_safe(spec["regex"]).search(text):  # type: ignore[union-attr]
        return False
    if spec["exclude_regex"] and compile_safe(spec["exclude_regex"]).search(text):  # type: ignore[union-attr]
        return False
    if spec["lang"] and lang and not any(lang == item or lang.startswith(item + "-") for item in spec["lang"]):
        return False
    if spec["lang"] and not lang:
        return False
    if spec["hashtags"]:
        present = hashtags_in(text)
        if not any(tag.lstrip("#") in present for tag in spec["hashtags"]):
            return False
    if spec["min_len"] and len(text) < spec["min_len"]:
        return False
    if spec["max_len"] and len(text) > spec["max_len"]:
        return False
    if spec["media"]:
        has_media = bool(post.get("media"))
        if (spec["media"] == "yes") != has_media:
            return False
    if spec["video"]:
        has_video = bool(post.get("video"))
        if (spec["video"] == "yes") != has_video:
            return False
    if spec["kind"]:
        is_reply = bool(post.get("reply"))
        is_retweet = bool(post.get("retweet")) or "repost" in ctx or "retweet" in ctx
        if spec["kind"] == "reply" and not is_reply:
            return False
        if spec["kind"] == "original" and (is_reply or is_retweet):
            return False
        if spec["kind"] == "retweet" and not is_retweet:
            return False
    return True


def to_env(spec: dict) -> dict[str, str]:
    """Traduce un filtro al contrato de variables del motor."""
    return {
        "X_MATCH": ",".join(spec["include"]),
        "X_EXCLUDE": ",".join(spec["exclude"]),
        "X_EXACT": ",".join(spec["exact"]),
        "X_INCLUDE_REGEX": spec["regex"],
        "X_EXCLUDE_REGEX": spec["exclude_regex"],
        "X_LANG": ",".join(spec["lang"]),
        "X_HASHTAGS_FILTER": ",".join(spec["hashtags"]),
        "X_MIN_LEN": str(spec["min_len"] or ""),
        "X_MAX_LEN": str(spec["max_len"] or ""),
        "X_MEDIA": spec["media"],
        "X_VIDEO": spec["video"],
        "X_KIND": spec["kind"],
    }


class ProfileStore:
    """Perfiles de filtros reutilizables (crear, duplicar, borrar, importar)."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self.store = xrepost_store.JsonStore(
            self.path, lambda: {"version": 1, "profiles": []}
        )

    def list(self) -> list[dict]:
        data = self.store.read()
        items = data.get("profiles")
        if not isinstance(items, list):
            return []
        out = []
        for item in items:
            if isinstance(item, dict) and item.get("id") and item.get("name"):
                out.append(item)
        return out

    def get(self, profile_id: str) -> dict | None:
        return next((item for item in self.list() if item.get("id") == profile_id), None)

    def save(self, name: str, spec: dict, *, profile_id: str = "") -> dict:
        clean = normalize_spec(spec)
        label = str(name or "").strip()[:80]
        if not label:
            raise FilterError("El perfil necesita un nombre")
        import secrets

        pid = profile_id or secrets.token_hex(6)
        saved: dict = {}

        def mutate(data: dict) -> dict:
            items = [item for item in data.get("profiles", []) if isinstance(item, dict)]
            existing = next((item for item in items if item.get("id") == pid), None)
            payload = {
                "id": pid,
                "name": label,
                "filters": clean,
                "updated": _now(),
            }
            if existing:
                if not existing.get("created"):
                    payload["created"] = _now()
                else:
                    payload["created"] = existing["created"]
                items = [payload if item.get("id") == pid else item for item in items]
            else:
                if len(items) >= MAX_PROFILES:
                    raise FilterError(f"Como máximo {MAX_PROFILES} perfiles")
                payload["created"] = _now()
                items.append(payload)
            data["profiles"] = items
            saved.clear()
            saved.update(payload)
            return data

        self.store.mutate(mutate)
        return saved

    def duplicate(self, profile_id: str, name: str = "") -> dict:
        original = self.get(profile_id)
        if not original:
            raise KeyError(profile_id)
        return self.save(name or f"{original['name']} (copia)", original.get("filters") or {})

    def delete(self, profile_id: str) -> bool:
        removed = {"value": False}

        def mutate(data: dict) -> dict:
            items = [item for item in data.get("profiles", []) if isinstance(item, dict)]
            kept = [item for item in items if item.get("id") != profile_id]
            removed["value"] = len(kept) != len(items)
            data["profiles"] = kept
            return data

        self.store.mutate(mutate)
        return removed["value"]

    def export(self, profile_id: str = "") -> dict:
        if profile_id:
            item = self.get(profile_id)
            if not item:
                raise KeyError(profile_id)
            return {"version": 1, "profiles": [item]}
        return {"version": 1, "profiles": self.list()}

    def import_data(self, data: dict, *, keep_ids: bool = False) -> list[dict]:
        items = data.get("profiles") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise FilterError("El archivo no contiene una lista de perfiles")
        saved = []
        for item in items:
            if not isinstance(item, dict):
                continue
            spec = normalize_spec(item.get("filters") or {})
            saved.append(
                self.save(
                    str(item.get("name") or "Importado"),
                    spec,
                    profile_id=str(item.get("id") or "") if keep_ids else "",
                )
            )
        return saved


def _now() -> str:
    import datetime as dt

    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def load_export_file(path: str | Path) -> dict:
    try:
        data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise FilterError(f"No se pudo leer el archivo de perfiles: {exc}") from exc
    if not isinstance(data, dict):
        raise FilterError("El archivo de perfiles no tiene el formato esperado")
    return data
