# 06. Final Empirical Benchmarking (G7 Suite + IndiaFinBench)

### Overview
Dual evaluation validating FinReg-SLM on internal hard compliance queries (300 items) and the external standardized public test split (324 items from IndiaFinBench).

---

### 🏆 Benchmark 1: IndiaFinBench (arXiv:2604.19298 — 324 Questions)
* **FinReg-SLM Flagship v3 (Current SOTA)**: **`89.83%`** Macro Accuracy
  * **Temporal Validity (62 Qs)**: **`96.77%`** (Dynamic statutory scoping)
  * **Regulatory Interpretation (139 Qs)**: **`90.29%`**
  * **Contradiction Detection (50 Qs)**: **`88.00%`**
  * **Numerical Calculations (73 Qs)**: **`84.25%`** (Sandboxed Python REPL execution)
* **FinReg-SLM Flagship v1.1 (Previous Best)**: **`87.96%`**
* **Base Stage 1 SFT**: **`80.98%`**
* **External Baselines**: Surpasses **Gemini 2.5 Flash (`89.70%`)**, **DeepSeek-R1-70B (`86.80%`)**, **LLaMA-3.3-70B (`82.70%`)**, and open 7B/8B models (`75.9% - 78.1%`).

---

### 🛡️ Benchmark 2: Internal G7 Hard Suite (300 Queries)
* **Core Statutory Compliance (C1–C3)**: `94.43%`
* **Verifiable Citation Grounding**: `99.17%` (0.0% phantom citations)
* **Epistemic Abstention Quality (C5)**: `82.50%` (up from 0.0% on base)
* **False Premise Rejection (C6)**: `58.00%` (up from 0.0% on base)
* **Structural Protocol Conformance**: `100.0%`

---

### 📁 Code, Notebooks & Results Artifacts
* **`notebooks/finreg-flagship-v3-benchmark.ipynb`**: Complete Kaggle GPU benchmark notebook executing batch causal inference across all 324 questions.
* **`src/run_flagship_v3_indiafinbench.py`**: Python inference runner for local GPU / cloud GPU execution.
* **`src/evaluate_flagship_v3_scorecard.py`**: Automated evaluation scorecard generator computing precision, recall, and category deltas.
* **`results/flagship_v3_indiafinbench_generations.jsonl`**: Complete 324-question test outputs with `<think>` traces and REPL execution blocks.
* **`results/flagship_v3_summary.json`**: Official category-level summary metrics.
* **`results/FLAGSHIP_V3_INDIAFINBENCH_SCORECARD.md`**: Formatted comparative scorecard markdown.
