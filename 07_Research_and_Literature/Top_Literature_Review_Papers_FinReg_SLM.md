# Top 8 Core Literature Review Papers: Methodology, Research Gaps, and Empirical Fixes

**Project:** FinReg-SLM (Domain-Specialized Small Language Model for Indian Financial Compliance)  
**Author:** Varun Gupta (UID: 2022300055)  
**Institution:** SVKM's NMIMS, MPSTME, Department of AI & DS  
**Date:** August 17, 2026  

---

## Executive Overview

This document details the eight most foundational, peer-reviewed literature sources that ground FinReg-SLM's six research gaps, architectural decisions, alignment strategy, and empirical benchmark evaluations.

---

## 1. Fine-Tuning or Retrieval? Comparing Knowledge Injection in LLMs
**Authors:** O. Ovadia, M. Brief, M. Mishaeli, and O. Elisha  
**Venue & Index:** Proceedings of the 2024 Conference on Empirical Methods in Natural Language Processing (EMNLP 2024), pp. 237–250 (*Scopus / ACL Anthology (Main Conference)*, 2024)  

### 🔬 Experimental Methodology
Conducted extensive empirical comparisons between RAG and unsupervised fine-tuning across synthetic and real-world knowledge extraction tasks.

### 📊 Key Empirical Findings
RAG consistently outperforms unsupervised fine-tuning for factual knowledge injection. Fine-tuned models suffer from the 'Reversal Curse' (inability to infer A -> B if trained on B -> A).

### ❌ Identified Research Gap
Proves that fine-tuning alone is insufficient for changing factual knowledge, but does not explore how fine-tuning can be combined with RAG to teach structured reasoning over complex regulatory syntax.

### 🛠️ FinReg-SLM Concrete Architectural Fix
We implemented Two-Stage RAFT (Retrieval-Augmented Fine-Tuning) where the 7B model is trained on golden regulatory chunks mixed with distractor circulars, forcing explicit <think> CoT deduction.

### 🚀 Measured Empirical Score Gain
**Core Statutory Compliance (C1–C3) jumped from 62.3% to 94.43% on G7; IndiaFinBench Regulatory Interpretation scored 90.29%.**

---

## 2. RAFT: Adapting Language Model to Domain Specific RAG
**Authors:** T. Zhang, S. G. Patil, N. Jain, S. Shen, M. Zaharia, I. Stoica, and J. E. Gonzalez  
**Venue & Index:** Conference on Language Modeling (COLM 2024), OpenReview: rzQGHXNReU (*Peer-Reviewed Core AI Conference*, 2024)  

### 🔬 Experimental Methodology
Formulated RAFT by training models to answer questions using golden documents surrounded by distractor documents, supervising step-by-step reasoning and verbatim citation extraction.

### 📊 Key Empirical Findings
RAFT trains the model to act as an open-book test taker: identifying the relevant passage, discarding irrelevant distractors, and citing source evidence verbatim.

### ❌ Identified Research Gap
Validated exclusively on PubMed, HotpotQA, and Gorilla API datasets; did not evaluate on multi-agency financial regulatory text where documents partially amend or contradict each other.

### 🛠️ FinReg-SLM Concrete Architectural Fix
Extended the RAFT paradigm to Indian financial regulations (SEBI & RBI), generating 257 golden CoT traces containing multi-hop statutory deductions and distractor filtering.

### 🚀 Measured Empirical Score Gain
**Multi-Hop Regulatory Synthesis (C2) improved by +40.44% (from 54.0% to 94.44% on G7).**

---

## 3. Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools
**Authors:** V. Magesh, F. Surani, M. Dahl, M. Suzgun, C. D. Manning, and D. E. Ho  
**Venue & Index:** Journal of Empirical Legal Studies, vol. 22, pp. 216–242 (*Wiley / Scopus Q1*, 2025)  

