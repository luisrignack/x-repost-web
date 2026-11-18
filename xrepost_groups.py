#!/usr/bin/env python3
"""Cuentas: grupos, alias, favoritos, importación/exportación y estadísticas.

El archivo de cuentas existente (``accounts.json``) se mantiene intacto. Los
metadatos nuevos viven aparte (``groups.json`` y ``accounts_meta.json``) para
que una versión anterior de xrepost siga pudiendo leer y escribir las cuentas
sin perder datos.

La "validación" de cuentas es sintáctica (formato de handle de X). No se hace
ninguna petición a X: verificar que una cuenta existe requiere la sesión
autenticada y se documenta como limitación.
"""

from __future__ import annotations

import csv
import io
import re
import secrets
from pathlib import Path

import xrepost_history
import xrepost_store

HANDLE_RE = re.compile(r"^[A-Za-z0-9_]{1,15}$")
MAX_MEMBERS = 500
MAX_GROUPS = 100
MAX_IMPORT = 2000


def normalize(value: object) -> str:
    return str(value or "").strip().lstrip("@").strip()


def valid(value: object) -> bool:
    return bool(HANDLE_RE.fullmatch(normalize(value)))


class GroupStore:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self.store = xrepost_store.JsonStore(
            self.path, lambda: {"version": 1, "groups": []}
        )

    def list(self) -> list[dict]:
        data = self.store.read()
        items = [item for item in data.get("groups", []) if isinstance(item, dict) and item.get("id")]
        return items

    def get(self, group_id: str) -> dict | None:
        return next((item for item in self.list() if item.get("id") == group_id), None)

    def create(self, name: str, description: str = "", members: list[str] | None = None) -> dict:
        label = str(name or "").strip()[:60]
        if not label:
            raise ValueError("El grupo necesita un nombre")
        group = {
            "id": secrets.token_hex(6),
            "name": label,
            "description": str(description or "").strip()[:200],
            "created": _now(),
            "members": self._clean_members(members or []),
        }

        def mutate(data: dict) -> dict:
            items = [item for item in data.get("groups", []) if isinstance(item, dict)]
            if any(str(item.get("name", "")).lower() == label.lower() for item in items):
                raise ValueError(f"Ya existe un grupo llamado «{label}»")
            if len(items) >= MAX_GROUPS:
                raise ValueError(f"Como máximo {MAX_GROUPS} grupos")
            items.append(group)
            data["groups"] = items
            return data

        self.store.mutate(mutate)
        return group

    def update(
        self,
        group_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        members: list[str] | None = None,
    ) -> dict:
        updated: dict = {}

        def mutate(data: dict) -> dict:
            groups = [item for item in data.get("groups", []) if isinstance(item, dict)]
            for item in groups:
                if item.get("id") != group_id:
                    continue
                if name is not None:
                    label = str(name).strip()[:60]
                    if not label:
                        raise ValueError("El grupo necesita un nombre")
                    if any(
                        other is not item and str(other.get("name", "")).lower() == label.lower()
                        for other in groups
                    ):
                        raise ValueError(f"Ya existe un grupo llamado «{label}»")
                    item["name"] = label
                if description is not None:
                    item["description"] = str(description).strip()[:200]
                if members is not None:
                    item["members"] = self._clean_members(members)
                item["updated"] = _now()
                updated.update(item)
                break
            data["groups"] = groups
            return data

        self.store.mutate(mutate)
        if not updated:
            raise KeyError(group_id)
        return updated

    def delete(self, group_id: str) -> bool:
        removed = {"value": False}

        def mutate(data: dict) -> dict:
            groups = [item for item in data.get("groups", []) if isinstance(item, dict)]
            kept = [item for item in groups if item.get("id") != group_id]
            removed["value"] = len(kept) != len(groups)
            data["groups"] = kept
            return data

        self.store.mutate(mutate)
        return removed["value"]

    def add_members(self, group_id: str, handles: list[str]) -> dict:
        group = self.get(group_id)
        if not group:
            raise KeyError(group_id)
        current = [member["handle"] for member in group.get("members", [])]
        merged = current + [normalize(handle) for handle in handles]
        return self.update(group_id, members=merged)

    def remove_members(self, group_id: str, handles: list[str]) -> dict:
        group = self.get(group_id)
        if not group:
            raise KeyError(group_id)
        drop = {normalize(handle).lower() for handle in handles}
        kept = [member for member in group.get("members", []) if member["handle"].lower() not in drop]
        return self.update(group_id, members=[member["handle"] for member in kept])

    def _clean_members(self, values: list[str] | list[dict]) -> list[dict]:
        out: list[dict] = []
        seen: set[str] = set()
        for item in values:
            alias = ""
            if isinstance(item, dict):
                handle = normalize(item.get("handle") or item.get("usuario") or "")
                alias = str(item.get("alias") or "").strip()[:60]
            else:
                handle = normalize(item)
            if not valid(handle):
                continue
            key = handle.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({"handle": handle, "alias": alias})
        if len(out) > MAX_MEMBERS:
            raise ValueError(f"Un grupo no puede tener más de {MAX_MEMBERS} cuentas")
        return out

    # -- importación / exportación --------------------------------------
    def parse_import(self, text: str) -> dict:
        """Acepta CSV/TXT:``handle``, ``@handle, alias`` o ``handle;alias``."""
        added: list[dict] = []
        skipped: list[dict] = []
        seen: set[str] = set()
        for number, line in enumerate(text.splitlines(), 1):
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            if number == 1 and re.match(r"^(handle|cuenta|usuario|account)\b", raw, re.I):
                continue
            parts = re.split(r"[,;\t]", raw)
            handle = normalize(parts[0])
            alias = ""
            if len(parts) > 1:
                alias = parts[1].strip()[:60]
            if not valid(handle):
                skipped.append({"line": number, "value": raw[:120], "reason": "handle no válido"})
                continue
            key = handle.lower()
            if key in seen:
                skipped.append({"line": number, "value": handle, "reason": "duplicado"})
                continue
            seen.add(key)
            added.append({"handle": handle, "alias": alias})
            if len(added) >= MAX_IMPORT:
                break
        return {"accounts": added, "skipped": skipped, "total": len(added) + len(skipped)}

    def import_into(self, group_id: str, text: str, *, replace: bool = False) -> dict:
        parsed = self.parse_import(text)
        if replace:
            self.update(group_id, members=parsed["accounts"])
        else:
            self.add_members(group_id, [item["handle"] for item in parsed["accounts"]])
        return parsed

    def export_csv(self, group_id: str = "") -> str:
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(["grupo", "handle", "alias"])
        groups = [self.get(group_id)] if group_id else self.list()
        for group in groups:
            if not group:
                continue
            for member in group.get("members", []):
                alias = str(member.get("alias") or "")
                # Neutraliza fórmulas al abrir el CSV en una hoja de cálculo.
                if alias.startswith(("=", "+", "-", "@", "\t", "\r")):
                    alias = "'" + alias
                writer.writerow([group["name"], member["handle"], alias])
        return buffer.getvalue()


