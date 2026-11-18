#!/usr/bin/env python3
"""Registro persistente de trabajos del panel.

Estados canónicos (independientes de la etiqueta que vea la interfaz):

    CREATED → QUEUED → RUNNING → COMPLETED
                                → FAILED
                                → CANCELLED
                                → TIMED_OUT
    (reinicio)  RUNNING/QUEUED → INTERRUPTED

Al arrancar, ningún trabajo puede quedarse en RUNNING: ``recover`` marca los
interrumpidos y el panel los muestra como tales. Nunca se reanuda solo un
trabajo cuyo resultado externo es desconocido.
"""

from __future__ import annotations

import datetime as dt
import time
from pathlib import Path
from typing import Any

import xrepost_store

CREATED = "CREATED"
QUEUED = "QUEUED"
RUNNING = "RUNNING"
COMPLETED = "COMPLETED"
FAILED = "FAILED"
CANCELLED = "CANCELLED"
TIMED_OUT = "TIMED_OUT"
INTERRUPTED = "INTERRUPTED"
STATES = (CREATED, QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED, TIMED_OUT, INTERRUPTED)

# ``status`` conserva el contrato anterior del panel (running/done/error/cancelled).
STATUS_FOR_STATE = {
    CREATED: "running",
    QUEUED: "running",
    RUNNING: "running",
    COMPLETED: "done",
    FAILED: "error",
    CANCELLED: "cancelled",
    TIMED_OUT: "error",
    INTERRUPTED: "interrupted",
}

SENSITIVE_KEYS = {"confirm", "token", "csrf", "password", "secret", "only_urls_file"}


def sanitize_params(params: dict | None) -> dict:
    """Copia los parámetros aptos para disco (sin secretos ni rutas internas)."""
    out: dict[str, Any] = {}
    for key, value in (params or {}).items():
        if key in SENSITIVE_KEYS or str(key).startswith("_"):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            out[key] = value
        elif isinstance(value, (list, tuple)):
            out[key] = [str(item)[:200] for item in value][:200]
        elif isinstance(value, dict):
            out[key] = {str(k)[:80]: str(v)[:200] for k, v in list(value.items())[:40]}
    return out


def _now() -> float:
    return time.time()


def _iso(ts: float | None) -> str:
    if not ts:
        return ""
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat(timespec="seconds")


class JobStore:
    def __init__(self, runs: str | Path, *, max_records: int = 200, max_age_days: int = 30):
        self.runs = Path(runs).expanduser()
        self.path = self.runs / "jobs.json"
        self.max_records = max_records
        self.max_age_days = max_age_days
        self.store = xrepost_store.JsonStore(
            self.path, lambda: {"version": 1, "jobs": []}, max_bytes=2 * 1024 * 1024
        )
        import threading

        self._lock = threading.RLock()

    # -- lectura ---------------------------------------------------------
    def list(self, limit: int = 0) -> list[dict]:
        with self._lock:
            data = self.store.read()
        items = [item for item in data.get("jobs", []) if isinstance(item, dict) and item.get("id")]
        items.sort(key=lambda item: float(item.get("created") or 0), reverse=True)
        return items[:limit] if limit else items

    def get(self, job_id: str) -> dict | None:
        return next((item for item in self.list() if item.get("id") == job_id), None)

    # -- escritura -------------------------------------------------------
    def create(self, job_id: str, kind: str, params: dict) -> dict:
        record = {
            "id": job_id,
            "kind": kind,
            "state": QUEUED,
            "status": STATUS_FOR_STATE[QUEUED],
            "created": _now(),
            "started": 0.0,
            "ended": 0.0,
            "returncode": None,
            "error": "",
            "params": sanitize_params(params),
            "post_count": 0,
            "pid": 0,
        }

        def mutate(data: dict) -> dict:
            items = [item for item in data.get("jobs", []) if isinstance(item, dict)]
            items = [item for item in items if item.get("id") != job_id]
            items.append(record)
            data["jobs"] = items
            return data

        with self._lock:
            self.store.mutate(mutate)
        return record

    def update(self, job_id: str, **fields: Any) -> dict:
        if "state" in fields:
            state = fields["state"]
            if state not in STATES:
                raise ValueError(f"Estado de trabajo no válido: {state}")
            fields.setdefault("status", STATUS_FOR_STATE[state])
        if "params" in fields:
            fields["params"] = sanitize_params(fields["params"])

        updated: dict = {}

        def mutate(data: dict) -> dict:
            for item in data.get("jobs", []):
                if isinstance(item, dict) and item.get("id") == job_id:
                    item.update(fields)
                    item["updated"] = _now()
                    updated.update(item)
                    break
            return data

        with self._lock:
            self.store.mutate(mutate)
        return updated

    def recover(self) -> list[dict]:
        """Marca como INTERRUPTED los trabajos que quedaron a medias."""
        interrupted: list[dict] = []

        def mutate(data: dict) -> dict:
            for item in data.get("jobs", []):
                if not isinstance(item, dict):
                    continue
                if item.get("state") in (RUNNING, QUEUED, CREATED):
                    item["state"] = INTERRUPTED
                    item["status"] = STATUS_FOR_STATE[INTERRUPTED]
                    item["ended"] = item.get("ended") or _now()
                    item["error"] = (
                        "El panel se cerró o reinició con esta ejecución en curso. "
                        "No se reanuda automáticamente: revisa el estado en X antes de repetir."
                    )
                    interrupted.append(dict(item))
            return data

        with self._lock:
            self.store.mutate(mutate)
        return interrupted

    def prune(self, *, keep: set[str] | None = None) -> list[str]:
        """Recorta el registro (no borra directorios: eso lo decide el panel)."""
        keep = keep or set()
        cutoff = _now() - self.max_age_days * 86400
        removed: list[str] = []

        def mutate(data: dict) -> dict:
            items = [item for item in data.get("jobs", []) if isinstance(item, dict)]
            items.sort(key=lambda item: float(item.get("created") or 0), reverse=True)
            kept = []
            for index, item in enumerate(items):
                job_id = str(item.get("id") or "")
                old = float(item.get("created") or 0) < cutoff and item.get("state") not in (RUNNING, QUEUED)
                if job_id in keep or (index < self.max_records and not old):
                    kept.append(item)
                else:
                    removed.append(job_id)
            data["jobs"] = kept
            return data

        with self._lock:
            self.store.mutate(mutate)
        return removed

    def export_view(self, job_id: str) -> dict:
        record = self.get(job_id)
        if not record:
            raise KeyError(job_id)
        return record
