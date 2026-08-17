# FinReg-SLM: Omni-Regulator AI
### A Two-Stage Aligned Reasoning Small Language Model with Version-Aware Hybrid Retrieval for Multi-Agency Indian Financial Compliance

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![PyTorch 2.4](https://img.shields.io/badge/PyTorch-2.4-EE4C2C.svg)](https://pytorch.org/)
[![HuggingFace Transformers](https://img.shields.io/badge/HuggingFace-Transformers-FFD21E.svg)](https://huggingface.co/)
[![Unsloth QLoRA](https://img.shields.io/badge/Unsloth-4bit%20NF4%20QLoRA-8A2BE2.svg)](https://github.com/unslothai/unsloth)
[![Compliance DPDP Act 2023](https://img.shields.io/badge/Compliance-DPDP%20Act%202023-008080.svg)](https://www.meity.gov.in/)
[![IndiaFinBench 80.98%](https://img.shields.io/badge/IndiaFinBench-80.98%25%20Macro-green.svg)](https://arxiv.org/abs/2604.19298)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📌 Executive Summary

**FinReg-SLM** is an on-premises, version-aware **7B Parameter Small Reasoning Language Model** engineered to automate statutory compliance verification across **13 Indian financial regulatory authorities** (RBI, SEBI, MCA, CBIC, CBDT, IBBI, EPFO, ESIC, IRDAI, PFRDA, MeitY, FIU-IND, IFSCA) and **25 Parliamentary Acts**.

Financial compliance in India requires navigating over **18,242 active circulars, Master Directions, notifications, and statutory guidelines**. Naive generative AI and standard semantic vector search suffer from critical failure modes:
1. **17%–33% Hallucination Rates:** Inventing fictitious circular numbers and misquoting statutory provisions.
2. **Temporal Amnesia:** Retrieving older, superseded circulars because of high keyword similarity, presenting obsolete law as active mandates.
3. **Epistemic Sycophancy (0% Refusal):** Accepting false user premises and enthusiastically answering ungrounded queries.
4. **Data Sovereignty Violations:** Uploading internal audit logs and banking records to offshore cloud APIs violates India's **Digital Personal Data Protection (DPDP) Act 2023**.

FinReg-SLM resolves these challenges by adapting **DeepSeek-R1-Distill-Qwen-7B** for local execution inside **4.5 GB VRAM on a single consumer 8GB GPU**. The system couples a **version-aware hybrid retrieval engine** (Dense BGE-small + BM25 Lexical + Reciprocal Rank Fusion $k=60$ + Temporal Filtering) with a **Two-Stage Alignment pipeline** (Stage 1 QLoRA SFT on Chain-of-Thought reasoning traces + Stage 2 Native Fused-Kernel DPO for citation grounding and epistemic refusal).

---

## 🏆 Benchmark Highlights

### 1. External IndiaFinBench Public Benchmark (arXiv:2604.19298 — 324 Questions)
* **Overall Macro Accuracy:** **`80.98%`** *(Beats Base LLaMA-3-8B at 77.60%, Mistral-7B at 76.20%, and Non-Specialist Humans at 69.00%)*
* **Regulatory Interpretation (139 Qs):** **`90.29%`** *(Directly rivals frontier cloud APIs: GPT-4o at 92.10% and Claude 3.5 Sonnet at 91.00%)*
* **Contradiction Detection (50 Qs):** **`79.00%`**
* **Temporal Reasoning (64 Qs):** **`75.78%`**
* **Reasoning Quality Score:** **`84.66%`**

### 2. Internal G7 Hard Compliance Benchmark (300 Queries via LLaMA-3.3-70B Judge)
* **Core Statutory Compliance (C1–C3):** **`94.43%`** (Direct: `92.2%`, Multi-Hop: `94.4%`, Cross-Regulatory: `96.7%`)
* **Verifiable Citation Grounding:** **`99.17%`** (Phantom citation rate: `0.0%`)
* **Epistemic Refusal Quality (C5):** **`82.50%`** (up from `0.0%` on base models)
* **False Premise Rejection (C6):** **`58.00%`** (up from `0.0%` on base models)
* **Structural Protocol Conformance:** **`100.0%`**

---

## 🏛️ Comprehensive Benchmark Leaderboard

### Table A: IndiaFinBench Full Leaderboard (324 Questions across SEBI & RBI)

| Model Name | Model Size & Hosting | Regulatory Interp. (139 Qs) | Contradiction (50 Qs) | Temporal (64 Qs) | Numerical (73 Qs) | Overall Macro Accuracy | Benchmark Tier |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Gemini 2.5 Flash** | Cloud MoE (Proprietary API) | **93.40%** | **88.00%** | **86.50%** | **87.20%** | **89.70%** | **Tier 1 (Frontier Cloud)** |
| **GPT-4o** | Cloud MoE (Proprietary API) | **92.10%** | **86.00%** | **84.40%** | **85.10%** | **88.20%** | **Tier 1 (Frontier Cloud)** |
| **Claude 3.5 Sonnet** | Cloud MoE (Proprietary API) | **91.00%** | **84.00%** | **82.80%** | **83.50%** | **86.50%** | **Tier 1 (Frontier Cloud)** |
| **FinReg-SLM 7B (Ours)** | **7B Dense (Local 8GB GPU)** | **90.29%** | **79.00%** | **75.78%** | **69.18%** | **80.98%** | **Top Tier 2 (Beats All Open Base Models)** |
| **LLaMA-3-8B Base** | 8B Dense (General Base) | 84.20% | 72.50% | 70.10% | 58.40% | 77.60% | Tier 2 (Open Base Model) |
| **Mistral-7B-Instruct** | 7B Dense (General Base) | 82.80% | 71.00% | 68.50% | 56.20% | 76.20% | Tier 2 (Open Base Model) |
| **Gemma 4 E4B** | 4B Dense (Compact Open) | 76.50% | 65.00% | 62.00% | 51.00% | 70.40% | Tier 3 (Compact Open Model) |
| **Non-Specialist Human** | Human Baseline | 74.00% | 66.00% | 65.00% | 54.00% | 69.00% | Human Baseline |

> **Privacy Note under DPDP Act 2023:** While Tier 1 proprietary models lead in raw mathematical score (due to hundreds of billions of parameters), their reliance on offshore third-party cloud APIs violates Indian enterprise banking regulations. FinReg-SLM runs **100% locally with zero data transfer**, outperforming all open base models of comparable scale and non-specialist human experts.

---

### Table B: Internal G7 Hard Suite Evaluation (300 Queries)

| Model Configuration | C1 (Direct) | C2 (Multi-Hop) | C3 (Cross-Reg) | C4 (Numeric) | C5 (Abstain) | C6 (Reject) | Citation Rate | LLM Judge Score |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Base 3B (Llama-3.2-3B)** | 58.0% | 52.0% | 46.0% | 44.0% | 0.0% (Hallucinated) | 0.0% (Sycophantic) | 18.6% | **44.80%** |
| **RAFT Fine-Tuned 3B** | 72.0% | 68.0% | 64.0% | 60.0% | 0.0% (Hallucinated) | 0.0% (Sycophantic) | 78.0% | **18.80%*** |
| **Stage 1 SFT 7B (DeepSeek-R1)** | 90.0% | 92.0% | 89.5% | 91.0% | 0.0% (Hallucinated) | 0.0% (Sycophantic) | 88.4% | **68.17%** |
| **Stage 2 DPO 7B (Our Final Model)** | **92.2%** | **94.4%** | **96.7%** | **93.8%*** | **82.5% (Refusal)** | **58.0% (Rejection)** | **99.2%** | **70.71% (100% Conf.)** |

*\*Evaluated via Meta-Llama-3.3-70B-Instruct under zero-shot deterministic evaluation (temperature=0.0).*

---

## 🔬 Research Gaps, Architectural Fixes & Empirical Gains

| Gap ID | Identified Research Gap | Key Literature | Our Concrete Architectural Fix | Measured Empirical Score Gain |
| :-: | :--- | :--- | :--- | :--- |
| **G1** | **RAG vs FT Dichotomy** | Ovadia 2024, Zhang 2024 | Two-Stage RAFT with Native `<think>` CoT traces (Golden Chunks + Distractor Circulars) | Core Statutory Compliance: **`62.3%` $\rightarrow$ `94.43%`**; IndiaFinBench Reg: **`90.29%`** |
| **G2** | **Hallucination of Authority** | Magesh 2025, Pai & Hsu 2026 | Verbatim Citation Verification + DPO Margin Loss Penalty | Citation Grounding: **`51.6%` $\rightarrow$ `99.17%`**; Phantom Citations: **`0.0%`** |
| **G3** | **Temporal Amnesia in RAG** | Kim 2026, Hindi 2025 | Structured Date Tagging (`effective_date`) + Hybrid BM25/Dense RRF + Temporal DPO | Contradiction Detection: **`79.00%`**; Temporal Reasoning: **`75.78%`** |
| **G4** | **Epistemic Inability to Abstain** | Magesh 2025, Kadavath 2022 | Negative Preference DPO Alignment (C5 Refusal & C6 False Premise Pairs) | Epistemic Refusal: **`0.0%` $\rightarrow$ `82.50%`**; Premise Rejection: **`0.0%` $\rightarrow$ `58.00%`** |
| **G5** | **Catastrophic Forgetting** | Luo 2023, Biderman 2024 | All-Linear QLoRA ($r=64, \alpha=128$) in 4-bit NF4 with strict ChatML Token Supervision | **`100.0%`** Structural Protocol Conformance; Zero Syntax Collapse |
| **G6** | **Non-Western Regulatory Void** | Du 2025, Rajveer 2026 | Dual Evaluation: Internal G7 Suite (300 Qs) + External IndiaFinBench (324 Qs) | Overall Macro Accuracy: **`80.98%`** *(Beats Base 7B/8B Open LLMs by **+3.4% to +5.0%**)* |

---

## 📁 Repository Directory Structure

```
FinReg_SLM_Unified_Project_Hub/
├── 00_Academic_Deliverables/          # Official institutional submissions and slide decks
│   ├── IPD_Tutorial_1_Varun_Gupta_55.docx           # Final focused 8-paper version with DOIs & full benchmarks
│   ├── IPD_Tutorial_1_Varun_Gupta_55_Version_1.docx # Original exhaustive 23-paper version with full Scopus index
│   ├── FinReg_SLM_Slide_Deck_4.pptx                 # 8-slide executive widescreen (16:9) presentation deck
│   ├── Top_Literature_Review_Papers_FinReg_SLM.docx # Dedicated breakdown of Top 8 literature papers (DOCX)
│   ├── Top_Literature_Review_Papers_FinReg_SLM.md   # Dedicated breakdown of Top 8 literature papers (Markdown)
│   ├── Tutorial 1 Literature Review Research Gap.pdf# Faculty guidelines and syllabus
│   └── Research Review - 2.pdf
│
├── 01_Phase_1_Corpus_Ingestion/      # Ingestion pipelines & multi-agency data models
│   ├── src/                          # Web scraping and circular extraction scripts (RBI, SEBI, MCA, etc.)
│   ├── specs/                        # 00-PROJECT-BRIEF.md through 11-RUNBOOK.md & data specifications
│   └── README.md                     # Ingestion architecture (18,242 documents, 435MB SQLite WAL)
│
├── 02_Phase_2_Hybrid_Retrieval/      # Version-aware hybrid retrieval engine
│   ├── src/                          # Dense vector (BGE-small) + BM25 FTS5 + RRF (k=60) + Temporal Filter
│   ├── data/                         # Processed chunk indexes and seed queries
│   ├── specs/                        # 12-PHASE2-BRIEF.md through 20-RUNBOOK.md
│   └── README.md                     # Hybrid search and temporal obsolescence resolution
│
├── 03_Phase_3_Dataset_Synthesis/     # Golden reasoning and preference pair datasets
│   ├── data/                         # omni_golden_sft_350.jsonl & omni_dpo_pairs_350.jsonl (257 clean traces)
│   ├── src/                          # Synthesis generators, hallucination traps, and distractor injectors
│   └── README.md                     # Data curation methodology and statistics
│
├── 04_Phase_4_Model_Training_DeepSeek_R1/  # Two-Stage QLoRA SFT & Native DPO on DeepSeek-R1-7B
│   ├── src/                          # Training pipelines (train_stage1_sft.py, train_stage2_dpo.py, merge)
│   ├── adapters/                     # Trained LoRA adapter checkpoints (configs & weights)
│   ├── logs/                         # Benchmark summaries and 70B LLM judge evaluation logs
│   └── README.md                     # 4-bit NF4 memory optimization and loss convergence
│
├── 05_Phase_5_Inference_Deployment/  # Local on-premises inference engine & Web UI
│   ├── src/                          # 4-bit model server (4.5GB VRAM), unified RAG engine, FastAPI backend
│   ├── web/                          # Full web interface (app.js, index.css, index.html) with audit export
│   ├── quantization/                 # Ollama export and Modelfiles
│   └── README.md                     # DPDP Act 2023 on-premises deployment guide
│
├── 06_Final_Empirical_Benchmarking/  # G7 Hard Suite (300 Qs) + External IndiaFinBench (324 Qs)
│   ├── data/                         # G7 test suite & official IndiaFinBench test set (324 questions)
│   ├── src/                          # 4-bit NF4 batch runner & 6-thread 70B LLM judge evaluators
│   ├── results/                      # Full evaluation JSON summaries, score breakdowns, markdown reports
│   ├── INDIAFINBENCH_EMPIRICAL_STUDY_AND_SCALING_ROADMAP.md # Institutional compute scaling roadmap
│   └── README.md                     # Comparative benchmark breakdown vs. open base and cloud models
│
├── 07_Research_and_Literature/       # Literature matrix, research gap mappings & viva guides
│   ├── FinReg_SLM_Comprehensive_Research_Gaps_Fixes_and_Empirical_Impact.md # 343-line gaps-to-fixes mapping
│   ├── Top_Literature_Review_Papers_FinReg_SLM.md / .docx
│   ├── LITERATURE-REVIEW-2026-08-14.md
│   ├── VIVA-READINESS-GUIDE-2026-08-14.md # Comprehensive viva voce Q&A guide
│   └── README.md
│
└── MASTER_PROJECT_INDEX.md           # Master technical index and repository navigation guide
```

---

## ⚙️ Quick Start & Execution

### 1. Prerequisites & Environment Setup
```bash
git clone https://github.com/Mister2005/FinReg-SLM-Major-Project.git
cd FinReg-SLM-Major-Project
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r 05_Phase_5_Inference_Deployment/requirements.txt
```

### 2. Launch Local FastAPI Model Server & UI
```bash
# Launch FastAPI backend with SSE streaming
uvicorn 05_Phase_5_Inference_Deployment.src.api:app --host 0.0.0.0 --port 8000
```
Open your browser at `http://localhost:8000` to interact with the compliance interface.

### 3. Run Automated IndiaFinBench Evaluation (324 Questions)
```bash
# Run local 4-bit NF4 batched inference
python 06_Final_Empirical_Benchmarking/src/run_inference.py

# Run Frontier LLM-as-a-Judge evaluation (LLaMA-3.3-70B)
python 06_Final_Empirical_Benchmarking/src/evaluate_indiafinbench.py
```

---

## 🔮 Future Scope & Scaling Roadmap

1. **Parameter Scaling on Institutional Multi-GPU Compute (14B / 32B / 70B):**
   * Fine-tuning `DeepSeek-R1-Distill-14B/32B` or `Meta-Llama-3.3-70B` on enterprise GPU hardware (e.g., A100/H100 clusters) will expand working memory depth, projected to achieve **>91.5% accuracy** and surpass proprietary cloud models on-premises.
2. **Program-Aided Compliance (Python REPL Sandbox):**
   * Integrating an automated Python execution sandbox inside `<think>` CoT traces to execute multi-step compound arithmetic (e.g., capital adequacy deductions and haircut compounding), boosting numerical accuracy from **69.18% to 98%+**.
3. **Online Group Relative Policy Optimization (GRPO):**
   * Transitioning from static offline DPO to online DeepSeek-style GRPO with verifiable rule-based reward functions for statutory circular citations and mathematical verification.
4. **Autonomous 24/7 Regulatory Monitoring Daemon:**
   * Background daemons actively monitoring daily gazettes across all 13 authorities, incrementally updating the SQLite WAL index with real-time SSE compliance alerts.

---

## 📚 Primary Literature References (IEEE Format)

* **[1]** O. Ovadia, M. Brief, M. Mishaeli, and O. Elisha, *"Fine-Tuning or Retrieval? Comparing Knowledge Injection in LLMs,"* in *Proc. EMNLP 2024*, pp. 237–250, 2024, doi: `10.18653/v1/2024.emnlp-main.15`.
* **[2]** T. Zhang, S. G. Patil, N. Jain, S. Shen, M. Zaharia, I. Stoica, and J. E. Gonzalez, *"RAFT: Adapting Language Model to Domain Specific RAG,"* in *Conf. on Language Modeling (COLM 2024)*, OpenReview: `rzQGHXNReU`, 2024.
* **[3]** V. Magesh, F. Surani, M. Dahl, M. Suzgun, C. D. Manning, and D. E. Ho, *"Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools,"* *Journal of Empirical Legal Studies*, vol. 22, pp. 216–242, 2025, doi: `10.1111/jels.12413`.
* **[4]** K.-C. Pai and W.-C. Hsu, *"Fine-tuning small language models for industrial retrieval-augmented generation: Efficiency, factuality, and hallucination analysis,"* *Computer Standards & Interfaces*, vol. 98, p. 104163, 2026, doi: `10.1016/j.csi.2026.104163`.
* **[5]** Y. Kim, *"Detecting jurisdiction compliance gaps in process plant engineering with regulatory RAG,"* *Journal of Loss Prevention in the Process Industries*, vol. 103, p. 106100, 2026, doi: `10.1016/j.jlp.2026.106100`.
* **[6]** R. Rafailov, A. Sharma, E. Mitchell, S. Ermon, C. D. Manning, and C. Finn, *"Direct Preference Optimization: Your Language Model Is Secretly a Reward Model,"* in *Advances in Neural Information Processing Systems (NeurIPS 2023)*, vol. 36, pp. 53728–53741, 2023.
* **[7]** D. Biderman, J. Portes, J. J. G. Ortiz, et al., *"LoRA Learns Less and Forgets Less,"* *Transactions on Machine Learning Research (TMLR)*, 2024.
* **[8]** R. S. Pall, *"IndiaFinBench: An Evaluation Benchmark for Large Language Model Performance on Indian Financial Regulatory Text,"* *arXiv preprint arXiv:2604.19298*, 2026.

---

## 🎓 Academic Details

* **Author:** Varun Gupta  
* **SAP ID:** 60018230100  
* **Program:** Final Year B.Tech. in Artificial Intelligence & Data Science (Sem VII, AY 2026–27)  
* **Course:** Research Ecosystem (DJS23ITELX12) | Department of AI & DS  
* **Institution:** SVKM's Dwarkadas J. Sanghvi College of Engineering (DJSCE), Mumbai, India
