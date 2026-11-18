#!/usr/bin/env python3
"""Exportaciones de xrepost: CSV, Markdown, JSON, HTML, PDF y backup.

* El CSV neutraliza fórmulas (``=``, ``+``, ``-``, ``@``, tabulador y retorno)
  anteponiendo un apóstrofo, para que una publicación no ejecute fórmulas al
  abrirse en una hoja de cálculo.
* El HTML escapa todo el contenido.
* El PDF se genera con un escritor mínimo (sin dependencias) y texto Latin-1
  sustituyendo lo no representable; es un PDF válido, no una captura.
* El backup es un ``.tar.gz`` con lista blanca de archivos y la restauración
  rechaza miembros con rutas absolutas o ``..``.
"""

from __future__ import annotations

import csv
import datetime as dt
import html
import io
import json
import os
import tarfile
import zlib
from pathlib import Path
from typing import Iterable

import xrepost_fs

DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
CSV_FIELDS = ["fecha", "autor", "usuario", "texto", "url", "estado"]


def csv_safe(value: object) -> str:
    text = "" if value is None else str(value)
    if text.startswith(DANGEROUS_PREFIXES):
        return "'" + text
    return text


def rows_to_csv(rows: Iterable[dict], fields: list[str] | None = None) -> str:
    fields = fields or CSV_FIELDS
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: csv_safe(row.get(field, "")) for field in fields})
    return buffer.getvalue()


def write_csv(rows: Iterable[dict], path: str | Path, fields: list[str] | None = None) -> Path:
    return xrepost_fs.atomic_write(path, rows_to_csv(rows, fields))


def _md_escape(value: object) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ").strip()


def rows_to_markdown(rows: Iterable[dict], *, title: str = "Publicaciones") -> str:
    lines = [f"# {title}", "", "| Fecha | Autor | Texto | Enlace | Estado |", "|---|---|---|---|---|"]
    for row in rows:
        author = f"{_md_escape(row.get('autor', ''))} {_md_escape(row.get('usuario', ''))}".strip()
        lines.append(
            f"| {_md_escape(row.get('fecha', ''))} | {author} | "
            f"{_md_escape(row.get('texto', ''))} | [post]({_md_escape(row.get('url', ''))}) | "
            f"{_md_escape(row.get('estado', ''))} |"
        )
    return "\n".join(lines) + "\n"


def write_markdown(rows: Iterable[dict], path: str | Path, *, title: str = "Publicaciones") -> Path:
    return xrepost_fs.atomic_write(path, rows_to_markdown(rows, title=title))


def write_json(payload: object, path: str | Path) -> Path:
    return xrepost_fs.atomic_write(
        path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    )


def rows_to_html(rows: Iterable[dict], *, title: str = "Informe de xrepost", subtitle: str = "") -> str:
    rows = list(rows)
    body = []
    for row in rows:
        link = html.escape(str(row.get("url") or ""), quote=True)
        body.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('fecha', '')))}</td>"
            f"<td><strong>{html.escape(str(row.get('autor', '')))}</strong>"
            f"<br><span class='muted'>{html.escape(str(row.get('usuario', '')))}</span></td>"
            f"<td>{html.escape(str(row.get('texto', '')))}</td>"
            f"<td>{'<a href=\"' + link + '\" rel=\"noopener noreferrer\">Ver en X</a>' if link else ''}</td>"
            f"<td><span class='pill'>{html.escape(str(row.get('estado', '')))}</span></td>"
            "</tr>"
        )
    generated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root{{color-scheme:light dark}}
