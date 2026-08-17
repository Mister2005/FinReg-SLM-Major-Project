"""Stage 1 SFT Trainer for DeepSeek-R1-Distill-Qwen-7B using TRL SFTTrainer."""

import os
import sys
import json
import logging
from pathlib import Path
import torch
from datasets import Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTConfig, SFTTrainer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("stage1_sft")

ROOT_DIR = Path(r"c:\Users\Varun\Desktop\Main\Sem 7\Major Project")
DATA_PATH = ROOT_DIR / "Phase 4 - Second Approach" / "data" / "omni_golden_sft_350.jsonl"
OUTPUT_DIR = ROOT_DIR / "Phase 4 - Second Approach" / "runs" / "stage1_r1_7b_sft"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL_NAME = "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"
MAX_SEQ_LENGTH = 1024

def tokenize_with_completion_mask(example, tokenizer, max_length=MAX_SEQ_LENGTH):
    messages = example["messages"]
    prompt_text = tokenizer.apply_chat_template(messages[:-1], tokenize=False, add_generation_prompt=True)
    full_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    
    p_ids = tokenizer.encode(prompt_text, add_special_tokens=False)
    full_ids = tokenizer.encode(full_text, add_special_tokens=False)
    
    asst_ids = full_ids[len(p_ids):] if len(full_ids) >= len(p_ids) else full_ids
    
    max_prompt_len = max_length - len(asst_ids)
    if len(p_ids) > max_prompt_len:
        p_ids = p_ids[-max_prompt_len:]
        
    input_ids = p_ids + asst_ids
    labels = [-100] * len(p_ids) + asst_ids
    attention_mask = [1] * len(input_ids)
    
    return {
        "input_ids": input_ids,
        "labels": labels,
        "attention_mask": attention_mask,
    }

def main():
    logger.info("=== STARTING PHASE 4 STAGE 1 SFT TRAINING (DeepSeek-R1-7B) ===")
    
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f]
    logger.info(f"Loaded {len(records)} pristine single-document training records.")
    
    raw_dataset = Dataset.from_list(records)
    dataset = raw_dataset.map(
        lambda ex: tokenize_with_completion_mask(ex, tokenizer),
        remove_columns=raw_dataset.column_names,
        desc="Applying completion-preserved masking"
    )
    
    active_tokens = sum(sum(1 for l in ex["labels"] if l != -100) for ex in dataset)
    logger.info(f"Verified {active_tokens} active non-zero training labels.")
    
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    
    logger.info(f"Loading 4-bit model: {MODEL_NAME}")
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=bnb_config,
        device_map={"": 0},
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(
        model,
        use_gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
    )
    
    # Q and V only defensive LoRA
    peft_config = LoraConfig(
        r=8,
        lora_alpha=16,
        target_modules=["q_proj", "v_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()
    
    checkpoint_dir = OUTPUT_DIR / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    training_args = SFTConfig(
        output_dir=str(checkpoint_dir),
        max_length=MAX_SEQ_LENGTH,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=2,
        learning_rate=1e-4,
        warmup_steps=20,
        max_steps=250,
        logging_steps=10,
        save_strategy="steps",
        save_steps=100,
        save_total_limit=2,
        bf16=True,
        optim="paged_adamw_8bit",
        report_to="none",
        dataloader_num_workers=0,
    )
    
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        processing_class=tokenizer,
    )
    
    logger.info("Starting Stage 1 SFT training loop...")
    train_result = trainer.train()
    
    logger.info(f"Stage 1 Training Complete. Final Loss: {train_result.training_loss:.4f}")
    trainer.save_model(str(OUTPUT_DIR / "final_adapter"))
    tokenizer.save_pretrained(str(OUTPUT_DIR / "final_adapter"))
    logger.info(f"Saved final adapter to {OUTPUT_DIR / 'final_adapter'}")

if __name__ == "__main__":
    main()
