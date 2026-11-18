#!/usr/bin/env python3
"""Estadísticas reales calculadas desde el historial, los trabajos y la bandeja.

No hay contadores inventados: un resultado desconocido (``unconfirmed``,
``quote_unverified``) nunca suma como éxito. La tasa de confirmación usa
``confirmados / (confirmados + desconocidos + fallos)`` y se muestra con el
denominador a la vista para que sea interpretable.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter
from pathlib import Path
from typing import Iterable

import xrepost_history

SUCCESS = ("reposted", "quoted")


def _parse_day(value: str) -> str:
    text = str(value or "")
    return text[:10] if len(text) >= 10 else ""


def compute(
    history: str | Path,
    *,
    jobs: Iterable[dict] = (),
    inbox: Iterable[dict] = (),
    schedules: Iterable[dict] = (),
    days: int = 30,
) -> dict:
    entries = xrepost_history.read_events(history)
    jobs = list(jobs)
    inbox = list(inbox)
    schedules = list(schedules)

    confirmed = quotes = undone = failed = unknown = 0
    by_account: dict[str, dict] = {}
    daily: Counter[str] = Counter()
    monthly: Counter[str] = Counter()
    last = ""

    for event in entries:
        action = event.get("action")
        result = str(event.get("result") or "")
        ts = str(event.get("ts") or "")
        if ts > last:
            last = ts
        day = _parse_day(ts)
        if day:
            daily[day] += 1
            monthly[day[:7]] += 1

        handle = str(event.get("search_user") or event.get("handle") or "").lstrip("@")
        account = None
        if handle:
            account = by_account.setdefault(
                handle.lower(),
                {"handle": handle, "reposts": 0, "quotes": 0, "undone": 0, "failed": 0, "unknown": 0, "last": ""},
            )
            if ts > account["last"]:
                account["last"] = ts

        if action == "repost" and result == "reposted":
            confirmed += 1
            if account:
                account["reposts"] += 1
        elif action == "repost" and result == "quoted":
            confirmed += 1
            quotes += 1
            if account:
                account["quotes"] += 1
        elif action == "undo" and result == "undone":
            undone += 1
            if account:
                account["undone"] += 1
        elif result in ("unconfirmed", "quote_unverified"):
            unknown += 1
            if account:
                account["unknown"] += 1
        elif result and result not in ("undone", "not_reposted", "already"):
            failed += 1
            if account:
                account["failed"] += 1

    found = sum(int(job.get("post_count") or 0) for job in jobs if job.get("kind") == "preview")
    discarded = sum(1 for item in inbox if item.get("status") == "rejected")
    approved = sum(1 for item in inbox if item.get("status") == "approved")
    verified = sum(1 for item in inbox if item.get("status") == "verified")
    total_jobs = len(jobs)
    job_states = Counter(str(job.get("state") or "") for job in jobs)

    denominator = confirmed + unknown + failed
    rate = round(100.0 * confirmed / denominator, 1) if denominator else 0.0

    cutoff = dt.date.today() - dt.timedelta(days=max(1, days))
    recent = []
    for offset in range(days - 1, -1, -1):
        day = (cutoff + dt.timedelta(days=offset + 1)).isoformat()
        recent.append({"date": day, "events": daily.get(day, 0)})

    return {
        "found": found,
        "reposts_confirmed": confirmed - quotes,
        "confirmed_total": confirmed,
        "quotes": quotes,
        "undone": undone,
        "failed": failed,
        "unknown": unknown,
        "errors": failed + unknown,
        "discarded": discarded,
        "approved": approved,
        "verified": verified,
        "inbox_pending": sum(1 for item in inbox if item.get("status") == "pending"),
        "confirmation_rate": rate,
        "rate_denominator": denominator,
        "by_account": sorted(
            by_account.values(), key=lambda item: (item["reposts"] + item["quotes"], item["last"]), reverse=True
        ),
        "daily": recent,
        "monthly": [{"month": month, "events": count} for month, count in sorted(monthly.items())[-12:]],
        "last_activity": last,
        "jobs": {
            "total": total_jobs,
            "previews": sum(1 for job in jobs if job.get("kind") == "preview"),
            "applies": sum(1 for job in jobs if job.get("kind") == "apply"),
            "undos": sum(1 for job in jobs if job.get("kind") == "undo"),
            "states": dict(job_states),
        },
        "schedules": {
            "total": len(schedules),
            "enabled": sum(1 for item in schedules if item.get("enabled")),
            "next": min(
                (str(item.get("next_run") or "") for item in schedules if item.get("next_run")),
                default="",
            ),
        },
        "total_events": len(entries),
    }


def account_activity(history: str | Path, handle: str) -> dict:
    """Historial individual de una cuenta (usado por la ficha de cuentas)."""
    wanted = str(handle or "").lstrip("@").lower()
    events = []
    for event in xrepost_history.read_events(history):
        candidate = str(event.get("search_user") or event.get("handle") or "").lstrip("@").lower()
        if candidate == wanted:
            events.append(event)
    return {
        "handle": handle,
        "events": events[-100:],
        "total": len(events),
        "last": max((str(event.get("ts") or "") for event in events), default=""),
    }
