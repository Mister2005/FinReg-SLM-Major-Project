from __future__ import annotations

import re
import sqlite3
from datetime import date

_ITA_2026_04_01 = date(2026, 4, 1)
_ITA_1961_PATTERN = re.compile(r"Income-tax Act,?\s*1961", re.IGNORECASE)
_ITA_2025_PATTERN = re.compile(r"Income-tax Act,?\s*2025", re.IGNORECASE)


def _cited_acts(conn: sqlite3.Connection, doc_id: str) -> tuple[bool, bool]:
    """(cites_1961, cites_2025), detected via citation extraction's
    target_act field per doc 06 — never by date alone."""
    rows = conn.execute(
        "SELECT target_act FROM citations WHERE doc_id = ? AND target_act IS NOT NULL",
        (doc_id,),
    ).fetchall()
    cites_1961 = any(_ITA_1961_PATTERN.search(r["target_act"]) for r in rows)
    cites_2025 = any(_ITA_2025_PATTERN.search(r["target_act"]) for r in rows)
    return cites_1961, cites_2025


def determine_regime(issue_date: date | None, cites_1961: bool, cites_2025: bool) -> str | None:
    if cites_1961 and cites_2025:
        return "both"
    if issue_date is None:
        return "ITA_2025" if cites_2025 else ("ITA_1961" if cites_1961 else None)
    if issue_date < _ITA_2026_04_01 and not cites_2025:
        return "ITA_1961"
    if issue_date >= _ITA_2026_04_01 and not cites_1961:
        return "ITA_2025"
    return "ITA_1961" if cites_1961 else ("ITA_2025" if cites_2025 else None)


def tag_direct_tax_documents(conn: sqlite3.Connection, regulator: str = "cbdt") -> int:
    """Tags statutory_regime for every document of the given regulator (CBDT
    by default — 'every direct-tax document', per doc 06). Non-direct-tax
    documents are never touched and keep statutory_regime = NULL."""
    rows = conn.execute(
        "SELECT doc_id, issue_date FROM documents WHERE regulator = ?", (regulator,)
    ).fetchall()

    count = 0
    for row in rows:
        cites_1961, cites_2025 = _cited_acts(conn, row["doc_id"])
        issue_date = date.fromisoformat(row["issue_date"]) if row["issue_date"] else None
        regime = determine_regime(issue_date, cites_1961, cites_2025)
        conn.execute(
            "UPDATE documents SET statutory_regime = ? WHERE doc_id = ?",
            (regime, row["doc_id"]),
        )
        count += 1
    conn.commit()
    return count
