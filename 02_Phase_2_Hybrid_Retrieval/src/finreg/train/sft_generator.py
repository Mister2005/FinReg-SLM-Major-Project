"""Synthetic SFT QA pair generator with benchmark exclusion enforcement (T-117, Invariant E7)."""

import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Set
from finreg.bench.freeze import assert_sft_exclusion_safety


class SFTDataGenerator:
    """Generates SFT instruction tuning dataset while guaranteeing zero overlap with benchmark gold citations."""

    def __init__(self, db_path: Path, exclusion_file: Path):
        self.db_path = db_path
        self.exclusion_file = exclusion_file

        if not self.exclusion_file.exists():
            raise FileNotFoundError(
                f"SFT Generation refused: '{self.exclusion_file}' does not exist. Benchmark must be frozen first!"
            )

        with open(self.exclusion_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.excluded_doc_ids: Set[str] = set(data.get("excluded_doc_ids", []))

    def generate_sft_pairs(self, target_count: int = 6000) -> List[Dict[str, Any]]:
        """Generates instruction tuning pairs from non-excluded corpus documents."""
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT doc_id, regulator, title, issue_date FROM documents WHERE doc_id IS NOT NULL")
        rows = cursor.fetchall()

        eligible_docs = [r for r in rows if r[0] not in self.excluded_doc_ids]
        conn.close()

        sft_doc_ids = {r[0] for r in eligible_docs}
        # Enforce Invariant E7 check
        assert_sft_exclusion_safety(sft_doc_ids, self.exclusion_file)

        pairs = []
        for idx in range(target_count):
            doc = eligible_docs[idx % len(eligible_docs)]
            doc_id, reg, title, issue_date = doc

            pair = {
                "id": f"sft-{idx+1:05d}",
                "doc_id": doc_id,
                "as_of_date": issue_date or "2026-06-01",
                "instruction": f"What compliance rules apply under {title or doc_id}?",
                "context": f"[REGULATOR: {reg or 'RBI'} | DOC: {doc_id} | TITLE: {title}]\nCompliance rules apply under this provision.",
                "response": f"Under [{doc_id} / para 1], regulated entities must adhere to statutory compliance norms.",
            }
            pairs.append(pair)

        return pairs
