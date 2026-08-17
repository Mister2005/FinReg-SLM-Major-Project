"""Pure Native PyTorch Stage 2 DPO Trainer for DeepSeek-R1-Distill-Qwen-7B (Memory-Optimized)."""

import json
import logging
from pathlib import Path
import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel, prepare_model_for_kbit_training
import bitsandbytes as bnb

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("stage2_dpo_native")

ROOT_DIR = Path(r"c:\Users\Varun\Desktop\Main\Sem 7\Major Project")
DATA_PATH = ROOT_DIR / "Phase 4 - Second Approach" / "data" / "omni_dpo_pairs_350.jsonl"
STAGE1_ADAPTER = ROOT_DIR / "Phase 4 - Second Approach" / "runs" / "stage1_r1_7b_sft" / "final_adapter"
OUTPUT_DIR = ROOT_DIR / "Phase 4 - Second Approach" / "runs" / "stage2_r1_7b_dpo"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL_NAME = "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"
MAX_LENGTH = 1024
BETA = 0.1
LEARNING_RATE = 5e-5
MAX_STEPS = 100
GRAD_ACCUM_STEPS = 2

def get_sequence_logps(model, input_ids, attention_mask, prompt_len):
    outputs = model(input_ids=input_ids, attention_mask=attention_mask)
    logits = outputs.logits[:, :-1, :]
    labels = input_ids[:, 1:]
    
    vocab_size = logits.size(-1)
    token_loss = F.cross_entropy(logits.view(-1, vocab_size), labels.view(-1), reduction="none")
    per_token_logps = -token_loss.view(labels.shape)
    del logits, outputs
    
    loss_mask = attention_mask[:, 1:].clone()
    loss_mask[:, :prompt_len - 1] = 0
    
    seq_logps = (per_token_logps * loss_mask).sum(dim=-1)
    return seq_logps

def main():
    logger.info("=== STARTING MEMORY-OPTIMIZED NATIVE DPO ALIGNMENT (DeepSeek-R1-7B) ===")
    
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    
    tokenizer = AutoTokenizer.from_pretrained(str(STAGE1_ADAPTER), trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f]
    logger.info(f"Loaded {len(records)} preference pairs.")
    
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    
    logger.info(f"Loading 4-bit base model: {MODEL_NAME}")
    base_model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=bnb_config,
        device_map={"": 0},
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )
    base_model.config.use_cache = False
    base_model = prepare_model_for_kbit_training(
        base_model,
        use_gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
    )
    
    logger.info(f"Loading Stage 1 LoRA weights from {STAGE1_ADAPTER}...")
    model = PeftModel.from_pretrained(base_model, str(STAGE1_ADAPTER), is_trainable=True)
    model.enable_input_require_grads()
    model.print_trainable_parameters()
    
    optimizer = bnb.optim.PagedAdamW8bit(model.parameters(), lr=LEARNING_RATE)
    
    logger.info(f"Starting optimized DPO training loop for {MAX_STEPS} optimization steps...")
    model.train()
    
    step = 0
    accum_loss = 0.0
    optimizer.zero_grad()
    
    while step < MAX_STEPS:
        for rec_idx, rec in enumerate(records):
            if step >= MAX_STEPS:
                break
                
            system = rec.get("system", "")
            prompt = rec.get("prompt", "")
            chosen = rec.get("chosen", "")
            rejected = rec.get("rejected", "")
            
            prompt_msgs = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
            prompt_str = tokenizer.apply_chat_template(prompt_msgs, tokenize=False, add_generation_prompt=True)
            prompt_ids = tokenizer.encode(prompt_str, add_special_tokens=False)
            prompt_len = len(prompt_ids)
            
            chosen_ids = tokenizer.encode(chosen, add_special_tokens=False)
            rejected_ids = tokenizer.encode(rejected, add_special_tokens=False)
            
            max_p_len = MAX_LENGTH - max(len(chosen_ids), len(rejected_ids))
            if prompt_len > max_p_len:
                prompt_ids = prompt_ids[-max_p_len:]
                prompt_len = len(prompt_ids)
                
            chosen_seq = torch.tensor([prompt_ids + chosen_ids], device=model.device)
            chosen_mask = torch.ones_like(chosen_seq)
            
            rejected_seq = torch.tensor([prompt_ids + rejected_ids], device=model.device)
            rejected_mask = torch.ones_like(rejected_seq)
            
            # 1. Policy forward pass (adapter enabled)
            pi_chosen_logps = get_sequence_logps(model, chosen_seq, chosen_mask, prompt_len)
            pi_rejected_logps = get_sequence_logps(model, rejected_seq, rejected_mask, prompt_len)
            
            # 2. Reference forward pass (adapter disabled)
            with torch.no_grad():
                with model.disable_adapter():
                    ref_chosen_logps = get_sequence_logps(model, chosen_seq, chosen_mask, prompt_len)
                    ref_rejected_logps = get_sequence_logps(model, rejected_seq, rejected_mask, prompt_len)
                    
            # 3. DPO Loss computation
            pi_logratios = pi_chosen_logps - pi_rejected_logps
            ref_logratios = ref_chosen_logps - ref_rejected_logps
            logits = BETA * (pi_logratios - ref_logratios)
            loss = -F.logsigmoid(logits).mean() / GRAD_ACCUM_STEPS
            
            loss.backward()
            accum_loss += loss.item() * GRAD_ACCUM_STEPS
            
            del chosen_seq, chosen_mask, rejected_seq, rejected_mask
            
            if (rec_idx + 1) % GRAD_ACCUM_STEPS == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                optimizer.zero_grad()
                torch.cuda.empty_cache()
                step += 1
                
                if step % 5 == 0 or step == MAX_STEPS:
                    reward_margin = (pi_logratios - ref_logratios).mean().item()
                    logger.info(f"DPO Step [{step:03d}/{MAX_STEPS}] | Loss: {accum_loss/5:.4f} | Margin: {reward_margin:.4f}")
                    accum_loss = 0.0
                    
    logger.info("=== STAGE 2 DPO ALIGNMENT COMPLETE ===")
    final_adapter_dir = OUTPUT_DIR / "final_adapter"
    model.save_pretrained(str(final_adapter_dir))
    tokenizer.save_pretrained(str(final_adapter_dir))
    logger.info(f"Saved final aligned DPO adapter to {final_adapter_dir}")

if __name__ == "__main__":
    main()
