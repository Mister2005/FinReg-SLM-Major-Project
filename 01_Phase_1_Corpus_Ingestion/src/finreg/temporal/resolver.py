from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone

from finreg.temporal.graph import build_edges_from_citations, detect_cycles


@dataclass(frozen=True)
class ResolutionSummary:
    withdrawn_from_listings: int
    superseded_from_citations: int
    in_force_from_defaulted: int
    cycles_detected: int
    metadata_gaps_added: int = field(default=0)


def _step1_withdrawal_listings(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        SELECT matched_doc_id, parsed_date FROM withdrawn_circulars
        WHERE matched_doc_id IS NOT NULL
        """
    ).fetchall()

    count = 0
    for row in rows:
        doc = conn.execute(
            "SELECT status, metadata_gaps FROM documents WHERE doc_id = ?", (row["matched_doc_id"],)
        ).fetchone()
        if doc is None:
            continue
        gaps = json.loads(doc["metadata_gaps"]) if doc["metadata_gaps"] else []
        if row["parsed_date"] is None:
            gaps.append(
                "in_force_to: withdrawn-listing date unparseable, left NULL rather than guessed"
            )
        conn.execute(
            """
            UPDATE documents
            SET status = 'withdrawn', in_force_to = ?, metadata_gaps = ?
            WHERE doc_id = ?
            """,
            (row["parsed_date"], json.dumps(gaps) if gaps else None, row["matched_doc_id"]),
        )
        count += 1
    conn.commit()
    return count


def _step2_and_3_citation_and_consolidation_edges(conn: sqlite3.Connection) -> int:
    edges = build_edges_from_citations(conn)
    count = 0
    for edge in edges:
        target = conn.execute(
            "SELECT status FROM documents WHERE doc_id = ?", (edge.target_doc_id,)
        ).fetchone()
        if target is None or target["status"] == "withdrawn":
            continue  # withdrawn wins — never overwritten by a weaker signal

        source_issue_date = conn.execute(
            "SELECT issue_date FROM documents WHERE doc_id = ?", (edge.source_doc_id,)
        ).fetchone()
        in_force_to = source_issue_date["issue_date"] if source_issue_date else None

        conn.execute(
            """
            UPDATE documents
            SET status = 'superseded', superseded_by = ?, in_force_to = ?
            WHERE doc_id = ?
            """,
            (edge.source_doc_id, in_force_to, edge.target_doc_id),
        )
        count += 1
    conn.commit()
    return count


def _step4_in_force_from_fallback(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        "SELECT doc_id, issue_date, metadata_gaps FROM documents WHERE in_force_from IS NULL"
    ).fetchall()

    count = 0
    for row in rows:
        if row["issue_date"] is None:
            continue
        gaps = json.loads(row["metadata_gaps"]) if row["metadata_gaps"] else []
        gaps.append("in_force_from: no explicit effective date found; issue_date used as proxy")
        conn.execute(
            "UPDATE documents SET in_force_from = ?, metadata_gaps = ? WHERE doc_id = ?",
            (row["issue_date"], json.dumps(gaps), row["doc_id"]),
        )
        count += 1
    conn.commit()
    return count


def _step6_detect_and_record_cycles(conn: sqlite3.Connection) -> int:
    edges = build_edges_from_citations(conn)
    cycles = detect_cycles(edges)
    now = datetime.now(timezone.utc).isoformat()

    for cycle in cycles:
        for doc_id in set(cycle):
            conn.execute(
                "UPDATE documents SET status = 'unknown', superseded_by = NULL WHERE doc_id = ?",
                (doc_id,),
            )
        conn.execute(
            """
            INSERT INTO temporal_issues (issue_type, detail, doc_ids_json, detected_at)
            VALUES ('supersession_cycle', ?, ?, ?)
            """,
            (f"cycle among {len(set(cycle))} documents", json.dumps(list(set(cycle))), now),
        )
    conn.commit()
    return len(cycles)


def resolve(conn: sqlite3.Connection) -> ResolutionSummary:
    """The 6-step algorithm from 06-TEMPORAL-VALIDITY-SPEC.md. Re-runnable at
    any time. Step 5 (do not promote unsuperseded documents to in_force) is
    enforced by omission: no step here ever sets status='in_force' — that
    only happens at ingest time for sources with a positive Active listing
    (RBI has none; SEBI's Active crawl already sets it in sources/sebi.py).
    A document that reaches this resolver with status='unknown' and no
    supersession evidence stays 'unknown'."""
    withdrawn = _step1_withdrawal_listings(conn)
    superseded = _step2_and_3_citation_and_consolidation_edges(conn)
    in_force_from_defaulted = _step4_in_force_from_fallback(conn)
    cycles = _step6_detect_and_record_cycles(conn)

    return ResolutionSummary(
        withdrawn_from_listings=withdrawn,
        superseded_from_citations=superseded,
        in_force_from_defaulted=in_force_from_defaulted,
        cycles_detected=cycles,
    )
