# FinReg-SLM: Master Project Repository & Technical Hub

**Project Title:** FinReg-SLM — Domain-Specialized Small Language Model for Multi-Agency Indian Financial Regulatory Compliance  
**Student Name:** Varun Gupta | **SAP ID:** 60004220055 | **UID:** 2022300055  
**Course:** Research Ecosystem (DJS23ITELX12) | Final Year B.Tech. in AI & DS (Sem VII)  
**Institution:** SVKM's NMIMS, Mukesh Patel School of Technology Management & Engineering (MPSTME)  
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
| **`01_Phase_1_Corpus_Ingestion/`** | Multi-Agency Crawlers & Ingestion Engine | Ingestion scripts, SQLite WAL schema (435 MB, 18,242 docs), extraction specifications, and temporal metadata tagging. |
| **`02_Phase_2_Hybrid_Retrieval/`** | Version-Aware Hybrid Search Pipeline | Dense BGE-small + BM25 FTS5 lexical index, Reciprocal Rank Fusion ($k=60$), cross-encoder reranker, and `effective_date` filters. |
| **`03_Phase_3_Dataset_Synthesis/`** | Golden SFT & DPO Preference Data | 257 golden reasoning traces with `<think>` CoT tags (`omni_golden_sft_350.jsonl`) and 257 DPO preference pairs (`omni_dpo_pairs_350.jsonl`). |
| **`04_Phase_4_Model_Training_DeepSeek_R1/`** | Two-Stage QLoRA SFT & Native DPO | SFT/DPO training scripts (4-bit NF4, fused kernels), adapter configs & weights, loss logs, and benchmark progression. |
| **`05_Phase_5_Inference_Deployment/`** | Local Inference Engine & Compliance UI | FastAPI streaming backend, 4-bit quantized loader (4.5GB VRAM), and full web interface for compliance officers. |
| **`06_Final_Empirical_Benchmarking/`** | G7 Suite (300 Qs) + IndiaFinBench (324 Qs) | Test runners, automated 70B LLM-as-a-Judge evaluators, evaluation JSON summaries, and institutional scaling roadmap. |
| **`07_Research_and_Literature/`** | Scopus Papers Matrix & Viva Guides | 6 research gaps mapping to code fixes, top 8 papers analysis, and viva voce readiness guide. |

---

## 📊 Dual Empirical Benchmark Results

### 1. Internal G7 Hard Compliance Benchmark (300 Queries via LLaMA-3.3-70B Judge)
* **Core Statutory Compliance (C1–C3):** **`94.43%`** (Direct: `92.2%`, Multi-Hop: `94.4%`, Cross-Regulatory: `96.7%`)
* **Verifiable Citation Grounding:** **`99.17%`** (Phantom citation rate: `0.0%`)
* **Epistemic Refusal Quality (C5):** **`82.50%`** (up from `0.0%` on base models)
* **False Premise Rejection (C6):** **`58.00%`** (up from `0.0%` on base models)
* **Structural Protocol Conformance:** **`100.0%`**

### 2. External IndiaFinBench Test Split (arXiv:2604.19298 — 324 Questions across SEBI & RBI)
* **Overall Macro Accuracy:** **`80.98%`** *(Beats Base LLaMA-3-8B at 77.60%, Mistral-7B at 76.20%, and Humans at 69.00%)*
* **Regulatory Interpretation (139 Qs):** **`90.29%`** *(Directly rivals GPT-4o at 92.10% and Claude 3.5 Sonnet at 91.00%)*
* **Contradiction Detection (50 Qs):** **`79.00%`**
* **Temporal Reasoning (64 Qs):** **`75.78%`**
* **Numerical Reasoning (73 Qs):** **`69.18%`**

---

## 🚀 Execution & Quick Start

### 1. Run Local Inference CLI:
```bash
python "05_Phase_5_Inference_Deployment/src/model_server.py"
```

### 2. Launch Full Web Compliance Auditor:
```bash
uvicorn "05_Phase_5_Inference_Deployment.src.api:app" --host 0.0.0.0 --port 8000
```
Open `http://localhost:8000` in your browser.

### 3. Run IndiaFinBench Benchmark Evaluation:
```bash
python "06_Final_Empirical_Benchmarking/src/run_inference.py"
python "06_Final_Empirical_Benchmarking/src/evaluate_indiafinbench.py"
```
