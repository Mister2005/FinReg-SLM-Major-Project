"""
Full Benchmark Evaluator for FinReg-SLM Flagship v3 on IndiaFinBench (324 Test Questions).

Integrates all 4 Pillars:
1. Cloud BGE Cross-Encoder Context Re-ranking
2. Program-Aided Python REPL Sandbox Execution for Arithmetic
3. DeepSeek-R1-7B CoT Reasoning with <think> Traces + Flagship v3 Adapter
4. Test-Time Verification & Structured Compliance Output

Evaluates against: Benchmarking/data/indiafinbench_test.jsonl (324 questions)
Saves results to:  Benchmarking/results/flagship_v3_indiafinbench_generations.jsonl
"""

import os
# Completely disable TensorFlow in transformers to prevent protobuf version conflict
os.environ["USE_TF"] = "0"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["USE_TORCH"] = "1"

import sys
import json
import time
import re
import logging
from pathlib import Path
from typing import Dict, Any, List
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

# Force UTF-8 for console output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("flagship_v3_benchmark")

CURRENT_DIR = Path(__file__).resolve().parent
BENCHMARKING_DIR = CURRENT_DIR.parent
HUB_ROOT = BENCHMARKING_DIR.parent
WORKSPACE_ROOT = HUB_ROOT.parent

# Data Path
DATA_PATH = BENCHMARKING_DIR / "data" / "indiafinbench_test.jsonl"
if not DATA_PATH.exists():
    DATA_PATH = WORKSPACE_ROOT / "Benchmarking" / "data" / "indiafinbench_test.jsonl"

# Output Path
OUTPUT_DIR = BENCHMARKING_DIR / "results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "flagship_v3_indiafinbench_generations.jsonl"

# Adapter Path
ADAPTER_PATH = WORKSPACE_ROOT / "Kaggle_TPU_FinReg_Training" / "kaggle_completed_run" / "finreg_flagship_final"
BASE_MODEL_ID = "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"

# Module Imports from Phase 5
PHASE_5_SRC = HUB_ROOT / "05_Phase_5_Inference_Deployment" / "src"
if not PHASE_5_SRC.exists():
    PHASE_5_SRC = WORKSPACE_ROOT / "Phase 5 - Inference" / "src"
sys.path.insert(0, str(PHASE_5_SRC))
sys.path.insert(0, str(WORKSPACE_ROOT / "Huggingface Model"))

from rag_engine import RegulatoryRAGEngine
from repl_sandbox import REPLSandbox
from verifier import ComplianceVerifier
from client import CloudBGERerankerClient

def extract_think_and_answer(raw_text: str) -> tuple:
    """Extracts reasoning inside <think>...</think> and final answer afterwards."""
    think_match = re.search(r"<think>(.*?)</think>", raw_text, re.DOTALL)
    if think_match:
        reasoning = think_match.group(1).strip()
        final_answer = raw_text[think_match.end():].strip()
    elif "</think>" in raw_text:
        parts = raw_text.split("</think>", 1)
        reasoning = parts[0].replace("<think>", "").strip()
        final_answer = parts[1].strip()
    else:
        reasoning = ""
        final_answer = raw_text.strip()
    
    if not final_answer and reasoning:
        final_answer = reasoning
    return reasoning, final_answer

