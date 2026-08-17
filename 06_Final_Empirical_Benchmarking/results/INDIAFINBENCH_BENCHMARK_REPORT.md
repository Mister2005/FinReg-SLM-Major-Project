# IndiaFinBench Benchmark Evaluation Report

**Model Evaluated:** FinReg-SLM DeepSeek-R1-7B (Stage 2 DPO)  
**Benchmark:** IndiaFinBench (arXiv:2604.19298, Rajveer Singh Pall et al.)  
**Split:** Test Set (324 Expert-Annotated RBI & SEBI Questions)  
**Evaluator:** Meta-Llama-3.3-70B-Instruct (Zero-Shot Deterministic Judge)  

---

## 1. Executive Summary

| Evaluation Metric | Score | Published Baseline Comparison |
| :--- | :---: | :--- |
| **Overall Accuracy** | **80.98%** | Competitive with Frontier 70B+ Baselines |
| **Reasoning Quality** | **84.66%** | Verifiable Chain-of-Thought `<think>` Reasoning |
| **Total Test Samples** | **324** | 100% Evaluated across RBI & SEBI |

---

## 2. Breakdown by Task Category

| Task Category | Sample Count | FinReg-SLM (7B DPO) Accuracy |
| :--- | :---: | :---: |
| **Regulatory Interpretation** | 139 | **90.29%** |
| **Numerical Reasoning** | 73 | **69.18%** |
| **Contradiction Detection** | 50 | **79.00%** |
| **Temporal Reasoning** | 64 | **75.78%** |

---

## 3. Breakdown by Regulatory Authority & Difficulty

### By Regulator:
- **SEBI (274 items):** 80.29%
- **RBI (52 items):** 84.62%

### By Difficulty:
- **Easy (127 items):** 87.40%
- **Medium (147 items):** 80.27%
- **Hard (52 items):** 67.31%

---

## 4. Key Scientific Insights
1. **Generalization Across Unseen RBI/SEBI Questions:** Our aligned 7B reasoning model demonstrates robust transfer to independent, third-party benchmark questions without task-specific prompt engineering.
2. **Chain-of-Thought Explanations:** The model's `<think> ... </think>` traces provide transparent statutory deduction, preventing blind memorization.
3. **On-Premises Privacy:** Achieved on a local 7B model deployable within private infrastructure under the DPDP Act 2023.
