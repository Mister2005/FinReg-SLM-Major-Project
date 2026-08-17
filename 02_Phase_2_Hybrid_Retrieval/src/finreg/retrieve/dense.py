"""Dense vector index and embedding engine (T-108)."""

import json
import numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from finreg.retrieve.chunker import RegulatoryChunk

try:
    from sentence_transformers import SentenceTransformer
    HAS_ST = True
except ImportError:
    HAS_ST = False


class DenseVectorIndex:
    """Dense vector index using SentenceTransformers and cosine similarity."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.model_name = model_name
        self.model = None
        self.chunks: List[RegulatoryChunk] = []
        self.embeddings: Optional[np.ndarray] = None

    def load_model(self, device: str = "cpu"):
        if not HAS_ST:
            raise ImportError("sentence-transformers is required for DenseVectorIndex.")
        if self.model is None:
            self.model = SentenceTransformer(self.model_name, device=device)

    def build_index(self, chunks: List[RegulatoryChunk], batch_size: int = 32):
        """Encodes chunk embedded_text and builds numpy vector index."""
        self.load_model()
        self.chunks = chunks
        texts = [c.embedded_text for c in chunks]
        if not texts:
            self.embeddings = np.empty((0, 384), dtype=np.float32)
            return

        emb_matrix = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True
        )
        self.embeddings = np.asarray(emb_matrix, dtype=np.float32)

    def search(self, query: str, top_k: int = 50) -> List[Tuple[RegulatoryChunk, float]]:
        """Queries index and returns top_k (chunk, similarity_score) tuples."""
        if self.embeddings is None or len(self.chunks) == 0:
            return []

        self.load_model()
        q_emb = self.model.encode([query], normalize_embeddings=True)[0]
        scores = np.dot(self.embeddings, q_emb)

        top_indices = np.argsort(scores)[::-1][:top_k]
        results = []
        for idx in top_indices:
            results.append((self.chunks[idx], float(scores[idx])))
        return results

    def save(self, index_dir: Path):
        """Saves index artifacts (embeddings numpy array + chunk metadata json)."""
        index_dir.mkdir(parents=True, exist_ok=True)
        if self.embeddings is not None:
            np.save(index_dir / "dense_embeddings.npy", self.embeddings)

        metadata = []
        for c in self.chunks:
            metadata.append({
                "chunk_id": c.chunk_id,
                "doc_id": c.doc_id,
                "provision_path": c.provision_path,
                "header_prefix": c.header_prefix,
                "content": c.content,
                "embedded_text": c.embedded_text,
                "in_force_from": c.in_force_from,
                "in_force_to": c.in_force_to,
                "status": c.status,
                "statutory_regime": c.statutory_regime,
                "regulator": c.regulator,
                "is_table": c.is_table,
            })
        with open(index_dir / "dense_chunks.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    def load(self, index_dir: Path):
        """Loads index artifacts from disk."""
        emb_path = index_dir / "dense_embeddings.npy"
        json_path = index_dir / "dense_chunks.json"

        if emb_path.exists():
            self.embeddings = np.load(emb_path)

        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            self.chunks = [
                RegulatoryChunk(
                    chunk_id=m["chunk_id"],
                    doc_id=m["doc_id"],
                    provision_path=m["provision_path"],
                    header_prefix=m["header_prefix"],
                    content=m["content"],
                    embedded_text=m["embedded_text"],
                    in_force_from=m.get("in_force_from"),
                    in_force_to=m.get("in_force_to"),
                    status=m.get("status", "unknown"),
                    statutory_regime=m.get("statutory_regime"),
                    regulator=m.get("regulator", "RBI"),
                    is_table=m.get("is_table", False),
                )
                for m in meta
            ]
