"""
High-Throughput Batched Inference of FinReg Stage 2 Aligned DeepSeek-R1-7B on IndiaFinBench.
Batch size = 4 for 4x speedup on consumer GPU.
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("indiafinbench_batched_inference")

ROOT_DIR = Path(r"c:\Users\Varun\Desktop\Main\Sem 7\Major Project")
DATA_PATH = ROOT_DIR / "Benchmarking" / "data" / "indiafinbench_test.jsonl"
MODEL_PATH = ROOT_DIR / "Phase 4 - Second Approach" / "runs" / "stage2_r1_7b_dpo" / "merged"
OUTPUT_DIR = ROOT_DIR / "Benchmarking" / "results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "stage2_r1_7b_indiafinbench_generations.jsonl"

BATCH_SIZE = 4

def main():
    logger.info("=== STARTING BATCHED FINREG-SLM 7B INFERENCE ON INDIAFINBENCH ===")
    
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        items = [json.loads(line) for line in f if line.strip()]
        
    logger.info(f"Total benchmark questions: {len(items)}")
    
    # Load completed items to support resuming seamlessly
    existing_ids = set()
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        existing_ids.add(json.loads(line)["id"])
                    except Exception:
                        pass
        logger.info(f"Found {len(existing_ids)} already completed items. Resuming remaining...")

    items_to_process = [item for item in items if item["id"] not in existing_ids]
    logger.info(f"Remaining items to process: {len(items_to_process)}")

    if not items_to_process:
        logger.info("All items already evaluated! Exiting.")
        return

    logger.info("Loading Stage 2 Aligned DeepSeek-R1-7B Model in 4-bit NF4...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True
    )

    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_PATH), padding_side="left")
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    model = AutoModelForCausalLM.from_pretrained(
        str(MODEL_PATH),
        quantization_config=bnb_config,
        device_map="auto"
    )
    model.eval()

    logger.info(f"Model loaded. Starting batched inference (BATCH_SIZE={BATCH_SIZE})...")
    start_time = time.time()
    
    system_msg = (
        "You are an expert Indian financial regulatory compliance officer. "
        "Carefully reason step-by-step inside <think> ... </think> tags based on the provided regulatory context, "
        "then provide a concise, direct, and legally grounded final answer."
    )

    # Process in batches
    num_batches = (len(items_to_process) + BATCH_SIZE - 1) // BATCH_SIZE

    with open(OUTPUT_FILE, "a", encoding="utf-8") as out_f:
        for b_idx in range(num_batches):
            batch_items = items_to_process[b_idx * BATCH_SIZE : (b_idx + 1) * BATCH_SIZE]
            
            prompts = []
            for item in batch_items:
                context = item.get("context", "")
                question = item.get("question", "")
                user_msg = f"Regulatory Context:\n{context}\n\nQuestion:\n{question}"
                messages = [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ]
                p_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                prompts.append(p_text)

            inputs = tokenizer(prompts, return_tensors="pt", padding=True, truncation=True, max_length=1800).to("cuda")
            input_lens = [len(inputs.input_ids[i]) for i in range(len(batch_items))]

            t0 = time.time()
            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=350,
                    do_sample=False,
                    pad_token_id=tokenizer.pad_token_id
                )
            batch_time = time.time() - t0

            for i, item in enumerate(batch_items):
                gen_tokens = outputs[i][inputs.input_ids.shape[1]:]
                raw_response = tokenizer.decode(gen_tokens, skip_special_tokens=True).strip()

                reasoning = ""
                final_answer = raw_response
                if "<think>" in raw_response and "</think>" in raw_response:
                    parts = raw_response.split("</think>")
                    reasoning = parts[0].replace("<think>", "").strip()
                    final_answer = parts[1].strip()
                elif "<think>" in raw_response:
                    parts = raw_response.split("<think>")
                    reasoning = parts[1].strip()
                    final_answer = parts[1].strip()

                record = {
                    "id": item["id"],
                    "task_type": item.get("task_type", ""),
                    "difficulty": item.get("difficulty", ""),
                    "source": item.get("source", ""),
                    "source_document": item.get("source_document", ""),
                    "question": item.get("question", ""),
                    "context": item.get("context", ""),
                    "reference_answer": item.get("reference_answer", ""),
                    "model_raw_response": raw_response,
                    "model_reasoning": reasoning,
                    "model_final_answer": final_answer,
                    "generation_time_sec": round(batch_time / len(batch_items), 2),
                    "generated_token_count": len(gen_tokens)
                }

                out_f.write(json.dumps(record) + "\n")

            out_f.flush()
            
            processed_so_far = min((b_idx + 1) * BATCH_SIZE, len(items_to_process))
            elapsed = time.time() - start_time
            rate = processed_so_far / max(elapsed, 0.1)
            logger.info(
                f"Batch [{b_idx + 1}/{num_batches}] | "
                f"Progress: [{processed_so_far}/{len(items_to_process)}] | "
                f"Batch Time: {batch_time:.2f}s | "
                f"Throughput: {rate:.2f} items/s | "
                f"Elapsed: {elapsed:.1f}s"
            )

    logger.info("=== BATCHED INFERENCE COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    main()
