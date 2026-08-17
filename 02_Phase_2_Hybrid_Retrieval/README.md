# 02. Phase 2 — Version-Aware Hybrid Retrieval Pipeline

### Overview
Phase 2 engineered the retrieval engine to overcome keyword mismatches on legal syntax and resolve temporal obsolescence.

### Key Components
* **Dense Vector Index**: BAAI/bge-small-en-v1.5 embeddings capturing high-level statutory semantics.
* **BM25 Lexical Index**: SQLite FTS5 / BM25 index matching exact alphanumeric circular numbers and Acts.
* **Reciprocal Rank Fusion (RRF)**: Merging dense and sparse rank lists with rank constant $k=60$.
* **Cross-Encoder Reranker**: `bge-reranker-base` filtering top-5 high-precision statutory passages.
* **Temporal Date Filter**: Restricts retrieval to circulars active as of query date (`as_of_date` >= `effective_date`).
