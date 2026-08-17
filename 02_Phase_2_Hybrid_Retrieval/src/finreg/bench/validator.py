"""Validator for the FinReg-SLM Phase 2 Seed Benchmark (T-101)."""

import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Tuple, Set, Optional
from pydantic import ValidationError
from finreg.bench.schema import BenchmarkQuestionRecord

TARGET_CATEGORY_COUNTS = {
    "C1": 60,
    "C2": 50,
    "C3": 60,
    "C4": 40,
    "C5": 40,
    "C6": 50,
}

MIN_REGULATOR_COUNTS = {
    "RBI": 90,
    "SEBI": 70,
    "Income-tax": 70,
    "GST": 50,
    "DPDP": 20,
}


class BenchmarkValidationResult:
    def __init__(self):
        self.total_records: int = 0
        self.valid_records: int = 0
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.category_counts: Dict[str, int] = {}
        self.regulator_counts: Dict[str, int] = {}

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0 and self.valid_records == self.total_records


def validate_benchmark_file(
    benchmark_path: Path,
    db_path: Optional[Path] = None,
    enforce_target_counts: bool = True
) -> Tuple[BenchmarkValidationResult, List[BenchmarkQuestionRecord]]:
    """Validates benchmark json/jsonl file against schema, manifest db, and category/regulator targets."""
    result = BenchmarkValidationResult()
    records: List[BenchmarkQuestionRecord] = []

    if not benchmark_path.exists():
        result.errors.append(f"Benchmark file not found: {benchmark_path}")
        return result, records

    # Read records
    raw_records = []
    with open(benchmark_path, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if content.startswith("["):
            raw_records = json.loads(content)
        else:
            for line_no, line in enumerate(content.splitlines(), start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw_records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    result.errors.append(f"Line {line_no}: Invalid JSON - {e}")

    result.total_records = len(raw_records)

    # 1. Schema validation
    seen_qids: Set[str] = set()
    for idx, raw in enumerate(raw_records, start=1):
        try:
            rec = BenchmarkQuestionRecord.model_validate(raw)
            if rec.qid in seen_qids:
                result.errors.append(f"Record #{idx}: Duplicate qid '{rec.qid}'")
            seen_qids.add(rec.qid)

            records.append(rec)
            result.valid_records += 1
            result.category_counts[rec.category] = result.category_counts.get(rec.category, 0) + 1
            result.regulator_counts[rec.regulator] = result.regulator_counts.get(rec.regulator, 0) + 1
        except ValidationError as ve:
            result.errors.append(f"Record #{idx} ({raw.get('qid', 'UNKNOWN')}): {ve}")

    # 2. Database validation against Phase 1 manifest.db
    if db_path and db_path.exists():
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT doc_id FROM documents")
        valid_doc_ids = set(row[0] for row in cursor.fetchall())
        conn.close()

        for rec in records:
            for citation in rec.gold_citations:
                if citation.doc_id not in valid_doc_ids:
                    result.errors.append(
                        f"Question '{rec.qid}': Cited doc_id '{citation.doc_id}' not found in Phase 1 manifest.db"
                    )
    elif db_path:
        result.warnings.append(f"Database path provided does not exist: {db_path}")

    # 3. Category count enforcement
    if enforce_target_counts:
        if result.total_records != 300:
            result.warnings.append(f"Total benchmark record count is {result.total_records}, expected 300.")

        for cat, expected in TARGET_CATEGORY_COUNTS.items():
            actual = result.category_counts.get(cat, 0)
            if actual != expected:
                result.warnings.append(f"Category '{cat}' count is {actual}, target is {expected}.")

        for reg, min_expected in MIN_REGULATOR_COUNTS.items():
            actual = result.regulator_counts.get(reg, 0)
            if actual < min_expected:
                result.warnings.append(f"Regulator '{reg}' count is {actual}, minimum expected is {min_expected}.")

    return result, records
