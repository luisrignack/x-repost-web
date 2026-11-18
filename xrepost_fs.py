#!/usr/bin/env python3
"""Utilidades de sistema de archivos seguro para xrepost.

Todo lo que la aplicación escribe vive bajo el directorio de estado del usuario
(``~/.local/state/xrepost`` por defecto). Este módulo centraliza las reglas que
antes estaban dispersas o ausentes:

* directorios privados ``0700`` y archivos sensibles ``0600``;
* escrituras atómicas (temporal en el mismo directorio + ``os.replace``);
* rechazo de enlaces simbólicos en rutas sensibles (evita que un enlace
  colocado por otro usuario redirija el historial o las cuentas);
* bloqueo entre procesos (``flock``) para las operaciones de lectura-modificación;
* validación de que una ruta destino sigue dentro de la carpeta permitida;
* límites de tamaño al leer (un archivo corrupto gigante no agota la memoria).

No se aplica ``chmod`` a carpetas ajenas: solo a rutas que la aplicación crea o
que ya están dentro de su directorio de datos.
"""

from __future__ import annotations

import contextlib
import errno
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any, Iterator

DIR_MODE = 0o700
FILE_MODE = 0o600
DEFAULT_MAX_BYTES = 8 * 1024 * 1024


class UnsafePathError(RuntimeError):
    """La ruta no cumple las reglas de seguridad (enlace, dueño o traversal)."""


def _is_symlink(path: Path) -> bool:
    try:
        return path.is_symlink()
    except OSError:
        return True


def ensure_dir(path: str | Path, mode: int = DIR_MODE) -> Path:
    """Crea (si hace falta) un directorio privado y devuelve su ruta."""
    target = Path(path).expanduser()
    if _is_symlink(target):
        raise UnsafePathError(f"El directorio es un enlace simbólico: {target}")
    try:
        target.mkdir(parents=True, exist_ok=True, mode=mode)
    except FileExistsError:
        pass
    if not target.is_dir():
        raise UnsafePathError(f"No es un directorio: {target}")
    if _is_symlink(target):
        raise UnsafePathError(f"El directorio es un enlace simbólico: {target}")
    try:
        current = stat.S_IMODE(target.stat().st_mode)
        if current & 0o077:
            os.chmod(target, mode)
    except OSError:
        # En sistemas sin permisos POSIX (o carpetas de solo lectura) se
        # continúa: la comprobación de dueño y el resto de reglas siguen.
        pass
    return target


def assert_owned(path: str | Path) -> None:
    """Comprueba que el archivo/directorio pertenece al usuario actual."""
    if os.name != "posix":
        return
    target = Path(path).expanduser()
    try:
        info = target.stat()
    except OSError as exc:
        raise UnsafePathError(f"No se pudo comprobar el propietario de {target}: {exc}") from exc
    euid = getattr(os, "geteuid", lambda: info.st_uid)()
    if info.st_uid != euid:
        raise UnsafePathError(
            f"{target} pertenece a otro usuario (uid {info.st_uid}); se rechaza por seguridad"
        )


def assert_regular_file(path: str | Path) -> Path:
    """Rechaza enlaces simbólicos y tipos especiales."""
    target = Path(path).expanduser()
    if _is_symlink(target):
        raise UnsafePathError(f"Se rechaza un enlace simbólico: {target}")
    try:
        info = target.lstat()
    except OSError as exc:
        raise UnsafePathError(f"No existe o no se puede leer: {target} ({exc})") from exc
    if not stat.S_ISREG(info.st_mode):
        raise UnsafePathError(f"No es un archivo normal: {target}")
    return target


