#!/usr/bin/env python3
"""Almacén JSON pequeño, concurrente y tolerante a corrupción.

Lo usan las funciones nuevas (grupos, perfiles, bandeja, programación y el
registro de trabajos). Mantiene el formato JSON legible del proyecto, escribe
de forma atómica y bloquea la lectura-modificación entre procesos.

No sustituye al historial JSONL: ese es un registro de eventos y aquí se
guardan documentos de estado pequeños.
"""

from __future__ import annotations

import copy
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

import xrepost_fs

VERSION = 1


class JsonStore:
    def __init__(
        self,
        path: str | Path,
        default: Callable[[], Any],
        *,
        version: int = VERSION,
        max_bytes: int = 4 * 1024 * 1024,
    ):
        self.path = Path(path).expanduser()
        self._default = default
        self.version = version
        self.max_bytes = max_bytes
        self._corrupt_backup = ""

    # -- lectura ---------------------------------------------------------
    def read(self) -> Any:
        data = xrepost_fs.read_json(self.path, default=None, max_bytes=self.max_bytes)
        if data is None:
            return copy.deepcopy(self._default())
        if not isinstance(data, dict):
            self._quarantine("no es un objeto JSON")
            return copy.deepcopy(self._default())
        if int(data.get("version") or 0) > self.version:
            raise ValueError(
                f"{self.path} fue escrito por una versión más nueva "
                f"(version {data.get('version')}); actualiza xrepost"
            )
        return data

    def _quarantine(self, reason: str) -> None:
        """Aparta un archivo corrupto en vez de sobrescribirlo sin avisar."""
        try:
            stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
            dest = self.path.with_name(f"{self.path.name}.corrupt-{stamp}")
            if self.path.exists():
                os.replace(self.path, dest)
                self._corrupt_backup = str(dest)
                print(f"  (aviso: {self.path} {reason}; se guardó como {dest})")
        except OSError:
            self._corrupt_backup = ""

    # -- escritura -------------------------------------------------------
    def write(self, data: Any) -> Any:
        payload = dict(data) if isinstance(data, dict) else {"value": data}
        payload["version"] = self.version
        xrepost_fs.write_json(self.path, payload)
        return payload

    def mutate(self, fn: Callable[[Any], Any]) -> Any:
        """Lee, transforma y escribe bajo bloqueo entre procesos."""
        xrepost_fs.ensure_dir(self.path.parent)
        with xrepost_fs.locked(str(self.path) + ".lock"):
            data = self.read()
            result = fn(data)
            if result is None:
                result = data
            self.write(result)
            return result

    # -- utilidades ------------------------------------------------------
    @property
    def corrupt_backup(self) -> str:
        return self._corrupt_backup

    def exists(self) -> bool:
        return self.path.exists()

    def as_json(self) -> str:
        return json.dumps(self.read(), ensure_ascii=False, indent=2)