class AccountMetaStore:
    """Alias y favoritos globales, sin tocar el esquema histórico de cuentas."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self.store = xrepost_store.JsonStore(
            self.path, lambda: {"version": 1, "accounts": {}}
        )

    def all(self) -> dict[str, dict]:
        data = self.store.read()
        items = data.get("accounts")
        if not isinstance(items, dict):
            return {}
        out = {}
        for key, value in items.items():
            if valid(key) and isinstance(value, dict):
                out[normalize(key).lower()] = {
                    "handle": normalize(value.get("handle") or key),
                    "alias": str(value.get("alias") or "")[:60],
                    "favorite": bool(value.get("favorite")),
                }
        return out

    def set(self, handle: str, *, alias: str | None = None, favorite: bool | None = None) -> dict:
        if not valid(handle):
            raise ValueError("Handle no válido")
        key = normalize(handle).lower()

        def mutate(data: dict) -> dict:
            items = data.get("accounts") if isinstance(data.get("accounts"), dict) else {}
            current = items.get(key) if isinstance(items.get(key), dict) else {}
            item = {
                "handle": normalize(handle),
                "alias": str(current.get("alias") or ""),
                "favorite": bool(current.get("favorite")),
            }
            if alias is not None:
                item["alias"] = str(alias).strip()[:60]
            if favorite is not None:
                item["favorite"] = bool(favorite)
            items[key] = item
            data["accounts"] = items
            return data

        self.store.mutate(mutate)
        return self.all()[key]

    def remove(self, handle: str) -> bool:
        key = normalize(handle).lower()
        removed = {"value": False}

        def mutate(data: dict) -> dict:
            items = data.get("accounts") if isinstance(data.get("accounts"), dict) else {}
            if key in items:
                items.pop(key)
                removed["value"] = True
            data["accounts"] = items
            return data

        self.store.mutate(mutate)
        return removed["value"]


def account_stats(history: str | Path) -> list[dict]:
    """Actividad real por cuenta a partir del historial (no de estimaciones)."""
    entries = xrepost_history.read_events(history)
    stats: dict[str, dict] = {}
    for event in entries:
        handle = normalize(event.get("search_user") or event.get("handle") or "")
        if not handle:
            continue
        key = handle.lower()
        item = stats.setdefault(
            key,
            {
                "handle": handle,
                "reposts": 0,
                "quotes": 0,
                "undone": 0,
                "errors": 0,
                "last": "",
            },
        )
        action, result = event.get("action"), event.get("result")
        if action == "repost" and result == "reposted":
            item["reposts"] += 1
        elif action == "repost" and result == "quoted":
            item["quotes"] += 1
        elif action == "undo" and result == "undone":
            item["undone"] += 1
        elif result not in ("reposted", "quoted", "undone", "not_reposted", "already"):
            item["errors"] += 1
        ts = str(event.get("ts") or "")
        if ts > item["last"]:
            item["last"] = ts
    return sorted(
        stats.values(),
        key=lambda item: (item["reposts"] + item["quotes"], item["last"]),
        reverse=True,
    )


def _now() -> str:
    import datetime as dt

    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def default_group_path(accounts: str | Path | None, history: str | Path | None) -> Path:
    import xrepost_accounts

    acc_path, _ = xrepost_accounts.resolve_paths(accounts, history)
    return acc_path.parent / "groups.json"


def default_meta_path(accounts: str | Path | None, history: str | Path | None) -> Path:
    import xrepost_accounts

    acc_path, _ = xrepost_accounts.resolve_paths(accounts, history)
    return acc_path.parent / "accounts_meta.json"
