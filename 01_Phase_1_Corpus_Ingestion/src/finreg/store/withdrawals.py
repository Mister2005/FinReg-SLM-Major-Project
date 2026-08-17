from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone


@dataclass(frozen=True)
class WithdrawnEntry:
    source_name: str
    source_url: str
    raw_circular_no: str
    raw_title: str
    raw_date: str | None
    parsed_date: date | None
    matched_doc_id: str | None


def insert_withdrawn_entry(conn: sqlite3.Connection, entry: WithdrawnEntry) -> None:
    conn.execute(
        """
        INSERT INTO withdrawn_circulars
            (source_name, source_url, raw_circular_no, raw_title, raw_date,
             parsed_date, matched_doc_id, retrieved_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entry.source_name,
            entry.source_url,
            entry.raw_circular_no,
            entry.raw_title,
            entry.raw_date,
            entry.parsed_date.isoformat() if entry.parsed_date else None,
            entry.matched_doc_id,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()


def match_rate(conn: sqlite3.Connection, source_name: str) -> float:
    """Fraction of withdrawn_circulars rows whose circular-number reference was
    resolved to a doc_id (i.e. the listing row carried a usable document link).
    Unresolved rows are retained with raw text, never dropped."""
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN matched_doc_id IS NOT NULL THEN 1 ELSE 0 END) AS matched
        FROM withdrawn_circulars
        WHERE source_name = ?
        """,
        (source_name,),
    ).fetchone()
    if row["total"] == 0:
        return 0.0
    return row["matched"] / row["total"]


def existing_document_match_rate(conn: sqlite3.Connection, source_name: str) -> float:
    """Fraction of withdrawn_circulars rows whose matched_doc_id resolves to an
    already-ingested documents row. Only meaningful after the corresponding
    notification crawl has run; used by the temporal resolver, not by ingest."""
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(
                CASE WHEN EXISTS (
                    SELECT 1 FROM documents d WHERE d.doc_id = withdrawn_circulars.matched_doc_id
                ) THEN 1 ELSE 0 END
            ) AS matched
        FROM withdrawn_circulars
        WHERE source_name = ?
        """,
        (source_name,),
    ).fetchone()
    if row["total"] == 0:
        return 0.0
    return row["matched"] / row["total"]
