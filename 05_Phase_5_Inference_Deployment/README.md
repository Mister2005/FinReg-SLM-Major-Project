# 05. Phase 5 — On-Premises Inference Engine & Compliance UI

### Overview
Phase 5 built the production deployment pipeline for self-hosted execution in banking environments.

### Modules
* **`src/model_server.py`**: 4-bit NF4 quantized loader utilizing ~4.5 GB VRAM with fast streaming token generation.
* **`src/rag_engine.py`**: Unified hybrid search orchestrator combining SQLite WAL, BM25, and BGE-small embeddings.
* **`src/api.py`**: FastAPI backend with Server-Sent Events (SSE) streaming and audit logging.
* **`web/`**: Full-featured compliance auditor interface featuring citation inspection, statutory filters, and audit trail export.
