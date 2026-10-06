# FinReg-SLM: Master Project Repository & Technical Hub

**Project Title:** FinReg-SLM — Domain-Specialized Small Language Model for Multi-Agency Indian Financial Regulatory Compliance  
**Student Name:** Varun Gupta | **SAP ID:** 60018230100  
**Course:** Research Ecosystem (DJS23ITELX12) | Final Year B.Tech. in AI & DS (Sem VII)  
**Institution:** SVKM's Dwarkadas J. Sanghvi College of Engineering (DJSCE), Mumbai  
**Date:** August 17, 2026  

---

## 🏛️ Project Summary at a Glance

FinReg-SLM is an on-premises, version-aware 7B reasoning language model engineered to automate compliance verification across **13 Indian financial regulatory authorities** (RBI, SEBI, MCA, CBIC, CBDT, IBBI, EPFO, ESIC, IRDAI, PFRDA, MeitY, FIU-IND, IFSCA) and **25 Parliamentary Acts**.

By combining a **version-aware hybrid retrieval engine** (Dense BGE-small + BM25 + Reciprocal Rank Fusion + Temporal Filtering) with a **Two-Stage Alignment strategy** (Stage 1 QLoRA SFT on Chain-of-Thought traces + Stage 2 Native DPO on epistemic preference pairs using `DeepSeek-R1-Distill-Qwen-7B`), FinReg-SLM achieves frontier-grade compliance accuracy with **100% on-premises privacy under the DPDP Act 2023**.

---

## 📂 Repository Directory Map

| Folder | Name & Purpose | Key Highlights & Contents |
| :--- | :--- | :--- |
| **`00_Academic_Deliverables/`** | Official Submissions & Presentation Decks | Final `IPD_Tutorial_1_Varun_Gupta_55.docx`, 8-Slide `FinReg_SLM_Slide_Deck_4.pptx`, Top 8 Papers review, and syllabus PDFs. |
| **`01_Phase_1_Corpus_Ingestion/`** | Multi-Agency Crawlers & Ingestion Engine | Ingestion scripts, SQLite WAL schema (505.96 MB, 21,705 docs across 13 regulators + 900 Central Acts), extraction specifications, and temporal metadata tagging. |
| **`02_Phase_2_Hybrid_Retrieval/`** | Version-Aware Hybrid Search Pipeline | Dense BGE-small + BM25 FTS5 lexical index, Reciprocal Rank Fusion ($k=60$), cross-encoder reranker, and `effective_date` filters. |
| **`03_Phase_3_Dataset_Synthesis/`** | Golden SFT & DPO Preference Data | 257 golden reasoning traces with `<think>` CoT tags (`omni_golden_sft_350.jsonl`) and 257 DPO preference pairs (`omni_dpo_pairs_350.jsonl`). |
| **`04_Phase_4_Model_Training_DeepSeek_R1/`** | Two-Stage QLoRA SFT & Native DPO | SFT/DPO training scripts (4-bit NF4, fused kernels), adapter configs & weights, loss logs, and benchmark progression. |
| **`05_Phase_5_Inference_Deployment/`** | Local Inference Engine & Compliance UI | FastAPI streaming backend, 4-bit quantized loader (4.5GB VRAM), and full web interface for compliance officers. |
| **`06_Final_Empirical_Benchmarking/`** | G7 Suite (300 Qs) + IndiaFinBench (324 Qs) | Test runners, automated 70B LLM-as-a-Judge evaluators, evaluation JSON summaries, and institutional scaling roadmap. |
| **`07_Research_and_Literature/`** | Scopus Papers Matrix & Viva Guides | 6 research gaps mapping to code fixes, top 8 papers analysis, and viva voce readiness guide. |

---

## 📊 Empirical Benchmark Results

### 1. FinReg-Omni13 Benchmark (325 Queries across ALL 13 Indian Regulators)
* **Method 1 (Single Pass / Pure Weights - DEFAULT):** **`100.00%`** (325.0 / 325) 🏆 **PERFECT SCORE**
* **Method 2 (Combined Pipeline: Model + REPL + Reflection):** **`99.38%`** (323.0 / 325)
* **Regulator Breakdown (25 Qs each):** RBI (100%), SEBI (100%), IRDAI (100%), PFRDA (100%), IBBI (100%), MCA (100%), CBIC (100%), CBDT (100%), CCI (100%), EPFO (100%), ESIC (100%), MEITY (100%), IFSCA (100%).
* **Multiple Choice (246 Qs):** **`100.00%`** | **Numerical & Calculations (65 Qs):** **`100.00%`** | **Contradiction (7 Qs):** **`100.00%`** | **Temporal (7 Qs):** **`100.00%`**

### 2. External IndiaFinBench Test Split (arXiv:2604.19298 — 324 Questions)
* **Method 1 (Single Pass):** **`99.38%`** (322 / 324 Questions correct)
* **Flagship Dual-Run Union:** **`99.91%`** (323 / 324 Questions correct)
* **Regulatory Interpretation (104 Qs):** **`100.00%`** (104 / 104)
* **Numerical Reasoning & Computation (100 Qs):** **`100.00%`** (100 / 100)
* **Temporal Validity & Amendments (60 Qs):** **`100.00%`** (60 / 60)
* **Cross-Statutory Contradiction (60 Qs):** **`96.67%`** (58 / 60)
* **Beats Frontier Cloud Models:** Vastly outperforms **Gemini 2.5 Pro (`91.10%`)**, **Gemini 2.5 Flash (`89.70%`)**, **DeepSeek-R1-70B (`86.80%`)**, **LLaMA-3.3-70B (`82.70%`)**, and **Qwen3-32B (`81.10%`)**.

### 3. Grand Total Evaluation Scope (649 Production Queries)
* **Method 1 Grand Total Accuracy:** **`99.69%`** (**647 / 649 queries passing**)
* **Execution Platform:** Kaggle Dual Tesla T4 GPUs (30 GB VRAM, 24,241s execution, Version 8)

### 4. Internal G7 Hard Compliance Benchmark (300 Queries via LLaMA-3.3-70B Judge)
* **Core Statutory Compliance (C1–C3):** **`94.43%`** (Direct: `92.2%`, Multi-Hop: `94.4%`, Cross-Regulatory: `96.7%`)
* **Verifiable Citation Grounding:** **`99.17%`** (Phantom citation rate: `0.0%`)
* **Epistemic Refusal Quality (C5):** **`82.50%`** (up from `0.0%` on base models)
* **False Premise Rejection (C6):** **`58.00%`** (up from `0.0%` on base models)
* **Structural Protocol Conformance:** **`100.0%`**

---

## 🚀 Execution & Quick Start

### 1. Run Enterprise Compliance CLI (Method 1 Default):
```bash
python "05_Phase_5_Inference_Deployment/Enterprise_Local_Deployment/cli.py" --interactive
```

### 2. Launch Enterprise Local FastAPI Server:
```bash
python "05_Phase_5_Inference_Deployment/Enterprise_Local_Deployment/api_server.py"
```
Open `http://localhost:8000` in your browser. Supports `POST /v1/compliance/audit` and `POST /v1/chat/completions`.

### 3. Run Kaggle Master Pipeline Benchmark (649 Queries):
```bash
jupyter notebook "06_Final_Empirical_Benchmarking/notebooks/FinReg_Omni13_Kaggle_Master_Pipeline.ipynb"
```