### 🔬 Experimental Methodology
Conducted the first pre-registered empirical benchmark auditing leading commercial legal AI tools (Lexis+ AI, Westlaw AI-Assisted Research, Ask Practical Law AI) across 200+ complex legal inquiries.

### 📊 Key Empirical Findings
Hallucination rates ranged from 17% to 33% despite retrieval grounding. Models frequently hallucinated case citations, misquoted statutory provisions, and exhibited strong sycophancy on false premises.

### ❌ Identified Research Gap
Audited closed commercial tools without providing an open-weights architectural fix for hallucination and sycophancy in statutory compliance.

### 🛠️ FinReg-SLM Concrete Architectural Fix
Introduced automated verbatim citation verification and Stage 2 DPO preference loss, penalizing ungrounded circular citations and rewarding explicit epistemic abstention.

### 🚀 Measured Empirical Score Gain
**Citation Grounding increased from 51.6% to 99.17%; phantom citation rate was reduced to 0.0%.**

---

## 4. Fine-Tuning Small Language Models for Industrial Retrieval-Augmented Generation: Efficiency, Factuality, and Hallucination Analysis
**Authors:** K.-C. Pai and W.-C. Hsu  
**Venue & Index:** Computer Standards & Interfaces, vol. 98, Article 104163 (*Elsevier / Scopus Q1*, 2026)  

### 🔬 Experimental Methodology
Fine-tuned small LLMs (1.5B–8B parameters) with QLoRA on industrial RAG logs and developed a 5-category regulatory hallucination taxonomy validated against 154 human-evaluated samples.

### 📊 Key Empirical Findings
Factual correctness on internal regulatory documents (mean 0.488) is substantially harder than customer-service RAG (mean 0.661). Small models require targeted negative supervision to prevent fabrication.

### ❌ Identified Research Gap
Analyzed industrial corporate guidelines without addressing statutory versioning, legislative amendments, or multi-agency regulatory overlaps.

### 🛠️ FinReg-SLM Concrete Architectural Fix
Utilized 4-bit QLoRA on DeepSeek-R1-7B with a 6-category failure taxonomy (C1–C6), specifically training for cross-regulatory overlaps and numeric threshold compliance.

### 🚀 Measured Empirical Score Gain
**Cross-Regulatory Overlap (C3) achieved 96.67% compliance; 100.0% structural protocol conformance.**

---

## 5. Detecting Jurisdiction Compliance Gaps in Process Plant Engineering with Regulatory RAG
**Authors:** Y. Kim  
**Venue & Index:** Journal of Loss Prevention in the Process Industries, vol. 103, Article 106100 (*Elsevier / Scopus Q1*, 2026)  

### 🔬 Experimental Methodology
Indexed 1,327 statutory documents in a local SQLite FTS5 database and deployed a localized small model (Qwen-4B) via Ollama to detect compliance violations against local safety regulations.

### 📊 Key Empirical Findings
Localized, on-premises SLM RAG increased detection of jurisdiction-specific compliance violations from 0/60 to 26/60 compared to generic international baselines.

### ❌ Identified Research Gap
Focused on single-regulator industrial engineering norms without addressing temporal amendment tracking or epistemic refusal.

### 🛠️ FinReg-SLM Concrete Architectural Fix
Built a multi-agency SQLite WAL index of 18,242 Indian regulatory circulars with `effective_date` metadata filtering and reciprocal rank fusion ($k=60$).

### 🚀 Measured Empirical Score Gain
**Contradiction Detection on IndiaFinBench achieved 79.00%; Temporal Reasoning achieved 75.78%.**

---

## 6. Direct Preference Optimization: Your Language Model Is Secretly a Reward Model
**Authors:** R. Rafailov, A. Sharma, E. Mitchell, S. Ermon, C. D. Manning, and C. Finn  
**Venue & Index:** Advances in Neural Information Processing Systems (NeurIPS 2023), vol. 36, pp. 53728–53741 (*NeurIPS / Scopus Indexed*, 2023)  

