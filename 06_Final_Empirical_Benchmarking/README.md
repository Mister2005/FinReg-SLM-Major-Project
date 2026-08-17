# 06. Final Empirical Benchmarking (G7 Suite + IndiaFinBench)

### Overview
Dual evaluation validating FinReg-SLM on internal hard compliance queries (300 items) and external standardized public test split (324 items).

### Benchmark 1: Internal G7 Hard Suite (300 Queries)
* **Core Statutory Compliance (C1–C3)**: `94.43%`
* **Verifiable Citation Grounding**: `99.17%` (0.0% phantom citations)
* **Epistemic Abstention Quality (C5)**: `82.50%` (up from 0.0% on base)
* **Structural Protocol Conformance**: `100.0%`

### Benchmark 2: IndiaFinBench (arXiv:2604.19298 — 324 Questions)
* **Overall Macro Accuracy**: **`80.98%`**
* **Regulatory Interpretation (139 Qs)**: **`90.29%`**
* **Contradiction Detection (50 Qs)**: **`79.00%`**
* **Temporal Reasoning (64 Qs)**: **`75.78%`**
* **Standing**: Outperforms Base LLaMA-3-8B (77.60%), Mistral-7B (76.20%), and Non-Specialist Humans (69.00%).