def _secure_chmod(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def atomic_write(
    path: str | Path,
    data: str | bytes,
    *,
    mode: int = FILE_MODE,
    create_parents: bool = True,
) -> Path:
    """Escribe un archivo de forma atómica y con permisos privados."""
    dest = Path(path).expanduser()
    parent = dest.parent
    if create_parents:
        ensure_dir(parent)
    if _is_symlink(dest):
        raise UnsafePathError(f"Se rechaza escribir sobre un enlace simbólico: {dest}")

    payload = data.encode("utf-8") if isinstance(data, str) else data
    fd, tmp_name = tempfile.mkstemp(dir=str(parent), prefix=".xrepost-", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        _secure_chmod(tmp, mode)
        os.replace(tmp, dest)
        _secure_chmod(dest, mode)
        try:
            dir_fd = os.open(parent, os.O_RDONLY)
        except OSError:
            dir_fd = -1
        if dir_fd >= 0:
            try:
                os.fsync(dir_fd)
            except OSError:
                pass
            finally:
                os.close(dir_fd)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise
    return dest


def write_json(path: str | Path, payload: Any, *, mode: int = FILE_MODE) -> Path:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    return atomic_write(path, text, mode=mode)


def read_text(
    path: str | Path,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    default: str | None = None,
) -> str | None:
    """Lee texto con límite de tamaño; nunca sigue enlaces simbólicos."""
    target = Path(path).expanduser()
    if _is_symlink(target):
        raise UnsafePathError(f"Se rechaza leer un enlace simbólico: {target}")
    try:
        with open(target, "rb") as fh:
            raw = fh.read(max_bytes + 1)
    except FileNotFoundError:
        return default
    except OSError as exc:
        if default is not None:
            return default
        raise UnsafePathError(f"No se pudo leer {target}: {exc}") from exc
    if len(raw) > max_bytes:
        raise UnsafePathError(f"{target} supera el tamaño máximo permitido ({max_bytes} bytes)")
    return raw.decode("utf-8", errors="replace")


def read_json(path: str | Path, default: Any = None, *, max_bytes: int = DEFAULT_MAX_BYTES) -> Any:
    text = read_text(path, max_bytes=max_bytes, default=None)
    if text is None or not text.strip():
        return default
    try:
        return json.loads(text)
    except ValueError:
        return default


@contextlib.contextmanager
def locked(path: str | Path, *, exclusive: bool = True) -> Iterator[None]:
    """Bloqueo entre procesos basado en un archivo ``.lock`` al lado del destino."""
    lock_path = Path(path).expanduser()
    ensure_dir(lock_path.parent)
    # El archivo de bloqueo no contiene datos: se abre en append para no
    # truncar el de otro proceso que llegue justo después.
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_APPEND, FILE_MODE)
    try:
        try:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        except (ImportError, OSError):
            pass
        yield
    finally:
        try:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_UN)
        except (ImportError, OSError):
            pass
        os.close(fd)


def append_line(path: str | Path, line: str, *, mode: int = FILE_MODE) -> None:
    """Añade una línea JSON de forma segura y sincronizada.

    Se usa ``O_NOFOLLOW`` para no escribir a través de un enlace simbólico y un
    ``flock`` para que el motor y el panel no mezclen líneas.
    """
    target = Path(path).expanduser()
    ensure_dir(target.parent)
    if _is_symlink(target):
        raise UnsafePathError(f"Se rechaza escribir sobre un enlace simbólico: {target}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    with locked(str(target) + ".append.lock"):
        fd = os.open(target, flags, mode)
        try:
            _secure_chmod(target, mode)
            data = (line.rstrip("\n") + "\n").encode("utf-8")
            written = 0
            while written < len(data):
                written += os.write(fd, data[written:])
            os.fsync(fd)
        finally:
            os.close(fd)


def safe_join(base: str | Path, *parts: str) -> Path:
    """Une rutas y garantiza que el resultado queda dentro de ``base``."""
    root = Path(base).expanduser().resolve()
    candidate = root.joinpath(*parts).resolve()
    if candidate != root and not candidate.is_relative_to(root):
        raise UnsafePathError(f"Ruta fuera del directorio permitido: {candidate}")
    return candidate


def is_within(base: str | Path, candidate: str | Path) -> bool:
    root = Path(base).expanduser().resolve()
    target = Path(candidate).expanduser().resolve()
    return target == root or target.is_relative_to(root)


def backup_file(src: str | Path, dest: str | Path) -> Path:
    """Copia un archivo con escritura atómica y permisos privados."""
    data = Path(src).expanduser().read_bytes()
    return atomic_write(dest, data)


def remove_tree(path: str | Path, base: str | Path) -> None:
    """Elimina un árbol solo si está dentro de ``base`` (nunca rutas ajenas)."""
    import shutil

    target = Path(path).expanduser()
    if not is_within(base, target) or Path(base).resolve() == target.resolve():
        raise UnsafePathError(f"Se rechaza borrar fuera de {base}: {target}")
    if target.is_symlink():
        target.unlink(missing_ok=True)
        return
    if target.exists():
        shutil.rmtree(target)


def file_size(path: str | Path) -> int:
    try:
        return Path(path).expanduser().stat().st_size
    except OSError:
        return 0


def ensure_private_file(path: str | Path, mode: int = FILE_MODE) -> None:
    """Ajusta permisos de un archivo sensible ya existente."""
    target = Path(path).expanduser()
    if _is_symlink(target):
        raise UnsafePathError(f"Se rechaza un enlace simbólico: {target}")
    if target.exists():
        _secure_chmod(target, mode)


def no_follow_open_flags() -> int:
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags


def describe_error(exc: OSError) -> str:
    if exc.errno == errno.ELOOP:
        return "enlace simbólico rechazado"
    return str(exc)
