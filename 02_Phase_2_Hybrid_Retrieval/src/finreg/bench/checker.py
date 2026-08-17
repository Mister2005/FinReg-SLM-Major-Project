"""Citation support checker for verifying gold citation text in Phase 1 corpus (T-103)."""

import sqlite3
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
from finreg.bench.schema import BenchmarkQuestionRecord


class CitationCheckResult:
    def __init__(self, qid: str):
        self.qid: str = qid
        self.doc_id: str = ""
        self.locator: str = ""
        self.doc_found: bool = False
        self.text_found: bool = False
        self.support_score: float = 0.0
        self.flagged: bool = False
        self.reason: str = ""


def check_citation_support(
    record: BenchmarkQuestionRecord,
    db_path: Path
) -> List[CitationCheckResult]:
    """Checks whether the cited doc_id text in Phase 1 database contains text supporting the gold answer."""
    results = []

    if not db_path.exists():
        res = CitationCheckResult(record.qid)
        res.flagged = True
        res.reason = f"Database file not found: {db_path}"
        return [res]

    if not record.gold_citations:
        if record.answerable and record.category != "C6":
            res = CitationCheckResult(record.qid)
            res.flagged = True
            res.reason = "Answerable question missing gold citations."
            return [res]
        return []

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Extract keywords from gold answer (ignoring short stopwords)
    answer_words = set(re.findall(r'\b[a-zA-Z0-9]{4,}\b', record.gold_answer.lower()))

    for citation in record.gold_citations:
        res = CitationCheckResult(record.qid)
        res.doc_id = citation.doc_id
        res.locator = citation.locator

        # 1. Check document presence
        cursor.execute("SELECT title FROM documents WHERE doc_id = ?", (citation.doc_id,))
        doc_row = cursor.fetchone()
        if not doc_row:
            res.doc_found = False
            res.flagged = True
            res.reason = f"doc_id '{citation.doc_id}' not found in documents table"
            results.append(res)
            continue
        res.doc_found = True

        # 2. Check text body
        cursor.execute("SELECT body FROM texts WHERE doc_id = ?", (citation.doc_id,))
        text_rows = cursor.fetchall()
        if not text_rows or not any(r[0] for r in text_rows):
            res.text_found = False
            res.flagged = True
            res.reason = f"No text body extracted for doc_id '{citation.doc_id}'"
            results.append(res)
            continue
        res.text_found = True

        full_text = " ".join(r[0] for r in text_rows if r[0]).lower()

        # Compute keyword overlap score
        if answer_words:
            matched_words = [w for w in answer_words if w in full_text]
            res.support_score = len(matched_words) / len(answer_words)
        else:
            res.support_score = 1.0

        if res.support_score < 0.20:
            res.flagged = True
            res.reason = f"Low keyword overlap ({res.support_score:.2%}) between gold answer and text of doc '{citation.doc_id}'"

        results.append(res)

    conn.close()
    return results


def check_all_citations(
    records: List[BenchmarkQuestionRecord],
    db_path: Path
) -> Dict[str, Any]:
    """Runs citation check across all benchmark records."""
    all_results: List[CitationCheckResult] = []
    flagged_qids: Set[str] = set()

    for rec in records:
        rec_results = check_citation_support(rec, db_path)
        all_results.extend(rec_results)
        if any(r.flagged for r in rec_results):
            flagged_qids.add(rec.qid)

    return {
        "total_questions_checked": len(records),
        "total_citations_checked": len(all_results),
        "flagged_questions_count": len(flagged_qids),
        "flagged_qids": sorted(list(flagged_qids)),
        "detailed_results": all_results,
    }
