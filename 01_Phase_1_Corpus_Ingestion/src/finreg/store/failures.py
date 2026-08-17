from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from enum import StrEnum


class ReasonCode(StrEnum):
    HTTP_4XX = "http_4xx"
    HTTP_5XX_EXHAUSTED = "http_5xx_exhausted"
    TIMEOUT_EXHAUSTED = "timeout_exhausted"
    ROBOTS_DISALLOWED = "robots_disallowed"
    CONTENT_TYPE_UNEXPECTED = "content_type_unexpected"
    PDF_CORRUPT = "pdf_corrupt"
    EXTRACTION_EMPTY = "extraction_empty"
    LISTING_PARSE_FAILED = "listing_parse_failed"


def record_failure(
    conn: sqlite3.Connection,
    *,
    source_url: str,
    source_name: str,
    reason_code: ReasonCode,
    detail: str | None,
    attempts: int,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    existing = conn.execute(
        """
        SELECT id, attempts FROM fetch_failures
        WHERE source_url = ? AND reason_code = ? AND resolved = 0
        """,
        (source_url, reason_code.value),
    ).fetchone()

    if existing is not None:
        conn.execute(
            """
            UPDATE fetch_failures
            SET attempts = ?, detail = ?, last_seen = ?
            WHERE id = ?
            """,
            (attempts, detail, now, existing["id"]),
        )
    else:
        conn.execute(
            """
            INSERT INTO fetch_failures
                (source_url, source_name, reason_code, detail, attempts, first_seen, last_seen, resolved)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (source_url, source_name, reason_code.value, detail, attempts, now, now),
        )
    conn.commit()