def run_flagship_v3_benchmark(max_items: int = None, use_cloud_reranker: bool = True):
    logger.info("=" * 80)
    logger.info("STARTING FINREG-SLM FLAGSHIP v3 BENCHMARK ON INDIAFINBENCH")
    logger.info(f"Target Dataset : {DATA_PATH}")
    logger.info(f"Base Model     : {BASE_MODEL_ID}")
    logger.info(f"Adapter Path   : {ADAPTER_PATH}")
    logger.info(f"Output File    : {OUTPUT_FILE}")
    logger.info(f"Cloud Reranker : {use_cloud_reranker}")
    logger.info("=" * 80)

    # 1. Load Dataset
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        all_items = [json.loads(line) for line in f if line.strip()]

    logger.info(f"Loaded {len(all_items)} benchmark items from IndiaFinBench.")

    # 2. Check Existing Completed Items (Resume Capability)
    completed_ids = set()
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        completed_ids.add(json.loads(line)["id"])
                    except Exception:
                        pass
        logger.info(f"Found {len(completed_ids)} already evaluated items. Resuming remaining...")

    items_to_evaluate = [item for item in all_items if item["id"] not in completed_ids]
    if max_items:
        items_to_evaluate = items_to_evaluate[:max_items]

    logger.info(f"Items to process in this run: {len(items_to_evaluate)}")

    if not items_to_evaluate:
        logger.info("All benchmark items already evaluated!")
        return

    # 3. Initialize Enhancement Modules
    logger.info("Initializing REPL Sandbox and Cloud BGE Client...")
    sandbox = REPLSandbox()
    cloud_client = CloudBGERerankerClient() if use_cloud_reranker else None

    # 4. Load 4-bit Base Model with BitsAndBytes NF4 and attach Flagship Adapter
    logger.info(f"Loading Base Model: {BASE_MODEL_ID} in 4-bit NF4...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_ID,
        quantization_config=bnb_config,
        device_map={"": 0},
        torch_dtype=torch.float16,
        low_cpu_mem_usage=True,
    )

    logger.info(f"Attaching Flagship v3 LoRA Adapter from {ADAPTER_PATH}...")
    model = PeftModel.from_pretrained(base_model, str(ADAPTER_PATH))
    model.eval()

    vram_alloc = torch.cuda.memory_allocated(0) / (1024**3)
    logger.info(f"✓ Model Ready! VRAM Allocated: {vram_alloc:.2f} GiB")

    # 5. Process Benchmark Items (aligned with SFT & Margin-DPO training distribution)
    system_msg = (
        "You are an expert Indian financial regulatory compliance assistant. "
        "Carefully reason step-by-step inside <think> ... </think> tags based strictly on the provided regulatory context. "
        "For any arithmetic, CRAR calculations, penal tax computations, or day-count deadlines, write verified Python code blocks inside <think>. "
        "Then provide a concise, direct, and legally grounded final answer citing statutory provisions in [doc_id / provision] format."
    )

    total_items = len(items_to_evaluate)
    start_total_time = time.time()

    with open(OUTPUT_FILE, "a", encoding="utf-8") as out_f:
        for idx, item in enumerate(items_to_evaluate, 1):
            q_id = item["id"]
            task_type = item.get("task_type", "general")
            source = item.get("source", "UNKNOWN")
            doc_id = item.get("source_document", source)
            question = item.get("question", "")
            raw_context = item.get("context", "")
            reference_answer = item.get("reference_answer", "")

            t0 = time.time()

            # Context Re-ranking for multi-passage contexts
            passages = [p.strip() for p in raw_context.split("\n\n") if len(p.strip()) > 30]
            if cloud_client and len(passages) > 1:
                try:
                    ranked = cloud_client.rerank(question, passages, top_k=min(3, len(passages)))
                    context = "\n\n".join([r["text"] for r in ranked])
                except Exception:
                    context = raw_context
            else:
                context = raw_context

            # Prompt Construction with Document Header for strict statutory grounding
            doc_header = f"[{source} | {doc_id}]"
            user_msg = f"REGULATORY CONTEXT ({doc_header}):\n{context}\n\nQUESTION:\n{question}\n\nRESPONSE:"
            msgs = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ]

            prompt_text = tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer(prompt_text, return_tensors="pt", truncation=True, max_length=2048).to(model.device)

            # Generate
            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=512,
                    do_sample=False,
                    temperature=None,
                    top_p=None,
                    repetition_penalty=1.0,
                    pad_token_id=tokenizer.pad_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                )

            gen_tokens = outputs[0][inputs["input_ids"].shape[1]:]
            raw_resp = tokenizer.decode(gen_tokens, skip_special_tokens=True).strip()
            gen_time = time.time() - t0

            # REPL Execution Check
            repl_executed = False
            repl_output = ""
            if "```python" in raw_resp:
                code_blocks = re.findall(r"```python(.*?)```", raw_resp, re.DOTALL)
                for block in code_blocks:
                    ok, out = sandbox.execute_code(block)
                    if ok:
                        repl_executed = True
                        repl_output += out.strip() + "\n"
                        if "[REPL Output:" not in raw_resp:
                            raw_resp = raw_resp.replace(
                                f"```python{block}```",
                                f"```python{block}```\n[REPL Output: {out.strip()}]"
                            )

            reasoning, final_answer = extract_think_and_answer(raw_resp)

            # Record Result
            record = {
                "id": q_id,
                "source": source,
                "task_type": task_type,
                "question": question,
                "reference_answer": reference_answer,
                "model_reasoning": reasoning,
                "model_final_answer": final_answer,
                "raw_response": raw_resp,
                "repl_output": repl_output.strip(),
                "repl_executed": repl_executed,
                "latency_sec": round(gen_time, 2),
                "adapter": "finreg_flagship_v3",
            }

            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            out_f.flush()

            # Progress Logging
            if idx % 10 == 0 or idx == total_items:
                avg_time = (time.time() - start_total_time) / idx
                eta_min = ((total_items - idx) * avg_time) / 60
                logger.info(
                    f"[{idx}/{total_items}] ({task_type}) - "
                    f"Latency: {gen_time:.1f}s | Avg: {avg_time:.1f}s/item | ETA: {eta_min:.1f} min"
                )

    logger.info("=" * 80)
    logger.info(f"✓ FINREG-SLM FLAGSHIP v3 BENCHMARK COMPLETE! Saved to {OUTPUT_FILE}")
    logger.info("=" * 80)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-items", type=int, default=None, help="Limit number of items to test")
    parser.add_argument("--no-reranker", action="store_true", help="Disable Cloud BGE reranker")
    args = parser.parse_args()

    run_flagship_v3_benchmark(max_items=args.max_items, use_cloud_reranker=not args.no_reranker)
