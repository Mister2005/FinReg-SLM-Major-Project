"""Cross-encoder reranker for top-50 fused candidates (T-111)."""

import time
from typing import List, Tuple
from finreg.retrieve.chunker import RegulatoryChunk

try:
    from sentence_transformers import CrossEncoder
    HAS_CROSS_ENCODER = True
except ImportError:
    HAS_CROSS_ENCODER = False


class CrossEncoderReranker:
    """Reranks candidates using a CrossEncoder model."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", enabled: bool = True):
        self.model_name = model_name
        self.enabled = enabled
        self.model = None
        self.last_latency_ms: float = 0.0

    def load_model(self):
        if self.enabled and HAS_CROSS_ENCODER and self.model is None:
            self.model = CrossEncoder(self.model_name)

    def rerank(
        self,
        query: str,
        candidates: List[Tuple[RegulatoryChunk, float]],
        top_k: int = 8
    ) -> List[Tuple[RegulatoryChunk, float]]:
        """Reranks candidates and returns top_k."""
        start_time = time.perf_counter()

        if not self.enabled or not HAS_CROSS_ENCODER or not candidates:
            self.last_latency_ms = (time.perf_counter() - start_time) * 1000
            return candidates[:top_k]

        self.load_model()

        # Prepare (query, passage) pairs
        pairs = [(query, chunk.embedded_text) for chunk, _ in candidates]
        scores = self.model.predict(pairs)

        reranked = []
        for idx, (chunk, _) in enumerate(candidates):
            reranked.append((chunk, float(scores[idx])))

        reranked.sort(key=lambda x: x[1], reverse=True)
        self.last_latency_ms = (time.perf_counter() - start_time) * 1000

        return reranked[:top_k]
