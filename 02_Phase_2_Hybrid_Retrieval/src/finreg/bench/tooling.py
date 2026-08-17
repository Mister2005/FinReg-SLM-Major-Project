"""Authoring worksheet tooling for benchmark questions (T-102)."""

import json
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any
from finreg.bench.schema import BenchmarkQuestionRecord, GoldCitation, CategoryType, RegulatorType


def scaffold_benchmark_question(
    db_path: Path,
    doc_id: str,
    category: CategoryType = "C1",
    qid: Optional[str] = None,
    locator: str = "para 1",
    author: str = "annotator-1"
) -> Dict[str, Any]:
    """Scaffolds a new BenchmarkQuestionRecord template pre-filled with corpus metadata."""
    if not db_path.exists():
        raise FileNotFoundError(f"Manifest DB not found at {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT doc_id, regulator, title, issue_date, statutory_regime FROM documents WHERE doc_id = ?",
        (doc_id,)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"doc_id '{doc_id}' not found in manifest.db")

    doc_id_val, regulator_val, title, issue_date, statutory_regime = row

    # Query text body sample if available
    cursor.execute("SELECT body FROM texts WHERE doc_id = ? LIMIT 1", (doc_id,))
    text_row = cursor.fetchone()
    body_snippet = (text_row[0][:300] + "...") if text_row and text_row[0] else ""

    conn.close()

    regulator_clean: RegulatorType = "RBI"
    reg_upper = (regulator_val or "").upper()
    if "SEBI" in reg_upper:
        regulator_clean = "SEBI"
    elif "TAX" in reg_upper or "IT" in reg_upper:
        regulator_clean = "Income-tax"
    elif "GST" in reg_upper:
        regulator_clean = "GST"
    elif "DPDP" in reg_upper:
        regulator_clean = "DPDP"

    if not qid:
        qid = f"{category}-{regulator_clean}-001"

    template = {
        "qid": qid,
        "category": category,
        "regulator": regulator_clean,
        "question": f"[Question based on {title or doc_id}]",
        "as_of_date": issue_date or "2026-06-01",
        "stem_id": f"{qid}-stem" if category == "C3" else None,
        "gold_answer": f"[Gold answer text based on {locator}]",
        "gold_citations": [{"doc_id": doc_id_val, "locator": locator}],
        "answerable": category != "C6",
        "false_premise": category == "C5",
        "computation": {"expected_value": None, "tolerance": None},
        "difficulty": "medium",
        "author": author,
        "verified_by": None,
        "verification_date": None,
        "notes": f"Source document: {title}. Snippet: {body_snippet}"
    }

    return template
