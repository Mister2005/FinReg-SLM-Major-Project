# 06. Final Empirical Benchmarking (G7 Suite + IndiaFinBench)

### Overview
Dual evaluation validating FinReg-SLM on internal hard compliance queries (300 items) and the external standardized public test split (324 items from IndiaFinBench).

---

### 🏆 Benchmark 1: IndiaFinBench (arXiv:2604.19298 — 324 Questions)
* **FinReg-SLM Flagship v5.2 (Current Global SOTA)**: **`99.15%`** Macro Accuracy (**320 / 324 Perfect Answers**)
  * **Contradiction Detection (50 Qs)**: **`100.00%`** (50 / 50 Perfect)
  * **Numerical Calculations (73 Qs)**: **`100.00%`** (73 / 73 Perfect via Sandboxed Python REPL)
  * **Temporal Validity (62 Qs)**: **`98.39%`** (61 / 62 Perfect via Dynamic Statutory Scoping)
  * **Regulatory Interpretation (139 Qs)**: **`98.20%`** (136 / 139 Perfect via Verbatim Grounding)
* **FinReg-SLM Flagship v4.3**: **`94.74%`**
* **FinReg-SLM Flagship v4.1**: **`94.08%`**
* **FinReg-SLM Flagship v3.0**: **`89.83%`**
* **Base Stage 1 SFT**: **`80.98%`**
* **External Baselines**: Surpasses **Gemini 2.5 Pro (`91.10%`)**, **Gemini 2.5 Flash (`89.70%`)**, **DeepSeek-R1-70B (`86.80%`)**, **LLaMA-3.3-70B (`82.70%`)**, and open 7B/8B models (`75.9% - 78.1%`).

---

### 🛡️ Benchmark 2: Internal G7 Hard Suite (300 Queries)
* **Core Statutory Compliance (C1–C3)**: `94.43%`
* **Verifiable Citation Grounding**: `99.17%` (0.0% phantom citations)
* **Epistemic Abstention Quality (C5)**: `82.50%` (up from 0.0% on base)
* **False Premise Rejection (C6)**: `58.00%` (up from 0.0% on base)
* **Structural Protocol Conformance**: `100.0%`

---

### 📁 Code, Notebooks & Results Artifacts
* **`notebooks/finreg-flagship-v5_2-benchmark.ipynb`**: Complete Kaggle Dual-GPU benchmark notebook executing 2-Pass Self-Correction causal inference across all 324 questions.
* **`results/flagship_v5_2_indiafinbench_generations.jsonl`**: Complete 324-question test outputs with `<think>` traces, REPL execution blocks, and self-correction records.
* **`results/flagship_v5_2_summary.json`**: Official category-level summary metrics (99.15% Macro Avg).
* **`results/FLAGSHIP_V5_2_INDIAFINBENCH_SCORECARD.md`**: Formatted comparative scorecard markdown.
* **`results/INDIAFINBENCH_BENCHMARK_REPORT.md`**: Comprehensive benchmark evaluation report.
