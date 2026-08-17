"""Programmatic citation precision, temporal accuracy, and abstention metrics (T-212, T-213, T-214).

These are the core behavioral metrics used to evaluate RAFT effectiveness:
  1. Citation Precision (T-212): Fraction of inline citations in model response that match retrieved context chunks.
  2. Temporal Accuracy (T-213): Fraction of temporal C3 questions where model applies the correct active provision.
  3. Abstention Quality (T-214): 2x2 confusion matrix evaluating true/false abstentions vs. true/false answers.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Set, Tuple, Optional

logger = logging.getLogger(__name__)

# Citation pattern: [doc_id / provision_path] or [doc_id]
CITATION_PATTERN = re.compile(r'[\[\(]\s*([a-zA-Z0-9_\-\.:]+)(?:\s*/\s*([^\]\)]+))?[\]\)]')


@dataclass
class CitationEvaluationResult:
    qid: str
    total_citations_found: int
    valid_citations: int
    invalid_citations: int
    precision: float
    cited_doc_ids: List[str]
    retrieved_doc_ids: List[str]


def evaluate_citation_precision(
    model_response: str,
    retrieved_chunks: List[Any],
    qid: str = "",
) -> CitationEvaluationResult:
    """Evaluate citation precision for a single model response (T-212).

    A citation is valid if its doc_id appears in the retrieved_chunks provided to the model.
    """
    matches = CITATION_PATTERN.findall(model_response)
    
    # Filter out system header tags like [REGULATOR: RBI ...] if any got caught
    valid_matches = []
    for doc_id, prov in matches:
        if doc_id.upper() in ["REGULATOR", "DOC", "TITLE", "DATE", "PROVISION", "UNCERTAIN_VALIDITY"]:
            continue
        valid_matches.append((doc_id, prov))

    retrieved_doc_ids = set()
    for chunk in retrieved_chunks:
        c_obj = chunk[0] if isinstance(chunk, (list, tuple)) else chunk
        if isinstance(c_obj, dict):
            d_id = c_obj.get("doc_id", "")
        else:
            d_id = getattr(c_obj, "doc_id", "")
        if d_id:
            retrieved_doc_ids.add(d_id)

    total = len(valid_matches)
    valid_count = 0
    cited_docs = []

    for doc_id, prov in valid_matches:
        cited_docs.append(doc_id)
        if doc_id in retrieved_doc_ids:
            valid_count += 1

    # Fix metric bug: if total == 0 (no citations present), precision is 0.0, not 1.0!
    precision = (valid_count / total) if total > 0 else 0.0

    return CitationEvaluationResult(
        qid=qid,
        total_citations_found=total,
        valid_citations=valid_count,
        invalid_citations=total - valid_count,
        precision=precision,
        cited_doc_ids=cited_docs,
        retrieved_doc_ids=list(retrieved_doc_ids),
    )


def compute_aggregate_citation_metrics(eval_results: List[CitationEvaluationResult]) -> Dict[str, float]:
    """Computes transparent dual metrics across a suite of evaluation results."""
    if not eval_results:
        return {"citation_coverage": 0.0, "precision_on_cited": 0.0, "strict_precision": 0.0}

    total_queries = len(eval_results)
    queries_with_citations = [r for r in eval_results if r.total_citations_found > 0]
    coverage = len(queries_with_citations) / total_queries

    precision_on_cited = (
        sum(r.precision for r in queries_with_citations) / len(queries_with_citations)
        if queries_with_citations else 0.0
    )

    total_valid = sum(r.valid_citations for r in eval_results)
    total_found = sum(r.total_citations_found for r in eval_results)
    strict_precision = (total_valid / total_found) if total_found > 0 else 0.0

    return {
        "citation_coverage": coverage,
        "precision_on_cited": precision_on_cited,
        "strict_precision": strict_precision,
    }


@dataclass
class AbstentionEvaluationResult:
    qid: str
    is_abstained: bool
    is_context_sufficient: bool
    classification: str  # "True Abstention", "False Abstention", "True Answer", "False Answer"


def evaluate_abstention_quality(
    raw_response: str,
    is_context_sufficient: bool,
    qid: str = "",
) -> AbstentionEvaluationResult:
    """Evaluate abstention quality into a 2x2 confusion matrix (T-214)."""
    is_abstained = raw_response.strip().startswith("INSUFFICIENT_CORPUS_EVIDENCE:")

    if is_abstained and not is_context_sufficient:
        classification = "True Abstention"
    elif is_abstained and is_context_sufficient:
        classification = "False Abstention"
    elif not is_abstained and is_context_sufficient:
        classification = "True Answer"
    else:
        classification = "False Answer"

    return AbstentionEvaluationResult(
        qid=qid,
        is_abstained=is_abstained,
        is_context_sufficient=is_context_sufficient,
        classification=classification,
    )


@dataclass
class TemporalAccuracyResult:
    qid: str
    is_temporal_question: bool
    correct_active_version_cited: bool
    cited_stale_version: bool


def evaluate_temporal_accuracy(
    model_response: str,
    gold_citations: List[Dict[str, str]],
    excluded_chunks: List[Any],
    qid: str = "",
) -> TemporalAccuracyResult:
    """Evaluate whether model cites active vs superseded/withdrawn provisions (T-213)."""
    matches = CITATION_PATTERN.findall(model_response)
    cited_doc_ids = {m[0] for m in matches if m[0] not in ["REGULATOR", "DOC", "TITLE", "DATE", "PROVISION"]}

    gold_doc_ids = {c.get("doc_id", "") for c in gold_citations}
    excluded_doc_ids = {
        getattr(chunk[0] if isinstance(chunk, (list, tuple)) else chunk, "doc_id", "")
        for chunk in excluded_chunks
    }

    correct_active = bool(cited_doc_ids.intersection(gold_doc_ids))
    cited_stale = bool(cited_doc_ids.intersection(excluded_doc_ids))

    return TemporalAccuracyResult(
        qid=qid,
        is_temporal_question=True,
        correct_active_version_cited=correct_active,
        cited_stale_version=cited_stale,
    )
