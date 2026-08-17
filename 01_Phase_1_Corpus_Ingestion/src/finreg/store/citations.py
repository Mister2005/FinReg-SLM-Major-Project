from __future__ import annotations

import sqlite3

from finreg.normalize.citations import CitationCandidate, extract_citations


def insert_citation(
    conn: sqlite3.Connection,
    doc_id: str,
    candidate: CitationCandidate,
    *,
    target_doc_id: str | None = None,
    relation: str | None = None,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO citations
            (doc_id, raw_span, char_start, char_end, citation_type,
             target_doc_id, target_act, target_section, relation, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            doc_id,
            candidate.raw_span,
            candidate.char_start,
            candidate.char_end,
            candidate.citation_type,
            target_doc_id,
            candidate.target_act,
            candidate.target_section,
            relation if relation is not None else candidate.relation,
            candidate.confidence,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def resolve_circular_target(
    conn: sqlite3.Connection, doc_number: str, issue_date_iso: str | None
) -> str | None:
    if issue_date_iso is not None:
        row = conn.execute(
            "SELECT doc_id FROM documents WHERE (doc_number = ? OR alias_doc_number = ? OR departmental_ref = ?) AND issue_date = ?",
            (doc_number, doc_number, doc_number, issue_date_iso),
        ).fetchone()
        if row is not None:
            return row["doc_id"]
    row = conn.execute(
        "SELECT doc_id FROM documents WHERE doc_number = ? OR alias_doc_number = ? OR departmental_ref = ?",
        (doc_number, doc_number, doc_number),
    ).fetchone()
    return row["doc_id"] if row is not None else None


def citations_for_doc(conn: sqlite3.Connection, doc_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM citations WHERE doc_id = ?", (doc_id,)
    ).fetchall()


def extract_and_store_citations(conn: sqlite3.Connection, doc_id: str, text: str) -> int:
    candidates = extract_citations(text)
    for candidate in candidates:
        target_doc_id = None
        citation_type = candidate.citation_type
        if candidate.citation_type == "circular" and candidate.circular_number:
            target_doc_id = resolve_circular_target(
                conn,
                candidate.circular_number,
                candidate.circular_date.isoformat() if candidate.circular_date else None,
            )
            if target_doc_id is None:
                citation_type = "unresolved"
        candidate_to_store = candidate if citation_type == candidate.citation_type else CitationCandidate(
            raw_span=candidate.raw_span,
            char_start=candidate.char_start,
            char_end=candidate.char_end,
            citation_type=citation_type,
            target_act=candidate.target_act,
            target_section=candidate.target_section,
            relation=candidate.relation,
            confidence=candidate.confidence,
            circular_number=candidate.circular_number,
            circular_date=candidate.circular_date,
        )
        insert_citation(conn, doc_id, candidate_to_store, target_doc_id=target_doc_id)
    return len(candidates)
