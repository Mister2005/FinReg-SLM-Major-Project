# FinReg-SLM Master Model Registry

The **FinReg-SLM Model Registry** provides standardized versioning, checkpoint tracking, and single-line model loading for all fine-tuned regulatory models (RAFT, Stage 1 SFT, Stage 2 DPO).

Each version is self-contained inside `04_Phase_4_Model_Training_DeepSeek_R1/models/Version_X/`.

---

## 1. Directory Structure

```
04_Phase_4_Model_Training_DeepSeek_R1/
├── models/                                      <- Ignored by Git
│   └── Version_1/                               <- Self-contained Version 1 Package
│       ├── merged_fp16/                         <- Full 15.2 GB standalone weights
│       │   ├── model-00001-of-00004.safetensors
│       │   ├── model-00002-of-00004.safetensors
│       │   ├── model-00003-of-00004.safetensors
│       │   ├── model-00004-of-00004.safetensors
│       │   ├── config.json & tokenizer.json
│       │   └── chat_template.jinja
│       │
│       └── adapters/                            <- Lightweight QLoRA adapters
│           ├── stage2_dpo_adapter/              <- 10.1 MB Production DPO adapter
│           └── stage1_sft_adapter/              <- CoT SFT adapter
│
└── model_registry/                              <- Version controller
    ├── MODEL_REGISTRY.json                      <- Links versions to benchmarks & paths
    ├── loader.py                                <- Standalone single-line loader
    └── README.md
```

---

## 2. Quick Start: Loading Version 1

You can load Version 1 without retraining using `loader.py`:

```python
from model_registry.loader import load_registered_model

# Option A: Load Production Baseline in 4-bit NF4 (<5GB VRAM on RTX 5060)
model, tokenizer, metadata = load_registered_model(
    version="v1.0_dpo_baseline",
    load_in_4bit=True,
    device_map="auto"
)

# Option B: Load Full Standalone 16-bit FP16 Merged Model
model, tokenizer, metadata = load_registered_model(
    version="v1.0_dpo_baseline",
    load_in_4bit=False,
    use_merged_weights=True
)
```

---

## 3. Version Catalog & Empirical Scorecard

| Version ID | Version Folder | Base Architecture | Alignment Strategy | G7 Hard Suite | IndiaFinBench (Macro Avg) | Citation Grounding |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| **`v1.0_dpo_baseline`** | `Version_1` | `DeepSeek-R1-Distill-Qwen-7B` | Two-Stage RAFT (SFT + DPO) | **70.71%** | **80.98%** | **99.17%** |
| **`v1.0_sft_stage1`** | `Version_1` | `DeepSeek-R1-Distill-Qwen-7B` | Stage 1 SFT on Golden `<think>` Traces | 68.17% | — | 88.40% |
