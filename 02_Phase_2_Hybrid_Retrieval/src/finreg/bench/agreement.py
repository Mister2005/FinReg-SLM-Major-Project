"""Annotation agreement tooling (T-105) computing Cohen's kappa for benchmark verification."""

import json
from pathlib import Path
from typing import List, Dict, Any, Tuple
from sklearn.metrics import cohen_kappa_score


def compute_binary_kappa(
    rater1_labels: List[int],
    rater2_labels: List[int]
) -> float:
    """Computes Cohen's kappa for binary judgements (e.g., answerable, false_premise)."""
    if len(rater1_labels) != len(rater2_labels):
        raise ValueError("Rater label arrays must have identical length.")
    return float(cohen_kappa_score(rater1_labels, rater2_labels))


def compute_correctness_kappa(
    rater1_scores: List[int],
    rater2_scores: List[int],
    weights: str = "quadratic"
) -> float:
    """Computes Cohen's kappa for 3-point correctness scale (0, 1, 2) with optional quadratic weights."""
    if len(rater1_scores) != len(rater2_scores):
        raise ValueError("Rater score arrays must have identical length.")
    return float(cohen_kappa_score(rater1_scores, rater2_scores, weights=weights))


def evaluate_annotation_agreement(
    overlap_records: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Evaluates agreement statistics across an overlap subsample of records.
    Each record in overlap_records must contain:
      - 'qid': str
      - 'rater1': {'answerable': bool, 'false_premise': bool, 'correctness': int (0..2)}
      - 'rater2': {'answerable': bool, 'false_premise': bool, 'correctness': int (0..2)}
    """
    r1_ans, r2_ans = [], []
    r1_fp, r2_fp = [], []
    r1_corr, r2_corr = [], []

    disagreements = []

    for item in overlap_records:
        qid = item["qid"]
        r1 = item["rater1"]
        r2 = item["rater2"]

        r1_ans.append(int(r1["answerable"]))
        r2_ans.append(int(r2["answerable"]))

        r1_fp.append(int(r1["false_premise"]))
        r2_fp.append(int(r2["false_premise"]))

        r1_corr.append(int(r1["correctness"]))
        r2_corr.append(int(r2["correctness"]))

        if (r1["answerable"] != r2["answerable"] or
            r1["false_premise"] != r2["false_premise"] or
            r1["correctness"] != r2["correctness"]):
            disagreements.append({
                "qid": qid,
                "rater1": r1,
                "rater2": r2,
            })

    kappa_answerable = compute_binary_kappa(r1_ans, r2_ans) if r1_ans else 0.0
    kappa_false_premise = compute_binary_kappa(r1_fp, r2_fp) if r1_fp else 0.0
    kappa_correctness = compute_correctness_kappa(r1_corr, r2_corr) if r1_corr else 0.0

    return {
        "sample_size": len(overlap_records),
        "kappa_answerable": round(kappa_answerable, 4),
        "kappa_false_premise": round(kappa_false_premise, 4),
        "kappa_correctness_weighted": round(kappa_correctness, 4),
        "disagreement_count": len(disagreements),
        "disagreements": disagreements,
        "meets_target_threshold": kappa_correctness >= 0.70,
    }
