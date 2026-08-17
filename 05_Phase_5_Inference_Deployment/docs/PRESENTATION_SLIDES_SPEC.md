# Final Major Project Presentation Deck Specification

## FinReg-AI: Indian Regulatory Compliance Intelligence System
**Presenter:** Varun (Sem 7/8 Major Project)  
**Target Time:** 15–20 Minutes  

---

### Slide 1: Title & Overview
- **Header**: FinReg-AI: Indian Regulatory Reasoning & Grounded Compliance Assistant
- **Subtitle**: Powered by DeepSeek-R1-7B DPO Alignment & 15,680 Real Regulatory Circulars
- **Key Points**:
  - Domain: Indian Banking, Corporate & Securities Law (RBI, SEBI, CBIC, MCA)
  - Key Innovation: Two-Stage SFT + DPO Alignment preserving reasoning circuits while achieving 100% benchmark grounding.

---

### Slide 2: The Problem with Generic LLMs in Law
- **Point 1**: High Legal Liability: Hallucinations lead to severe financial/regulatory penalties.
- **Point 2**: Temporal Velocity: Circulars amend previous rules; static models cite repealed provisions.
- **Point 3**: Reasoning Destruction: Standard fine-tuning breaks chain-of-thought representations.

---

### Slide 3: Ingestion Architecture & Data Engine
- **Visual**: Pipeline Diagram (Scraper $\to$ SQLite Manifest $\to$ Temporal Index $\to$ RAG)
- **Scale**: 15,680 circulars & Master Directions (14,147 RBI, 2,797 SEBI).
- **Temporal Modeling**: Explicit `[in_force_from, in_force_to]` metadata filtering as of query date.

---

### Slide 4: The 2-Stage Alignment Solution (Why It Worked)
- **Stage 1 (Clean SFT)**:
  - 250 single-document golden pairs.
  - $Q/V$-only LoRA ($0.0331\%$ parameters modified) keeping $99.967\%$ frozen.
  - Loss: $2.159 \to 1.503$, Token Accuracy: $73.0\%$.
- **Stage 2 (DPO Preference Optimization)**:
  - 250 preference pairs.
  - Native PyTorch DPO ($\beta=0.1$) rewarding bracketed citations & calibrated abstention.
  - Loss: $0.6931 \to 0.0055$, Margin: $+83.43$.

---

### Slide 5: Empirical Benchmark Matrix (300 Questions)
- **Table**:
  - Base 7B: **$68.17\%$**
  - Phase 3 Dense RAFT 7B: **$78.50\%$**
  - **Phase 5 FinReg-AI (Ours)**: **`100.00%`**
- **Breakdown**:
  - Single-Hop & Multi-Hop Grounding: $100\%$
  - Temporal & Ambiguous Resolution: $100\%$
  - Abstention & Hallucination Defense: $100\%$

---

### Slide 6: System Demo & Architecture
- **FastAPI Backend**: Real-time REST endpoints (`/api/query`, `/api/documents/{doc_id}`).
- **Glassmorphic Web Interface**:
  - Live collapsible `<think>` reasoning tree.
  - Clickable citation pills linking directly to source circular text in SQLite.
  - Time-travel compliance date selector.

---

### Slide 7: Portability & Quantization
- **Merged Model**: Standalone 15.2 GB FP16 safetensors (zero runtime adapter dependency).
- **Ollama / GGUF**: Single-command execution via `Modelfile` for edge deployment.

---

### Slide 8: Future Extensions & Conclusion
- Hybrid Dense + BM25 Reciprocal Rank Fusion.
- Continuous real-time scraper daemon.
- Summary: Demonstrates that disciplined small-model alignment beats brute-force prompting in specialized legal domains.
