"""Retrieval quality metrics evaluator: Recall@k, MRR, temporal precision (T-114)."""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Set
from finreg.bench.schema import BenchmarkQuestionRecord
from finreg.retrieve.chunker import RegulatoryChunk
from finreg.retrieve.temporal import parse_date


@dataclass
class RetrievalMetricsResult:
    total_questions: int
    recall_at_5: float
    recall_at_8: float
    recall_at_20: float
    mrr: float
    temporal_precision: float
    passes_gate_p3: bool  # Recall@8 >= 0.70


def evaluate_retrieval_quality(
    records: List[BenchmarkQuestionRecord],
    retrieved_results: Dict[str, List[Tuple[RegulatoryChunk, float]]]
) -> RetrievalMetricsResult:
    """
    Evaluates retrieval quality metrics across benchmark questions.
    retrieved_results maps qid -> list of (chunk, score) tuples.
    """
    recall_5_list = []
    recall_8_list = []
    recall_20_list = []
    mrr_list = []
    temporal_precision_list = []

    for rec in records:
        if not rec.gold_citations or not rec.answerable or rec.category == "C6":
            continue

        gold_doc_ids = {c.doc_id for c in rec.gold_citations if c.doc_id}
        if not gold_doc_ids:
            continue

        chunks = [item[0] for item in retrieved_results.get(rec.qid, [])]

        # Calculate Recall@k
        def compute_recall_at_k(k_val: int) -> float:
            k_chunks = chunks[:k_val]
            k_doc_ids = {c.doc_id for c in k_chunks}
            matched = gold_doc_ids.intersection(k_doc_ids)
            return len(matched) / len(gold_doc_ids)

        recall_5_list.append(compute_recall_at_k(5))
        r8 = compute_recall_at_k(8)
        recall_8_list.append(r8)
        recall_20_list.append(compute_recall_at_k(20))

        # Calculate MRR
        first_rr = 0.0
        for rank, chunk in enumerate(chunks, start=1):
            if chunk.doc_id in gold_doc_ids:
                first_rr = 1.0 / rank
                break
        mrr_list.append(first_rr)

        # Calculate Temporal Precision on retrieved chunks
        q_date = parse_date(str(rec.as_of_date))
        if chunks and q_date:
            valid_count = 0
            for chunk in chunks[:8]:
                if chunk.status == "withdrawn":
                    continue
                f_date = parse_date(chunk.in_force_from)
                t_date = parse_date(chunk.in_force_to)
                is_from_ok = (f_date is None) or (f_date <= q_date)
                is_to_ok = (t_date is None) or (t_date > q_date)
                if is_from_ok and is_to_ok:
                    valid_count += 1
            temporal_precision_list.append(valid_count / min(len(chunks), 8))

    mean_r5 = float(np.mean(recall_5_list)) if recall_5_list else 0.0
    mean_r8 = float(np.mean(recall_8_list)) if recall_8_list else 0.0
    mean_r20 = float(np.mean(recall_20_list)) if recall_20_list else 0.0
    mean_mrr = float(np.mean(mrr_list)) if mrr_list else 0.0
    mean_temp_prec = float(np.mean(temporal_precision_list)) if temporal_precision_list else 0.0

    return RetrievalMetricsResult(
        total_questions=len(recall_8_list),
        recall_at_5=round(mean_r5, 4),
        recall_at_8=round(mean_r8, 4),
        recall_at_20=round(mean_r20, 4),
        mrr=round(mean_mrr, 4),
        temporal_precision=round(mean_temp_prec, 4),
        passes_gate_p3=mean_r8 >= 0.70
    )
