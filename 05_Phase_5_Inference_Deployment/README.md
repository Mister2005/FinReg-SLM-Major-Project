# 05. Phase 5 — On-Premises 4-Pillar Inference Engine & Compliance UI

### Overview
Phase 5 establishes the production inference architecture for self-hosted execution in secure banking environments (100% on-premises under 6.0 GB VRAM, DPDP Act 2023 compliant).

### 🏛️ The 4 Pillars of Inference Enhancement
1. **Pillar 1: Cross-Encoder Context Re-ranking (`src/rag_engine.py` & `src/client.py`)**:
   - Scores and ranks candidate provisions using BAAI/bge-reranker-base (local or dedicated endpoint).
2. **Pillar 2: Program-Aided Numerical Sandbox (`src/repl_sandbox.py`)**:
   - Sandboxed Python REPL for deterministic financial arithmetic (LCR haircuts, CAR tier capital, penal interest calculations), yielding 84.25% numerical accuracy.
3. **Pillar 3: DeepSeek-R1-7B Structured Reasoning Engine (`src/model_server.py`)**:
   - 4-bit NF4 quantized loader generating transparent `<think>` step-by-step statutory deduction traces.
4. **Pillar 4: Extractive Statutory Verifier (`src/verifier.py` & `src/best_of_n_search.py`)**:
   - Verifies citation grounding and prevents hallucinated circular references against the local SQLite manifest.

### Supporting Modules
* **`src/docket_schema.py`**: Pydantic schema enforcing structured compliance dockets with confidence scores and statutory citations.
* **`src/api.py`**: Production FastAPI backend with Server-Sent Events (SSE) streaming and audit logging.
* **`src/demo_e2e_pipeline.py`**: End-to-end multi-agency compliance auditing demonstration.
* **`src/test_all_4_pillars.py`**: Automated verification test suite for all 4 pillars.
* **`web/`**: Full-featured compliance auditor interface with interactive citation inspection and regulatory timeline filtering.

