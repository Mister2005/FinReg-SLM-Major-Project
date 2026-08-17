from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timezone


@dataclass(frozen=True)
class NewDocument:
    doc_id: str
    regulator: str
    source_name: str
    doc_type: str
    title: str
    source_url: str
    licence: str
    doc_number: str | None = None
    departmental_ref: str | None = None
    alias_doc_number: str | None = None
    issue_date: date | None = None
    department: str | None = None
    addressee: str | None = None
    pdf_url: str | None = None
    html_sha256: str | None = None
    pdf_sha256: str | None = None
    attribution: str | None = None
    metadata_gaps: list[str] = field(default_factory=list)


def upsert_document(conn: sqlite3.Connection, doc: NewDocument) -> None:
    retrieved_at = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO documents
            (doc_id, regulator, source_name, doc_type, doc_number, departmental_ref,
             alias_doc_number, title, issue_date, department, addressee, source_url, pdf_url,
             html_sha256, pdf_sha256, retrieved_at, status, licence, attribution,
             metadata_gaps)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unknown', ?, ?, ?)
        ON CONFLICT(doc_id) DO UPDATE SET
            doc_type = excluded.doc_type,
            doc_number = excluded.doc_number,
            departmental_ref = excluded.departmental_ref,
            alias_doc_number = excluded.alias_doc_number,
            title = excluded.title,
            issue_date = excluded.issue_date,
            department = excluded.department,
            addressee = excluded.addressee,
            source_url = excluded.source_url,
            pdf_url = excluded.pdf_url,
            html_sha256 = COALESCE(excluded.html_sha256, documents.html_sha256),
            pdf_sha256 = COALESCE(excluded.pdf_sha256, documents.pdf_sha256),
            retrieved_at = excluded.retrieved_at,
            attribution = excluded.attribution,
            metadata_gaps = excluded.metadata_gaps
        """,
        (
            doc.doc_id,
            doc.regulator,
            doc.source_name,
            doc.doc_type,
            doc.doc_number,
            doc.departmental_ref,
            doc.alias_doc_number,
            doc.title,
            doc.issue_date.isoformat() if doc.issue_date else None,
            doc.department,
            doc.addressee,
            doc.source_url,
            doc.pdf_url,
            doc.html_sha256,
            doc.pdf_sha256,
            retrieved_at,
            doc.licence,
            doc.attribution,
            json.dumps(doc.metadata_gaps) if doc.metadata_gaps else None,
        ),
    )
    conn.commit()


def get_document(conn: sqlite3.Connection, doc_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM documents WHERE doc_id = ?", (doc_id,)
    ).fetchone()