body{{font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;margin:0;padding:32px;background:#0b1220;color:#f1f5f9}}
main{{max-width:1100px;margin:0 auto}}
h1{{font-size:22px;margin:0 0 4px}} .muted{{color:#94a3b8}}
meta, .sub{{color:#94a3b8;font-size:12.5px}}
table{{width:100%;border-collapse:collapse;margin-top:18px;background:#111c2e;border:1px solid #1b293d;border-radius:12px;overflow:hidden}}
th,td{{padding:10px 12px;border-bottom:1px solid #1b293d;text-align:left;vertical-align:top}}
th{{background:#1b293d;font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#94a3b8}}
a{{color:#38bdf8}} .pill{{display:inline-block;padding:2px 8px;border-radius:999px;background:#1b293d;font-size:11.5px}}
</style></head>
<body><main>
<h1>{html.escape(title)}</h1>
<p class="sub">{html.escape(subtitle)}</p>
<p class="sub">Generado {html.escape(generated)} · {len(rows)} filas</p>
<table><thead><tr><th>Fecha</th><th>Autor</th><th>Publicación</th><th>Enlace</th><th>Estado</th></tr></thead>
<tbody>{''.join(body)}</tbody></table>
</main></body></html>
"""


def write_html(rows: Iterable[dict], path: str | Path, *, title: str = "Informe de xrepost", subtitle: str = "") -> Path:
    rows = list(rows)
    return xrepost_fs.atomic_write(path, rows_to_html(rows, title=title, subtitle=subtitle))


# --- PDF mínimo -------------------------------------------------------------


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_text(value: object) -> str:
    text = str(value if value is not None else "")
    text = text.encode("latin-1", "replace").decode("latin-1")
    return _pdf_escape(text)


def _wrap(text: str, width: int) -> list[str]:
    text = " ".join(str(text).split())
    if not text:
        return [""]
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            while len(word) > width:
                lines.append(word[:width])
                word = word[width:]
            current = word
    if current:
        lines.append(current)
    return lines


def rows_to_pdf(rows: Iterable[dict], *, title: str = "Informe de xrepost", subtitle: str = "") -> bytes:
    rows = list(rows)
    lines: list[str] = [title]
    if subtitle:
        lines.append(subtitle)
    lines.append(dt.datetime.now(dt.timezone.utc).strftime("Generado %Y-%m-%d %H:%M UTC"))
    lines.append("")
    for index, row in enumerate(rows, 1):
        head = f"{index}. {row.get('autor', '')} {row.get('usuario', '')} · {row.get('fecha', '')} · {row.get('estado', '')}"
        lines.extend(_wrap(head, 92))
        lines.extend("   " + line for line in _wrap(str(row.get("texto", "")), 90))
        url = str(row.get("url", ""))
        if url:
            lines.append("   " + url)
        lines.append("")

    per_page = 46
    pages = [lines[i : i + per_page] for i in range(0, max(1, len(lines)), per_page)] or [[title]]
    objects: list[bytes] = []
    page_ids: list[int] = []

    def add(obj: bytes) -> int:
        objects.append(obj)
        return len(objects)

    catalog_id = add(b"")
    pages_id = add(b"")
    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")

    for page_lines in pages:
        stream_ops = ["BT", "/F1 10 Tf", "14 TL", "48 800 Td"]
        for line in page_lines:
            stream_ops.append(f"({_pdf_text(line)}) Tj")
            stream_ops.append("T*")
        stream_ops.append("ET")
        stream = "\n".join(stream_ops).encode("latin-1", "replace")
        compressed = zlib.compress(stream)
        content_id = add(
            b"<< /Length " + str(len(compressed)).encode() + b" /Filter /FlateDecode >>\nstream\n"
            + compressed
            + b"\nendstream"
        )
        page_id = add(
            b"<< /Type /Page /Parent " + str(pages_id).encode() + b" 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 " + str(font_id).encode() + b" 0 R >> >> "
            b"/Contents " + str(content_id).encode() + b" 0 R >>"
        )
        page_ids.append(page_id)

    kids = b" ".join(str(pid).encode() + b" 0 R" for pid in page_ids)
    objects[catalog_id - 1] = b"<< /Type /Catalog /Pages " + str(pages_id).encode() + b" 0 R >>"
    objects[pages_id - 1] = (
        b"<< /Type /Pages /Count " + str(len(page_ids)).encode() + b" /Kids [" + kids + b"] >>"
    )

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        b"trailer\n<< /Size " + str(len(objects) + 1).encode() + b" /Root "
        + str(catalog_id).encode() + b" 0 R >>\nstartxref\n"
        + str(xref_at).encode() + b"\n%%EOF\n"
    )
    return bytes(out)


def write_pdf(rows: Iterable[dict], path: str | Path, *, title: str = "Informe de xrepost", subtitle: str = "") -> Path:
    return xrepost_fs.atomic_write(path, rows_to_pdf(rows, title=title, subtitle=subtitle))


# --- backup -----------------------------------------------------------------

DEFAULT_BACKUP_PATHS = (
    "history.jsonl",
    "accounts.json",
    "hashtags.json",
    "network.json",
    "groups.json",
    "profiles.json",
    "inbox.json",
    "schedules.json",
)


def backup_bundle(
    state_dir: str | Path,
    dest: str | Path,
    *,
    extra: Iterable[str | Path] = (),
) -> dict:
    """Crea un tar.gz con los documentos de estado (nunca perfiles de Chrome)."""
    base = Path(state_dir).expanduser().resolve()
    target = Path(dest).expanduser()
    xrepost_fs.ensure_dir(target.parent)
    names: list[str] = []
    candidates = list(DEFAULT_BACKUP_PATHS) + [str(item) for item in extra]
    tmp = target.with_name(target.name + ".tmp")
    with tarfile.open(tmp, "w:gz") as tar:
        for name in candidates:
            path = xrepost_fs.safe_join(base, name)
            if not path.exists() or path.is_symlink() or not path.is_file():
                continue
            tar.add(path, arcname=path.name)
            names.append(path.name)
    xrepost_fs.atomic_write(target, tmp.read_bytes())
    tmp.unlink(missing_ok=True)
    return {
        "path": str(target),
        "bytes": xrepost_fs.file_size(target),
        "files": names,
    }


def restore_bundle(archive: str | Path, state_dir: str | Path, *, allow: Iterable[str] = DEFAULT_BACKUP_PATHS) -> dict:
    """Restaura un backup rechazando rutas fuera del directorio de estado."""
    base = xrepost_fs.ensure_dir(state_dir)
    allowed = {Path(name).name for name in allow}
    restored: list[str] = []
    skipped: list[str] = []
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            name = Path(member.name)
            if not member.isfile() or name.is_absolute() or ".." in name.parts or name.name not in allowed:
                skipped.append(member.name)
                continue
            source = tar.extractfile(member)
            if source is None:
                skipped.append(member.name)
                continue
            xrepost_fs.atomic_write(base / name.name, source.read())
            restored.append(name.name)
    return {"restored": restored, "skipped": skipped}


def new_backup_path(state_dir: str | Path) -> Path:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(state_dir).expanduser() / "backups" / f"xrepost-backup-{stamp}.tar.gz"
