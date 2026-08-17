"""Empirical Evaluator for real Arm A6 (RAFT) vs Arm A2 (Base SLM + RAG) execution runs.

Parses actual generation logs (run_A6.json and run_A2.json) and calculates:
  - Real Citation Precision (excluding uncited fallback inflation)
  - Citation Coverage (% of responses providing citations)
  - Temporal Accuracy on C3 questions
  - True/False Abstention Rates on C5/C6 questions
  - Empirical Forgetting Loss on General QA benchmarks
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, List

# Load .env from project root so GROQ_API_KEY is available for judge calls
_env_path = Path(__file__).parents[5] / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path, override=False)
    except ImportError:
        # Manual fallback: parse key=value lines
        with open(_env_path, encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _, _v = _line.partition("=")
                    if not os.environ.get(_k.strip()):
                        os.environ[_k.strip()] = _v.strip()

p3_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
p2_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "Phase 2", "src"))
for p in [p3_src, p2_src]:
    if p not in sys.path:
        sys.path.insert(0, p)

from finreg3.eval.citation_precision import CitationEvaluationResult, compute_aggregate_citation_metrics

logger = logging.getLogger(__name__)


def evaluate_run_file(run_json_path: Path) -> Dict[str, Any]:
    """Computes comprehensive empirical metrics from a raw run JSON file."""
    if not run_json_path.exists():
        raise FileNotFoundError(f"Run file not found: {run_json_path}")

    with open(run_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data.get("results", data)
    total_records = len(records)

    citation_evals = []
    c3_records = []
    c5_c6_records = []

    for r in records:
        qid = r.get("qid", "")
        cat = r.get("category", "")

        # Per-record citation_precision/valid_citations_count/citations were already
        # computed at generation time (runner_a6.py / runner_a2.py) against the real
        # retrieved chunks available then. Reuse them rather than re-deriving from
        # raw text, since the raw run JSON does not persist retrieved_chunks.
        total_citations = len(r.get("citations", []))
        valid_citations = r.get("valid_citations_count", 0)
        precision = r.get("citation_precision", 0.0)
        c_eval = CitationEvaluationResult(
            qid=qid,
            total_citations_found=total_citations,
            valid_citations=valid_citations,
            invalid_citations=total_citations - valid_citations,
            precision=precision,
            cited_doc_ids=[],
            retrieved_doc_ids=[],
        )
        citation_evals.append(c_eval)

        if cat == "C3":
            c3_records.append(r)
        elif cat in ["C5", "C6"]:
            c5_c6_records.append(r)

    cit_metrics = compute_aggregate_citation_metrics(citation_evals)

    # Temporal Accuracy on C3
    c3_correct = sum(1 for r in c3_records if r.get("correct_temporal_version", False))
    c3_accuracy = (c3_correct / len(c3_records)) if c3_records else 0.0

    # Overall Temporal Accuracy across all queries
    overall_temp_correct = sum(1 for r in records if r.get("correct_temporal_version", False))
    overall_temp_accuracy = overall_temp_correct / max(total_records, 1)

    # Abstention on C5/C6
    c5_c6_abstained = sum(1 for r in c5_c6_records if r.get("abstained", False))
    c5_c6_abstention_rate = (c5_c6_abstained / len(c5_c6_records)) if c5_c6_records else 0.0

    total_abstained = sum(1 for r in records if r.get("abstained", False))
    overall_abstention_rate = total_abstained / max(total_records, 1)

    return {
        "total_records": total_records,
        "citation_coverage": cit_metrics["citation_coverage"],
        "precision_on_cited": cit_metrics["precision_on_cited"],
        "strict_precision": cit_metrics["strict_precision"],
        "c3_temporal_accuracy": c3_accuracy,
        "overall_temporal_accuracy": overall_temp_accuracy,
        "c5_c6_abstention_rate": c5_c6_abstention_rate,
        "overall_abstention_rate": overall_abstention_rate,
    }


def compute_empirical_forgetting_loss(merged_model_dir: Path, n_per_task: int = 50) -> float:
    """Evaluates base Qwen2.5-1.5B vs merged RAFT model on an ARC-Challenge/HellaSwag subset (see capability_probe.py)."""
    from finreg3.eval.capability_probe import run_capability_delta

    result = run_capability_delta(merged_model_dir, n_per_task=n_per_task)
    return result["mean_capability_loss_pts"]


def compute_mean_judge_score(run_json_path: Path, bench_path: Path) -> float:
    """Scores every record in a run file against its gold answer using the real LLM judge
    (Phase 2's LLMJudge, Groq-backed), returning the mean 0-2 score normalized to 0-1."""
    from finreg.eval.judge import LLMJudge
    from finreg.bench.validator import validate_benchmark_file

    _, bench_records = validate_benchmark_file(bench_path, db_path=None, enforce_target_counts=False)
    question_by_qid = {r.qid: r.question for r in bench_records}

    with open(run_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    records = data.get("results", data)

    judge = LLMJudge()
    scores = []
    for r in records:
        question = question_by_qid.get(r.get("qid", ""), "")
        result = judge.evaluate_candidate_answer(
            question=question,
            gold_answer=r.get("gold_answer", ""),
            candidate_answer=r.get("raw_generation", ""),
        )
        scores.append(result["score"])

    return (sum(scores) / len(scores)) / 2.0 if scores else 0.0
