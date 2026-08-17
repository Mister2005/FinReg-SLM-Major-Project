"""
FinReg-SLM Standardized Model Loader & Version Resolver.

Provides a unified interface to load any registered model version from
04_Phase_4_Model_Training_DeepSeek_R1/models/Version_X/ without retraining.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("model_registry")

REGISTRY_DIR = Path(__file__).parent
PHASE_4_DIR = REGISTRY_DIR.parent
REGISTRY_FILE = REGISTRY_DIR / "MODEL_REGISTRY.json"

def get_registered_versions() -> Dict[str, Any]:
    """Load the manifest of all registered model versions."""
    if not REGISTRY_FILE.exists():
        raise FileNotFoundError(f"Registry manifest not found at: {REGISTRY_FILE}")
    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_registered_model(
    version: str = "v1.0_dpo_baseline",
    load_in_4bit: bool = True,
    device_map: str = "auto",
    use_merged_weights: bool = True,
) -> Tuple[Any, Any, Dict[str, Any]]:
    """
    Load a registered FinReg-SLM model and tokenizer by version string.
    
    Args:
        version: Version identifier (e.g. 'v1.0_dpo_baseline', 'v1.0_sft_stage1', 'latest').
        load_in_4bit: Whether to load in 4-bit NF4 precision (recommended for 8GB GPU).
        device_map: Device mapping ('auto', 'cuda:0', or 'cpu').
        use_merged_weights: If True and merged weights exist in models/Version_X, loads directly from merged FP16 directory.
        
    Returns:
        (model, tokenizer, metadata)
    """
    registry = get_registered_versions()
    models = registry.get("registered_models", {})
    
    if version == "latest" or version == "default":
        version = registry.get("default_version", "v1.0_dpo_baseline")
        
    if version not in models:
        raise ValueError(f"Version '{version}' not found in registry. Available versions: {list(models.keys())}")
        
    meta = models[version]
    logger.info(f"Loading Registered Model: {meta['display_name']} (Folder: {meta.get('version_folder', 'Version_1')})")
    
    paths = meta.get("storage_paths", {})
    merged_path = Path(paths.get("merged_fp16_abs", ""))
    adapter_path = Path(paths.get("full_adapter_abs", ""))
    
    if use_merged_weights and merged_path.exists():
        target_dir = merged_path
        logger.info(f"Resolved to Standalone Merged Model at: {target_dir}")
    elif adapter_path.exists():
        target_dir = adapter_path
        logger.info(f"Resolved to LoRA Adapter at: {target_dir}")
    else:
        target_dir = PHASE_4_DIR / paths.get("adapter_dir", "")
        logger.info(f"Resolved to Relative Adapter at: {target_dir}")
        
    # 1. Load Tokenizer
    logger.info(f"Loading tokenizer from: {target_dir}")
    tokenizer = AutoTokenizer.from_pretrained(str(target_dir), trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        
    # 2. Configure Quantization
    if load_in_4bit:
        logger.info("Applying BitsAndBytes 4-bit NF4 Quantization (BFloat16 compute)...")
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
        model = AutoModelForCausalLM.from_pretrained(
            str(target_dir),
            quantization_config=bnb_config,
            device_map=device_map,
            trust_remote_code=True,
            torch_dtype=torch.bfloat16,
        )
    else:
        logger.info("Loading in 16-bit Float precision...")
        model = AutoModelForCausalLM.from_pretrained(
            str(target_dir),
            device_map=device_map,
            trust_remote_code=True,
            torch_dtype=torch.float16,
        )
        
    model.eval()
    logger.info(f"Model {version} successfully initialized and ready for inference.")
    return model, tokenizer, meta

if __name__ == "__main__":
    print("=== FinReg-SLM Registry Inspection (Version-1) ===")
    reg = get_registered_versions()
    for v_id, data in reg["registered_models"].items():
        print(f"\n[{v_id}] {data['display_name']}")
        print(f"  Version Folder: {data.get('version_folder', 'Version_1')}")
        print(f"  Base Model:     {data['architecture']['base_model']}")
        print(f"  G7 Score:       {data['empirical_benchmarks'].get('internal_g7_hard_suite', {}).get('overall_judge_score', 'N/A')}%")
        print(f"  IndiaFin:       {data['empirical_benchmarks'].get('india_fin_bench_arxiv_2604_19298', {}).get('overall_macro_avg', 'N/A')}%")
