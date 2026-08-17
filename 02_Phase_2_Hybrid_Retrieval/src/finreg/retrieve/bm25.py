"""BM25 Lexical Index for statutory provisions and references (T-109)."""

import re
from typing import List, Tuple
from rank_bm25 import BM25Okapi
from finreg.retrieve.chunker import RegulatoryChunk


def tokenize_text(text: str) -> List[str]:
    """Tokenizes text preserving section numbers, hyphens, underscores, and colons in doc_ids."""
    return re.findall(r'\b[a-zA-Z0-9\-\._:]+\b', text.lower())



class BM25LexicalIndex:
    """BM25 lexical index over regulatory chunks."""

    def __init__(self):
        self.chunks: List[RegulatoryChunk] = []
        self.bm25: BM25Okapi = None

    def build_index(self, chunks: List[RegulatoryChunk]):
        """Tokenizes chunk embedded_texts and builds BM25 index."""
        self.chunks = chunks
        corpus_tokens = [tokenize_text(c.embedded_text) for c in chunks]
        self.bm25 = BM25Okapi(corpus_tokens)

    def search(self, query: str, top_k: int = 50) -> List[Tuple[RegulatoryChunk, float]]:
        """Queries BM25 index and returns top_k (chunk, score) tuples."""
        if self.bm25 is None or not self.chunks:
            return []

        q_tokens = tokenize_text(query)
        if not q_tokens:
            return []

        scores = self.bm25.get_scores(q_tokens)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        results = []
        for idx in top_indices:
            results.append((self.chunks[idx], float(scores[idx])))
        return results
