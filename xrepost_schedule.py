#!/usr/bin/env python3
"""Programación de búsquedas (solo recopilación y previsualización).

Decisión de seguridad deliberada: **no existe repost automático programado**.
Una tarea programada únicamente ejecuta una previsualización (dry-run) y deja
los resultados en la bandeja de revisión. Publicar requiere que una persona
revise y confirme.

Frecuencias admitidas: una vez, diaria y semanal. La separación mínima es de 5
minutos para evitar ráfagas contra X. Las fechas se guardan en ISO UTC.
"""

from __future__ import annotations

import calendar
import datetime as dt
import secrets
from pathlib import Path

import xrepost_store

ONCE = "once"
DAILY = "daily"
WEEKLY = "weekly"
MONTHLY = "monthly"
FREQUENCIES = (ONCE, DAILY, WEEKLY, MONTHLY)
MIN_INTERVAL_MINUTES = 5
MAX_SCHEDULES = 50
MODE = "preview"  # fijo: nunca apply


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_iso(value: object) -> dt.datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("Falta la fecha y hora")
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Fecha y hora no válidas (usa ISO 8601)") from None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _add_month(value: dt.datetime) -> dt.datetime:
    month = value.month + 1
    year = value.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def compute_next(item: dict, *, after: dt.datetime | None = None) -> str:
    """Próxima ejecución a partir de la hora base (o cadena vacía si no hay)."""
    base = after or now()
    frequency = item.get("frequency")
    try:
        start = parse_iso(item.get("run_at"))
    except ValueError:
        return ""
    if frequency == ONCE:
        return _iso(start) if start > base else ""
    if frequency in (DAILY, WEEKLY, MONTHLY):
        candidate = start
        while candidate <= base:
            if frequency == DAILY:
                candidate += dt.timedelta(days=1)
            elif frequency == WEEKLY:
                candidate += dt.timedelta(days=7)
            else:
                candidate = _add_month(candidate)
            if candidate.year > base.year + 5:
                return ""
        return _iso(candidate)
    return ""


class ScheduleStore:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self.store = xrepost_store.JsonStore(
            self.path, lambda: {"version": 1, "schedules": []}
        )

    def list(self) -> list[dict]:
        data = self.store.read()
        items = [item for item in data.get("schedules", []) if isinstance(item, dict) and item.get("id")]
        items.sort(key=lambda item: str(item.get("next_run") or "9999"))
        return items

    def get(self, schedule_id: str) -> dict | None:
        return next((item for item in self.list() if item.get("id") == schedule_id), None)

    def create(
        self,
        name: str,
        params: dict,
        *,
        frequency: str,
        run_at: str,
        enabled: bool = True,
        notify: bool = True,
    ) -> dict:
        label = str(name or "").strip()[:80]
        if not label:
            raise ValueError("La programación necesita un nombre")
        if frequency not in FREQUENCIES:
            raise ValueError(f"Frecuencia no válida: {frequency}")
        start = parse_iso(run_at)
        if start <= now():
            raise ValueError("La fecha de la programación debe estar en el futuro")
        item = {
            "id": secrets.token_hex(6),
            "name": label,
            "mode": MODE,
            "params": _clean_params(params),
            "frequency": frequency,
            "run_at": _iso(start),
            "next_run": compute_next({"frequency": frequency, "run_at": _iso(start)}),
            "enabled": bool(enabled),
            "notify": bool(notify),
            "created": _iso(now()),
            "last_run": "",
            "last_job": "",
            "last_result": "",
        }

        def mutate(data: dict) -> dict:
            items = [item for item in data.get("schedules", []) if isinstance(item, dict)]
            if len(items) >= MAX_SCHEDULES:
                raise ValueError(f"Como máximo {MAX_SCHEDULES} programaciones")
            items.append(item)
            data["schedules"] = items
            return data

        self.store.mutate(mutate)
        return item

    def update(self, schedule_id: str, **fields) -> dict:
        allowed = {
            "name",
            "enabled",
            "notify",
            "frequency",
            "run_at",
            "params",
            "last_run",
            "last_job",
            "last_result",
        }
        updated: dict = {}

        def mutate(data: dict) -> dict:
            for item in data.get("schedules", []):
                if not isinstance(item, dict) or item.get("id") != schedule_id:
                    continue
                for key, value in fields.items():
                    if key not in allowed:
                        continue
                    if key == "frequency":
                        if value not in FREQUENCIES:
                            raise ValueError(f"Frecuencia no válida: {value}")
                        item["frequency"] = value
                    elif key == "run_at":
                        item["run_at"] = _iso(parse_iso(value))
                    elif key == "params":
                        item["params"] = _clean_params(value)
                    elif key == "name":
                        label = str(value).strip()[:80]
                        if not label:
                            raise ValueError("La programación necesita un nombre")
                        item["name"] = label
                    elif key in ("last_run", "last_job", "last_result"):
                        item[key] = str(value or "")[:200]
                    else:
                        item[key] = bool(value)
                item["next_run"] = compute_next(item)
                item["updated"] = _iso(now())
                updated.update(item)
                break
            data["schedules"] = data.get("schedules", [])
            return data

        self.store.mutate(mutate)
        if not updated:
            raise KeyError(schedule_id)
        return updated

    def delete(self, schedule_id: str) -> bool:
        removed = {"value": False}

        def mutate(data: dict) -> dict:
            items = [item for item in data.get("schedules", []) if isinstance(item, dict)]
            kept = [item for item in items if item.get("id") != schedule_id]
            removed["value"] = len(kept) != len(items)
            data["schedules"] = kept
            return data

        self.store.mutate(mutate)
        return removed["value"]

    def due(self, *, at: dt.datetime | None = None) -> list[dict]:
        moment = at or now()
        out = []
        for item in self.list():
            if not item.get("enabled") or item.get("mode") != MODE:
                continue
            try:
                due_at = parse_iso(item.get("next_run"))
            except ValueError:
                continue
            if due_at <= moment:
                out.append(item)
        return out

    def mark_run(self, schedule_id: str, *, job_id: str, result: str) -> dict:
        """Registra la ejecución y calcula la siguiente (nunca queda en bucle)."""
        item = self.get(schedule_id)
        if not item:
            raise KeyError(schedule_id)
        moment = now()
        follow = compute_next({**item, "run_at": item.get("run_at")}, after=moment)
        return self.update(
            schedule_id,
            last_run=_iso(moment),
            last_job=job_id,
            last_result=result,
            next_run=follow,
        )


def _clean_params(params: dict) -> dict:
    allowed = {"users", "from", "to", "scope", "limit", "delay", "match", "exclude", "quote", "profile_id"}
    out = {}
    for key in allowed:
        value = params.get(key)
        if isinstance(value, (str, int, float, bool)) and value is not None:
            out[key] = value
    return out


def default_schedule_path(history: str | Path) -> Path:
    return Path(history).expanduser().parent / "schedules.json"
