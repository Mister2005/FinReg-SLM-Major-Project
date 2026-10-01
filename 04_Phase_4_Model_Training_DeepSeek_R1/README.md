# 04. Phase 4 — Two-Stage Model Training & Alignment (DeepSeek-R1-7B)

### Overview
Phase 4 executes the two-stage domain alignment on `DeepSeek-R1-Distill-Qwen-7B` using 4-bit NormalFloat4 (NF4) QLoRA under an 8GB consumer GPU budget (as well as scalable Kaggle Cloud GPU execution).

### Notebooks & Execution
* **`notebooks/finreg-slm-flagship-training.ipynb`**: Complete end-to-end Jupyter notebook for training the FinReg Flagship adapter on cloud GPU, combining Stage 1 RAFT SFT and Stage 2 Epistemic Margin-DPO.

### Stage 1: Retrieval-Augmented Fine-Tuning (SFT)
* **Configuration**: Rank 64, Alpha 128, all 7 projection matrices (`q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`).
* **Target Data**: 1,200 curated Indian financial regulatory reasoning traces (RBI Master Directions, SEBI Circulars, PMLA).
* **Outcome**: Taught the model to generate structured `<think>` reasoning before outputting statutory answers, achieving 90.5% core compliance.

### Stage 2: Direct Preference Optimization (DPO)
* **Configuration**: Fused-kernel native DPO with beta=0.1, trained directly on the 257 preference pairs.
* **Outcome**: Completely eliminated sycophancy, boosting citation grounding from 88.4% -> 99.17% and epistemic refusal from 0.0% -> 82.50%.

