#!/usr/bin/env python3
"""Máquina de estados explícita por publicación.

Estados canónicos (independientes de las etiquetas que muestra el panel):

    DISCOVERED → SELECTED → PENDING → EXECUTING → CONFIRMED
                                              → UNCONFIRMED
                                              → FAILED
    CONFIRMED → UNDO_PENDING → UNDONE

``SKIPPED`` representa una decisión humana de no publicar. Las transiciones
están validadas: un estado terminal no puede volver a ejecutarse sin una
decisión explícita, y un resultado incierto nunca pasa a ``CONFIRMED`` sin una
comprobación real.

La bandeja (``xrepost_inbox``) sigue usando sus etiquetas históricas
(``pending``, ``approved``…); este módulo es la capa canónica que se guarda en
el campo ``state`` de cada elemento.
"""

from __future__ import annotations

from typing import Iterable

DISCOVERED = "DISCOVERED"
SELECTED = "SELECTED"
PENDING = "PENDING"
EXECUTING = "EXECUTING"
CONFIRMED = "CONFIRMED"
UNCONFIRMED = "UNCONFIRMED"
FAILED = "FAILED"
SKIPPED = "SKIPPED"
UNDO_PENDING = "UNDO_PENDING"
UNDONE = "UNDONE"

STATES = (
    DISCOVERED,
    SELECTED,
    PENDING,
    EXECUTING,
    CONFIRMED,
    UNCONFIRMED,
    FAILED,
    SKIPPED,
    UNDO_PENDING,
    UNDONE,
)

#: Transiciones permitidas desde cada estado. Incluye las rutas de recuperación
#: que un resultado externo puede exigir (por ejemplo, un fallo que se reintenta
#: tras revisarlo a mano). No incluye atajos que saltarían la verificación real.
TRANSITIONS: dict[str, frozenset[str]] = {
    DISCOVERED: frozenset({PENDING, SELECTED, SKIPPED}),
    PENDING: frozenset({SELECTED, SKIPPED, EXECUTING}),
    SELECTED: frozenset({PENDING, SKIPPED, EXECUTING, UNCONFIRMED, FAILED}),
    EXECUTING: frozenset({CONFIRMED, UNCONFIRMED, FAILED}),
    CONFIRMED: frozenset({UNDO_PENDING}),
    UNCONFIRMED: frozenset({CONFIRMED, FAILED, PENDING, EXECUTING}),
    FAILED: frozenset({PENDING, SELECTED, SKIPPED, UNCONFIRMED}),
    SKIPPED: frozenset({PENDING, SELECTED}),
    UNDO_PENDING: frozenset({UNDONE, CONFIRMED, FAILED}),
    UNDONE: frozenset(),
}

#: Etiquetas históricas de la bandeja → estado canónico.
STATUS_TO_STATE = {
    "pending": PENDING,
    "approved": SELECTED,
    "rejected": SKIPPED,
    "queued": EXECUTING,
    "executed": EXECUTING,
    "verified": CONFIRMED,
    "unconfirmed": UNCONFIRMED,
    "failed": FAILED,
    "undo_pending": UNDO_PENDING,
    "undone": UNDONE,
}


class TransitionError(ValueError):
    """Transición no permitida entre dos estados canónicos."""


def state_for(status: str) -> str:
    """Traduce una etiqueta de la bandeja a su estado canónico.

    Una etiqueta desconocida se trata como ``DISCOVERED``: nunca se asume que
    una publicación se publicó por un valor inesperado.
    """
    return STATUS_TO_STATE.get(str(status or "").strip().lower(), DISCOVERED)


def can(origin: str, target: str) -> bool:
    """``True`` si la transición está permitida (mismo estado es idempotente)."""
    if origin == target:
        return True
    return target in TRANSITIONS.get(origin, frozenset())


def require(origin: str, target: str) -> None:
    """Valida la transición o lanza :class:`TransitionError`."""
    if not can(origin, target):
        raise TransitionError(f"Transición no permitida: {origin} → {target}")


def normalize(state: str | None, status: str = "") -> str:
    """Devuelve un estado canónico a partir de ``state`` o de ``status``."""
    value = str(state or "").strip()
    if value.upper() in STATES:
        return value.upper()
    return state_for(value or status)


def next_state(origin: str, target: str, *, status: str = "") -> str:
    """Valida y devuelve ``target``; si falta, se deduce de ``status``."""
    destination = normalize(target, status)
    require(normalize(origin), destination)
    return destination


def history_summary(states: Iterable[str]) -> dict[str, int]:
    """Cuenta elementos por estado canónico (incluye estados vacíos)."""
    counts = {state: 0 for state in STATES}
    for state in states:
        canonical = normalize(state)
        counts[canonical] = counts.get(canonical, 0) + 1
    return counts
