"""Reciprocal Rank Fusion (RRF) for combining dense and lexical search (T-110)."""

from typing import List, Tuple, Dict
from finreg.retrieve.chunker import RegulatoryChunk


def reciprocal_rank_fusion(
    dense_results: List[Tuple[RegulatoryChunk, float]],
    lexical_results: List[Tuple[RegulatoryChunk, float]],
    k: int = 60,
    top_n: int = 50
) -> List[Tuple[RegulatoryChunk, float]]:
    """
    Fuses dense and lexical search results using Reciprocal Rank Fusion.
    Score = 1 / (k + rank_dense) + 1 / (k + rank_lexical)
    """
    scores: Dict[str, float] = {}
    chunk_map: Dict[str, RegulatoryChunk] = {}

    # Process dense ranks
    for rank, (chunk, _score) in enumerate(dense_results, start=1):
        cid = chunk.chunk_id
        chunk_map[cid] = chunk
        scores[cid] = scores.get(cid, 0.0) + (1.0 / (k + rank))

    # Process lexical ranks
    for rank, (chunk, _score) in enumerate(lexical_results, start=1):
        cid = chunk.chunk_id
        chunk_map[cid] = chunk
        scores[cid] = scores.get(cid, 0.0) + (1.0 / (k + rank))

    # Sort candidates by fused score
    sorted_candidates = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]

    fused_results = []
    for cid, score in sorted_candidates:
        fused_results.append((chunk_map[cid], score))

    return fused_results
