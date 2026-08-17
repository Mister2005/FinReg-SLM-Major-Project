"""Validator for C3 as-of-date stem pairs and variants (T-104)."""

from typing import List, Dict, Set, Tuple
from finreg.bench.schema import BenchmarkQuestionRecord


class C3StemValidationResult:
    def __init__(self):
        self.total_c3_records: int = 0
        self.total_stems: int = 0
        self.valid_stems: int = 0
        self.defective_qids: List[str] = []
        self.errors: List[str] = []
        self.warnings: List[str] = []

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


def validate_c3_stems(records: List[BenchmarkQuestionRecord]) -> C3StemValidationResult:
    """Validates that C3 questions occur in stem groups with >= 2 dated variants having distinct citations/answers."""
    result = C3StemValidationResult()
    c3_records = [r for r in records if r.category == "C3"]
    result.total_c3_records = len(c3_records)

    stems: Dict[str, List[BenchmarkQuestionRecord]] = {}
    for rec in c3_records:
        if not rec.stem_id:
            result.errors.append(f"C3 Question '{rec.qid}' is missing stem_id.")
            result.defective_qids.append(rec.qid)
            continue
        stems.setdefault(rec.stem_id, []).append(rec)

    result.total_stems = len(stems)

    for stem_id, variants in stems.items():
        if len(variants) < 2:
            result.errors.append(
                f"Stem '{stem_id}' has only {len(variants)} variant ({variants[0].qid}). C3 stems require >= 2 variants."
            )
            for v in variants:
                result.defective_qids.append(v.qid)
            continue

        # Check dates differ
        dates = [str(v.as_of_date) for v in variants]
        if len(set(dates)) < len(variants):
            result.warnings.append(
                f"Stem '{stem_id}' variants have duplicate as_of_dates: {dates}"
            )

        # Check gold citations or answers differ across dates
        citations_per_variant: List[Set[str]] = []
        for v in variants:
            cset = {f"{c.doc_id}:{c.locator}" for c in v.gold_citations}
            citations_per_variant.append(cset)

        # Ensure not all variants have identical gold citations
        first_cset = citations_per_variant[0]
        all_identical = all(cset == first_cset for cset in citations_per_variant[1:])
        if all_identical:
            result.errors.append(
                f"Stem '{stem_id}' variants ({[v.qid for v in variants]}) have identical gold citations. Date is not decisive."
            )
            for v in variants:
                result.defective_qids.append(v.qid)
        else:
            result.valid_stems += 1

    return result
