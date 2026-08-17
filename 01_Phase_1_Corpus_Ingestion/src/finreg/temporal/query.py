from __future__ import annotations

import sqlite3
from datetime import date


def in_force_as_of(
    conn: sqlite3.Connection, as_of: date, regulator: str | None = None
) -> tuple[list[str], list[str]]:
    """Returns (in_force_doc_ids, unknown_doc_ids) as separate lists — never
    merged. A caller that treats 'unknown' as 'in force' is making its own
    choice under uncertainty; the corpus never makes it for them."""
    as_of_iso = as_of.isoformat()

    base_query = """
        SELECT doc_id, status FROM v_in_force_as_of
        WHERE status != 'withdrawn'
        AND in_force_from IS NOT NULL AND in_force_from <= ?
        AND (in_force_to IS NULL OR in_force_to > ?)
    """
    params: list[object] = [as_of_iso, as_of_iso]
    if regulator is not None:
        base_query += " AND regulator = ?"
        params.append(regulator)

    rows = conn.execute(base_query, params).fetchall()

    in_force_ids = [r["doc_id"] for r in rows if r["status"] == "in_force"]
    unknown_ids = [r["doc_id"] for r in rows if r["status"] == "unknown"]

    return in_force_ids, unknown_ids
