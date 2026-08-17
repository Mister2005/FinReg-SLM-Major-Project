from __future__ import annotations

import hashlib
import mimetypes
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    (b"%PDF-", "pdf"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpg"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"PK\x03\x04", "zip"),
]


@dataclass(frozen=True)
class StoredBlob:
    sha256: str
    byte_length: int
    content_type: str | None
    extension: str
    stored_path: Path
    is_new: bool


def _sniff_extension(body: bytes, content_type: str | None) -> str:
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if guessed:
            return guessed.lstrip(".")
    for signature, ext in _MAGIC_SIGNATURES:
        if body.startswith(signature):
            return ext
    return "bin"


def blob_path(root: Path, sha256: str, extension: str) -> Path:
    return root / sha256[0:2] / sha256[2:4] / f"{sha256}.{extension}"


def write_blob(
    conn: sqlite3.Connection,
    root: Path,
    body: bytes,
    content_type: str | None,
) -> StoredBlob:
    sha256 = hashlib.sha256(body).hexdigest()
    existing = conn.execute(
        "SELECT sha256, byte_length, content_type, extension, stored_path FROM blobs WHERE sha256 = ?",
        (sha256,),
    ).fetchone()
    if existing is not None:
        return StoredBlob(
            sha256=existing["sha256"],
            byte_length=existing["byte_length"],
            content_type=existing["content_type"],
            extension=existing["extension"],
            stored_path=Path(existing["stored_path"]),
            is_new=False,
        )

    extension = _sniff_extension(body, content_type)
    path = blob_path(root, sha256, extension)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)

    conn.execute(
        """
        INSERT INTO blobs (sha256, byte_length, content_type, extension, stored_path, first_seen_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            sha256,
            len(body),
            content_type,
            extension,
            str(path),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()

    return StoredBlob(
        sha256=sha256,
        byte_length=len(body),
        content_type=content_type,
        extension=extension,
        stored_path=path,
        is_new=True,
    )
