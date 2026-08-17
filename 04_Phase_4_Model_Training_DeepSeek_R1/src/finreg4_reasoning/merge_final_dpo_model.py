"""Merge Stage 2 DPO LoRA Adapter into DeepSeek-R1-Distill-Qwen-7B base weights."""

import logging
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("merge_final_dpo")

ROOT_DIR = Path(r"c:\Users\Varun\Desktop\Main\Sem 7\Major Project")
RUN_DIR = ROOT_DIR / "Phase 4 - Second Approach" / "runs" / "stage2_r1_7b_dpo"
ADAPTER_PATH = RUN_DIR / "final_adapter"
MERGED_OUTPUT_DIR = RUN_DIR / "merged"
MODEL_NAME = "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"

def main():
    logger.info("=== MERGING STAGE 2 DPO ADAPTER INTO BASE WEIGHTS ===")
    logger.info(f"Adapter Path: {ADAPTER_PATH}")
    logger.info(f"Target Output Directory: {MERGED_OUTPUT_DIR}")
    
    if not ADAPTER_PATH.exists():
        raise FileNotFoundError(f"Adapter path does not exist: {ADAPTER_PATH}")
        
    MERGED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Loading base model in float16 for merge: {MODEL_NAME}")
    base_model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype=torch.float16,
        device_map="cpu",
        low_cpu_mem_usage=True,
        trust_remote_code=True,
    )
    
    tokenizer = AutoTokenizer.from_pretrained(str(ADAPTER_PATH), trust_remote_code=True)
    
    logger.info(f"Loading LoRA weights from {ADAPTER_PATH}...")
    peft_model = PeftModel.from_pretrained(base_model, str(ADAPTER_PATH))
    
    logger.info("Merging LoRA adapter into base model weights...")
    merged_model = peft_model.merge_and_unload()
    
    logger.info(f"Saving merged model to {MERGED_OUTPUT_DIR}...")
    merged_model.save_pretrained(str(MERGED_OUTPUT_DIR), safe_serialization=True, max_shard_size="4GB")
    tokenizer.save_pretrained(str(MERGED_OUTPUT_DIR))
    
    logger.info(f"=== STAGE 2 DPO MERGE COMPLETE: {MERGED_OUTPUT_DIR} ===")

if __name__ == "__main__":
    main()
