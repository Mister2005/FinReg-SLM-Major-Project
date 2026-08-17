from __future__ import annotations

import sqlite3

from finreg.normalize.doc_number import (
    match_rbi_departmental_reference,
    match_rbi_master_reference,
)
from finreg.normalize.citations import CitationCandidate
from finreg.store.citations import insert_citation, resolve_circular_target


def parse_subsumption_table(rows: list[list[str]]) -> list[str]:
    """Extract candidate subsumed-circular reference strings from a Master
    Circular/Direction appendix table (as produced by extract/tables.py).
    Returns the raw matched reference text per row that names one, skipping
    header/blank rows. Never fabricates an entry for a row with no match."""
    references: list[str] = []
    for row in rows:
        row_text = " | ".join(cell for cell in row if cell)
        match = match_rbi_master_reference(row_text) or match_rbi_departmental_reference(row_text)
        if match:
            references.append(match)
    return references


def ingest_master_consolidation(
    conn: sqlite3.Connection, master_doc_id: str, rows: list[list[str]]
) -> tuple[int, int]:
    """Resolve each subsumed-circular reference in a consolidation table to a
    doc_id and store it as a `supersedes` citation from the master document.
    Returns (total_entries, resolved_count); unresolved entries are retained
    as citations rows with target_doc_id NULL, never dropped."""
    references = parse_subsumption_table(rows)
    resolved_count = 0
    for reference in references:
        target_doc_id = resolve_circular_target(conn, reference, None)
        if target_doc_id is not None:
            resolved_count += 1
        candidate = CitationCandidate(
            raw_span=reference,
            char_start=0,
            char_end=len(reference),
            citation_type="circular" if target_doc_id else "unresolved",
            target_act=None,
            target_section=None,
            relation="supersedes",
            confidence=1.0 if target_doc_id else 0.5,
            circular_number=reference,
        )
        insert_citation(conn, master_doc_id, candidate, target_doc_id=target_doc_id)
    return len(references), resolved_count