### 🔬 Experimental Methodology
Derived an exact closed-form solution to the constrained RLHF problem, optimizing policy parameters directly on pairwise preference data $(x, y_w, y_l)$ using binary cross-entropy loss without training a separate reward model.

### 📊 Key Empirical Findings
DPO achieves superior or equivalent alignment to PPO while being computationally stable, memory-efficient, and free from reinforcement learning hyperparameter collapse.

### ❌ Identified Research Gap
General-domain preference alignment focuses on helpfulness and harmlessness, leaving legal precision, statutory citation grounding, and epistemic refusal unaddressed.

### 🛠️ FinReg-SLM Concrete Architectural Fix
Constructed 257 domain-specific DPO preference pairs containing subtle legal hallucination traps, sycophancy counters, and out-of-scope refusal targets.

### 🚀 Measured Empirical Score Gain
**Epistemic Abstention Quality (C5) increased from 0.0% to 82.50%; False Premise Rejection (C6) increased from 0.0% to 58.00%.**

---

## 7. LoRA Learns Less and Forgets Less / Catastrophic Forgetting in LLMs
**Authors:** D. Biderman et al. (TMLR 2024) / Y. Luo et al. (EMNLP 2023)  
**Venue & Index:** Transactions on Machine Learning Research (TMLR 2024) / EMNLP 2023, pp. 8934–8947 (*TMLR / EMNLP Main Conference*, 2023-2024)  

### 🔬 Experimental Methodology
Audited catastrophic forgetting across 1B–7B models under full-parameter fine-tuning vs. parameter-efficient fine-tuning (LoRA).

### 📊 Key Empirical Findings
Full fine-tuning significantly degrades out-of-domain reasoning and instruction following. LoRA exhibits a Pareto-optimal trade-off: preserving base capabilities while adapting domain representations.

### ❌ Identified Research Gap
Identified the forgetting trade-off but did not optimize LoRA rank and target module selection for dual CoT reasoning and strict ChatML token supervision in legal compliance.

### 🛠️ FinReg-SLM Concrete Architectural Fix
Configured all-linear QLoRA (Rank 64, Alpha 128) across all 7 projection matrices (`q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`) in 4-bit NF4.

### 🚀 Measured Empirical Score Gain
**Maintained 100.0% structural protocol conformance and zero ChatML tag degradation on 8GB consumer GPU.**

---

## 8. IndiaFinBench: An Evaluation Benchmark for Large Language Model Performance on Indian Financial Regulatory Text
**Authors:** Rajveer Singh Pall  
**Venue & Index:** arXiv preprint arXiv:2604.19298, Repository: Rajveer-code/IndiaFinBench (*First Standardized Indian Financial NLP Benchmark*, 2026)  

### 🔬 Experimental Methodology
Curated 406 expert-annotated QA pairs from 192 primary SEBI and RBI documents (1992–2026) across 4 tasks: Regulatory Interpretation, Numerical Reasoning, Contradiction Detection, and Temporal Reasoning.

### 📊 Key Empirical Findings
Evaluated 12 zero-shot models; 7B base models score ~76% (Tier 2), non-specialist humans score 69%, while cloud frontier models score 88%–89.7% (Tier 1). Numerical reasoning is the most discriminative task (35.9% spread).

### ❌ Identified Research Gap
Provided the evaluation benchmark but did not develop an open-weights fine-tuned small language model to bridge the gap between 7B base models and frontier cloud APIs.

### 🛠️ FinReg-SLM Concrete Architectural Fix
We evaluated our final Stage 2 Aligned DeepSeek-R1-7B model zero-shot on the official 324-question test split using an automated 70B LLM judge.

### 🚀 Measured Empirical Score Gain
**FinReg-SLM achieved 80.98% macro accuracy (90.29% on Regulatory Interpretation), outperforming open-source Base 7B/8B LLMs by +3.4% to +5.0%.**

---
