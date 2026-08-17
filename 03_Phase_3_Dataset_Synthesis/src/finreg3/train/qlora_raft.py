"""RAFT QLoRA training runner for Qwen 2.5 7B Instruct (T-208, T-209, T-211).

Extends Phase 2's QLoRA config with RAFT-specific parameters:
- Higher LoRA rank (r=32) for behavioral pattern capacity
- Lower learning rate (1e-4) for skill-oriented fine-tuning
- Completion-only loss masking on assistant turns
- MLP target modules for behavioral adaptation
"""

from __future__ import annotations

import json
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path("c:/Users/Varun/Desktop/Main/Sem 7/Major Project/Phase 3/config/raft_train.yaml")
DEFAULT_TRAIN_DATA = Path("c:/Users/Varun/Desktop/Main/Sem 7/Major Project/Phase 3/data/sft/raft-chat-v1.jsonl")
DEFAULT_OUTPUT_DIR = Path("c:/Users/Varun/Desktop/Main/Sem 7/Major Project/Phase 3/runs/raft-qwen2.5-7b")


def load_raft_config(config_path: Path = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Load RAFT training configuration from YAML."""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config


def prepare_raft_training(
    train_data_path: Path = DEFAULT_TRAIN_DATA,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> Dict[str, Any]:
    """Prepare RAFT training configuration and emit manifest (T-208).

    This generates the training manifest and validates the config.
    Actual training execution is done via the CLI or run script (T-209).
    """
    config = load_raft_config(config_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Validate train data exists
    if not train_data_path.exists():
        raise FileNotFoundError(
            f"Training data not found at {train_data_path}. "
            "Run 'finreg3 raft generate' followed by 'finreg3 raft format' first."
        )

    # Count training examples
    with open(train_data_path, "r", encoding="utf-8") as f:
        num_examples = sum(1 for _ in f)

    model_cfg = config.get("model", {})
    lora_cfg = config.get("lora", {})
    train_cfg = config.get("training", {})

    effective_batch = (
        train_cfg.get("per_device_train_batch_size", 1) *
        train_cfg.get("gradient_accumulation_steps", 16)
    )
    steps_per_epoch = num_examples // effective_batch
    total_steps = steps_per_epoch * train_cfg.get("num_train_epochs", 3)

    manifest = {
        "status": "CONFIGURED_READY",
        "phase": "Phase 3 — RAFT Skill-Oriented Fine-Tuning",
        "gpu_target": "RTX 5060 Laptop GPU (8GB VRAM)",
        "model": {
            "model_id": model_cfg.get("model_id", "Qwen/Qwen2.5-7B-Instruct"),
            "load_in_4bit": model_cfg.get("load_in_4bit", True),
            "quant_type": model_cfg.get("quant_type", "nf4"),
        },
        "lora": {
            "r": lora_cfg.get("r", 32),
            "alpha": lora_cfg.get("alpha", 64),
            "target_modules": lora_cfg.get("target_modules", []),
            "dropout": lora_cfg.get("dropout", 0.05),
        },
        "training": {
            "num_examples": num_examples,
            "num_epochs": train_cfg.get("num_train_epochs", 3),
            "effective_batch_size": effective_batch,
            "steps_per_epoch": steps_per_epoch,
            "total_steps": total_steps,
            "learning_rate": train_cfg.get("learning_rate", 1e-4),
            "max_seq_length": train_cfg.get("max_seq_length", 2048),
            "gradient_checkpointing": train_cfg.get("gradient_checkpointing", True),
            "loss_on_completion_only": train_cfg.get("loss_on_completion_only", True),
        },
        "vram_optimization": {
            "4bit_nf4_bitsandbytes": True,
            "paged_adamw_8bit": True,
            "gradient_checkpointing": True,
        },
        "output": {
            "checkpoint_dir": str(output_dir / "checkpoints"),
            "merged_dir": str(output_dir / "merged"),
        },
    }

    manifest_path = output_dir / "raft_train_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"RAFT training manifest written to {manifest_path}")
    logger.info(f"  Model: {manifest['model']['model_id']}")
    logger.info(f"  LoRA rank: {manifest['lora']['r']}, alpha: {manifest['lora']['alpha']}")
    logger.info(f"  Examples: {num_examples}, Epochs: {manifest['training']['num_epochs']}")
    logger.info(f"  Total steps: {total_steps}")
    logger.info(f"  Estimated time: {total_steps * 3 // 60} minutes on RTX 5060")

    return manifest


def run_raft_qlora_training(
    train_data_path: Path = DEFAULT_TRAIN_DATA,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    config_path: Path = DEFAULT_CONFIG_PATH,
    resume_from_checkpoint: bool = True,
) -> Dict[str, Any]:
    """Execute RAFT QLoRA fine-tuning on RTX 5060 GPU (T-209).

    Uses pre-tokenized dataset + BitsAndBytes 4-bit NF4 + PEFT LoRA
    with Qwen2.5-1.5B-Instruct on RTX 5060 GPU (8GB VRAM).
    """
    config = load_raft_config(config_path)
    model_cfg = config.get("model", {})
    lora_cfg = config.get("lora", {})
    train_cfg = config.get("training", {})

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from trl import SFTConfig, SFTTrainer
    from datasets import load_dataset

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA not available! Training requires RTX 5060 GPU.")
    logger.info(f"GPU: {torch.cuda.get_device_name(0)} | VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    model_id = model_cfg.get("model_id", "unsloth/qwen2.5-1.5b-instruct-unsloth-bnb-4bit")
    max_seq_length = train_cfg.get("max_seq_length", 1024)

    # 4-bit NF4 Quantization Config for RTX 5060 (8GB VRAM)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type=model_cfg.get("quant_type", "nf4"),
        bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    logger.info(f"Loading tokenizer: {model_id}")
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True

    logger.info(f"Loading model in 4-bit NF4 quantization on GPU 0: {model_id}")
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb_config,
        device_map={"": 0},  # Force 100% of layers onto RTX 5060 GPU 0
        trust_remote_code=True,
        torch_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(
        model,
        use_gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
    )

    # LoRA Config
    peft_config = LoraConfig(
        r=lora_cfg.get("r", 16),
        lora_alpha=lora_cfg.get("alpha", 32),
        lora_dropout=lora_cfg.get("dropout", 0.05),
        target_modules=lora_cfg.get("target_modules", ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj"]),
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    # Tokenize with completion-only loss masking. Qwen's chat template has no
    # `{% generation %}` marker, so TRL's `assistant_only_loss` can't auto-detect
    # assistant spans; and TRL's own prompt/completion boundary alignment produced
    # Tokenize with completion-only loss masking and guaranteed completion preservation.
    # If the combined prompt + completion exceeds max_seq_length, truncate the
    # prompt context rather than the assistant completion so the model always
    # has non-empty supervisory signal.
    def tokenize_with_completion_mask(example):
        prompt_text = tokenizer.apply_chat_template(
            example["messages"][:-1], tokenize=False, add_generation_prompt=True
        )
        full_text = tokenizer.apply_chat_template(
            example["messages"], tokenize=False, add_generation_prompt=False
        )
        
        p_ids = tokenizer.encode(prompt_text, add_special_tokens=False)
        full_ids = tokenizer.encode(full_text, add_special_tokens=False)
        
        # Assistant token IDs are the suffix of full_ids starting after len(p_ids)
        r_ids = full_ids[len(p_ids):]
        if not r_ids:
            # Fallback if chat template suffix alignment differs
            r_ids = tokenizer.encode(example["messages"][-1]["content"], add_special_tokens=False)

        # Truncate prompt from right if exceeding max_seq_length
        if len(p_ids) + len(r_ids) > max_seq_length:
            avail_prompt_len = max(max_seq_length - len(r_ids), 32)
            p_ids = p_ids[:avail_prompt_len]
            r_ids = r_ids[:max_seq_length - len(p_ids)]

        input_ids = p_ids + r_ids
        labels = [-100] * len(p_ids) + list(r_ids)
        attention_mask = [1] * len(input_ids)

        return {"input_ids": input_ids, "labels": labels, "attention_mask": attention_mask}

    logger.info(f"Loading dataset from {train_data_path}...")
    raw_dataset = load_dataset("json", data_files=str(train_data_path), split="train")
    dataset = raw_dataset.map(tokenize_with_completion_mask, remove_columns=raw_dataset.column_names)
    logger.info(f"Dataset ready: {len(dataset)} examples (completion-only loss masking applied).")

    checkpoint_dir = output_dir / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    training_args = SFTConfig(
        output_dir=str(checkpoint_dir),
        max_length=max_seq_length,
        num_train_epochs=train_cfg.get("num_train_epochs", 3),
        per_device_train_batch_size=train_cfg.get("per_device_train_batch_size", 2),
        gradient_accumulation_steps=train_cfg.get("gradient_accumulation_steps", 4),
        learning_rate=train_cfg.get("learning_rate", 1e-4),
        warmup_steps=10,
        logging_steps=train_cfg.get("logging_steps", 5),
        save_strategy=train_cfg.get("save_strategy", "steps"),
        save_steps=train_cfg.get("save_steps", 50),
        save_total_limit=2,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        optim=train_cfg.get("optim", "paged_adamw_8bit"),
        report_to="none",
        max_grad_norm=0.3,
        seed=42,
        packing=False,
        dataloader_num_workers=0,
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        processing_class=tokenizer,
    )

    # Resume from checkpoint if available
    checkpoint = None
    if resume_from_checkpoint and any(checkpoint_dir.glob("checkpoint-*")):
        checkpoints = sorted(checkpoint_dir.glob("checkpoint-*"))
        checkpoint = str(checkpoints[-1])
        logger.info(f"Resuming from checkpoint: {checkpoint}")
    else:
        logger.info("Starting fresh training.")

    logger.info("=== Starting RAFT QLoRA Training (Qwen2.5-1.5B) on RTX 5060 ===")
    train_result = trainer.train(resume_from_checkpoint=checkpoint)

    logger.info("Saving final LoRA adapter...")
    trainer.save_model(str(output_dir / "final"))
    tokenizer.save_pretrained(str(output_dir / "final"))

    metrics = {
        "train_loss": train_result.training_loss,
        "train_runtime": train_result.metrics.get("train_runtime", 0),
        "train_samples_per_second": train_result.metrics.get("train_samples_per_second", 0),
        "total_steps": train_result.global_step,
    }

    metrics_path = output_dir / "train_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    logger.info(f"Training complete! Loss: {metrics['train_loss']:.4f}")
    logger.info(f"Runtime: {metrics['train_runtime']:.0f}s ({metrics['train_runtime']/60:.1f} min)")
    return metrics





def merge_raft_adapter(
    adapter_path: Path = DEFAULT_OUTPUT_DIR / "final",
    output_path: Path = DEFAULT_OUTPUT_DIR / "merged",
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> Path:
    """Merge LoRA adapter into base model weights for inference (T-211)."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    config = load_raft_config(config_path)
    model_cfg = config.get("model", {})
    raw_model_id = model_cfg.get("model_id", "Qwen/Qwen2.5-3B-Instruct")
    # If using an unsloth 4bit name, map to original HF repo
    if "1.5b" in raw_model_id.lower():
        model_id = "Qwen/Qwen2.5-1.5B-Instruct"
    elif "3b" in raw_model_id.lower():
        model_id = "Qwen/Qwen2.5-3B-Instruct"
    elif "7b" in raw_model_id.lower():
        model_id = "Qwen/Qwen2.5-7B-Instruct"
    else:
        model_id = raw_model_id

    logger.info(f"Loading unquantized base model for merging: {model_id}")
    base_model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
        device_map="cpu",
        trust_remote_code=True,
    )

    logger.info(f"Loading LoRA adapter from: {adapter_path}")
    model = PeftModel.from_pretrained(base_model, str(adapter_path))

    logger.info("Merging adapter into base model...")
    model = model.merge_and_unload()

    output_path.mkdir(parents=True, exist_ok=True)
    try:
        model.save_pretrained(str(output_path), safe_serialization=True)
    except Exception as e:
        logger.warning(f"Standard save_pretrained raised exception ({e}), using safetensors direct export...")
        from safetensors.torch import save_file
        save_file(model.state_dict(), str(output_path / "model.safetensors"))
        model.config.save_pretrained(str(output_path))

    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    tokenizer.save_pretrained(str(output_path))

    logger.info(f"Merged model saved to {output_path}")
    return output_path
