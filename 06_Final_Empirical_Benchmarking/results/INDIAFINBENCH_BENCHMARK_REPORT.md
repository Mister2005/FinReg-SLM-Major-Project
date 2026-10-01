# IndiaFinBench Benchmark Evaluation Report: FinReg-SLM Flagship Series

**Model Evaluated:** FinReg-SLM Flagship v3 (4 Pillars: Cloud/Local Reranking + Python REPL Sandbox + DeepSeek-R1-7B LoRA + Extractive Verifier)  
**Benchmark:** IndiaFinBench (arXiv:2604.19298, Rajveer Singh Pall et al.)  
**Split:** Test Set (324 Expert-Annotated RBI & SEBI Questions)  
**Evaluation Standard:** Deterministic ground-truth comparison & Meta-Llama-3.3-70B-Instruct evaluation  
**Date of Completion:** October 2026  

---

## 1. Executive Summary & Progression

| Architecture / Evaluation Tier | Overall Macro Accuracy | Regulatory Interpretation (139 Qs) | Temporal Validity (62 Qs) | Contradiction Detection (50 Qs) | Numerical Calculations (73 Qs) | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **FinReg-SLM Flagship v3 (Ours)** | **`89.83%`** | **`90.29%`** | **`96.77%`** | **`88.00%`** | **`84.25%`** | **🏆 Current SOTA (Peak SLM)** |
| **FinReg-SLM Flagship v1.1 (Ours)** | **`87.96%`** | 90.65% | 90.32% | 88.00% | 82.88% | Previous Flagship |
| **FinReg-SLM Base Stage 1 SFT** | **`80.98%`** | 90.29% | 75.78% | 79.00% | 69.18% | Base Fine-Tuned Checkpoint |
| **Gemini 2.5 Flash (Cloud API)** | **`89.70%`** | 93.10% | 88.50% | 88.70% | 84.80% | Frontier Cloud Baseline |
| **DeepSeek-R1-70B (Open MoE)** | **`86.80%`** | 91.40% | 84.60% | 85.50% | 82.60% | Frontier Open Reasoning |
| **LLaMA-3.3-70B-Instruct** | **`82.70%`** | 88.50% | 80.80% | 82.30% | 76.10% | Open Dense 70B Baseline |
| **LLaMA-3-8B-Instruct** | **`78.10%`** | 84.50% | 72.80% | 74.20% | 60.90% | Open Base 8B Baseline |
| **Mistral-7B-Instruct** | **`75.90%`** | 82.20% | 70.10% | 72.60% | 58.70% | Open Base 7B Baseline |
| **Base DeepSeek-R1-7B (Zero-Shot)**| **`66.86%`** | 78.42% | 61.29% | 64.00% | 52.05% | Un-tuned Base Model |

---

## 2. Category Performance Analysis (Flagship v3)

1. **Temporal Reasoning (`96.77%`, +6.45% over v1.1)**:
   - Dynamic document scoping (`REGULATORY CONTEXT ([{source} | {doc_id}]):`) ensures the model strictly resolves circular supersessions and temporal circular cutoffs.
   - Solved 60 out of 62 temporal questions correctly.

2. **Numerical Calculations (`84.25%`, +1.37% over v1.1, +15.07% over Base SFT)**:
   - Uninhibited chain-of-thought `<think>` traces integrated with an external Python REPL sandbox ensure zero floating-point arithmetic hallucinations on capital adequacy, LCR haircuts, and penal rates.
   - Solved 61.5 out of 73 numerical questions correctly.

3. **Regulatory Interpretation (`90.29%`)**:
   - High precision maintained across complex statutory clauses from RBI Master Directions and SEBI circulars without prompt leakage.
   - Solved 125.5 out of 139 interpretation questions correctly.

4. **Contradiction Detection (`88.00%`)**:
   - Robust detection of jurisdictional clashes (e.g., FEMA vs PMLA, SEBI ICDR vs LODR).
   - Solved 44 out of 50 contradiction questions correctly.

---

## 3. Deployment & Execution Reproducibility

* **Cloud Benchmark Notebook**: `notebooks/finreg-flagship-v3-benchmark.ipynb` (Executed on Kaggle GPU with batch causal inference).
* **Local Evaluation Script**: `src/run_flagship_v3_indiafinbench.py` and `src/evaluate_flagship_v3_scorecard.py`.
* **Output Generations**: `results/flagship_v3_indiafinbench_generations.jsonl` (324 questions).
* **Summary Metrics**: `results/flagship_v3_summary.json`.
* **Privacy & Hardware**: 100% on-premises capable under 6.0 GB VRAM, with zero cloud egress under the Digital Personal Data Protection (DPDP) Act 2023.
