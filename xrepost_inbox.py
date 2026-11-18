#!/usr/bin/env python3
"""Bandeja de revisión persistente.

Flujo: búsqueda → resultados → revisión → aprobación → ejecución → verificación.

La selección se guarda por identificador estable de publicación (el ID numérico
del estado de X), no por posición en la tabla. Rechazar o aprobar no borra el
elemento: se conserva con su decisión y su historial para poder auditar qué se
descartó y por qué.
"""

from __future__ import annotations

import datetime as dt
import secrets
from pathlib import Path

import xrepost_history
import xrepost_store

PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
QUEUED = "queued"
EXECUTED = "executed"
VERIFIED = "verified"
UNCONFIRMED = "unconfirmed"
FAILED = "failed"
STATUSES = (PENDING, APPROVED, REJECTED, QUEUED, EXECUTED, VERIFIED, UNCONFIRMED, FAILED)
MAX_ITEMS = 5000


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


class InboxStore:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self.store = xrepost_store.JsonStore(
            self.path, lambda: {"version": 1, "items": []}, max_bytes=8 * 1024 * 1024
        )

    def list(self, *, status: str = "", limit: int = 200, query: str = "") -> list[dict]:
        data = self.store.read()
        items = [item for item in data.get("items", []) if isinstance(item, dict) and item.get("id")]
        if status:
            items = [item for item in items if item.get("status") == status]
        needle = query.strip().lower()
        if needle:
            items = [
                item
                for item in items
                if any(needle in str(item.get(field, "")).lower() for field in ("text", "handle", "author", "url"))
            ]
        items.sort(key=lambda item: str(item.get("added") or ""), reverse=True)
        return items[: max(1, min(limit, 1000))]

    def get(self, item_id: str) -> dict | None:
        return next((item for item in self.list(limit=MAX_ITEMS) if item.get("id") == item_id), None)

    def upsert_from_posts(self, posts: list[dict], params: dict, run: str = "") -> dict:
        """Añade/actualiza resultados de una búsqueda sin pisar decisiones humanas."""
        added = 0
        updated = 0

        def mutate(data: dict) -> dict:
            nonlocal added, updated
            items = [item for item in data.get("items", []) if isinstance(item, dict)]
            by_id = {str(item.get("id")): item for item in items}
            for post in posts:
                url = str(post.get("url") or "")
                item_id = xrepost_history.tweet_id(url)
                if not item_id or not item_id.isdigit():
                    continue
                existing = by_id.get(item_id)
                if existing:
                    existing.update(
                        {
                            "url": url or existing.get("url", ""),
                            "handle": str(post.get("usuario") or existing.get("handle", "")).lstrip("@"),
                            "author": str(post.get("autor") or existing.get("author", "")),
                            "text": str(post.get("texto") or existing.get("text", ""))[:1000],
                            "date": str(post.get("fecha") or existing.get("date", ""))[:40],
                            "last_seen": now(),
                        }
                    )
                    updated += 1
                else:
                    if len(items) >= MAX_ITEMS:
                        continue
                    item = {
                        "id": item_id,
                        "url": url,
                        "handle": str(post.get("usuario") or "").lstrip("@"),
                        "author": str(post.get("autor") or ""),
                        "text": str(post.get("texto") or "")[:1000],
                        "date": str(post.get("fecha") or "")[:40],
                        "status": PENDING,
                        "added": now(),
                        "last_seen": now(),
                        "run": run,
                        "search": {
                            "users": str(params.get("users") or "")[:300],
                            "from": str(params.get("from") or "")[:10],
                            "to": str(params.get("to") or "")[:10],
                            "quote": str(params.get("quote") or "")[:280],
                        },
                        "detail": "",
                    }
                    items.append(item)
                    by_id[item_id] = item
                    added += 1
            data["items"] = items
            return data

        self.store.mutate(mutate)
        return {"added": added, "updated": updated}

    def decide(self, ids: list[str], status: str) -> dict:
        if status not in (PENDING, APPROVED, REJECTED):
            raise ValueError(f"Decisión no válida: {status}")
        wanted = {str(item) for item in ids}
        changed = 0

        def mutate(data: dict) -> dict:
            nonlocal changed
            for item in data.get("items", []):
                if isinstance(item, dict) and str(item.get("id")) in wanted:
                    if item.get("status") in (QUEUED, EXECUTED, VERIFIED, UNCONFIRMED):
                        continue
                    item["status"] = status
                    item["decided"] = now()
                    changed += 1
            return data

        self.store.mutate(mutate)
        return {"changed": changed}

    def mark(self, ids: list[str], status: str, detail: str = "") -> int:
        if status not in STATUSES:
            raise ValueError(f"Estado de bandeja no válido: {status}")
        wanted = {str(item) for item in ids}
        changed = 0

        def mutate(data: dict) -> dict:
            nonlocal changed
            for item in data.get("items", []):
                if isinstance(item, dict) and str(item.get("id")) in wanted:
                    item["status"] = status
                    item["detail"] = str(detail)[:500]
                    item["updated"] = now()
                    changed += 1
            return data

        self.store.mutate(mutate)
        return changed

    def approved_urls(self, ids: list[str] | None = None) -> list[str]:
        items = self.list(status=APPROVED, limit=MAX_ITEMS)
        if ids is not None:
            wanted = {str(item) for item in ids}
            items = [item for item in items if str(item.get("id")) in wanted]
        return [str(item.get("url")) for item in items if item.get("url")]

    def counts(self) -> dict[str, int]:
        result = {status: 0 for status in STATUSES}
        for item in self.list(limit=MAX_ITEMS):
            status = str(item.get("status") or PENDING)
            result[status] = result.get(status, 0) + 1
        return result

    def import_items(self, items: list[dict]) -> int:
        """Importación desde una exportación JSON (conserva decisiones)."""
        count = 0

        def mutate(data: dict) -> dict:
            nonlocal count
            existing = {
                str(item.get("id")): item
                for item in data.get("items", [])
                if isinstance(item, dict)
            }
            for item in items:
                if not isinstance(item, dict) or not str(item.get("id") or "").isdigit():
                    continue
                base = existing.get(str(item["id"])) or {}
                merged = {**base, **item, "id": str(item["id"])}
                if merged.get("status") not in STATUSES:
                    merged["status"] = PENDING
                existing[str(item["id"])] = merged
                count += 1
            data["items"] = list(existing.values())
            return data

        self.store.mutate(mutate)
        return count


def default_inbox_path(history: str | Path) -> Path:
    return Path(history).expanduser().parent / "inbox.json"
