"""
Inference-Enhanced Benchmark Evaluator on IndiaFinBench.

Integrates all 4 enhancement pillars:
1. Cloud BGE Cross-Encoder Context Re-ranking
2. Program-Aided Python REPL Sandbox Execution for Arithmetic
3. DeepSeek-R1-7B CoT Reasoning with <think> Traces
4. Test-Time Verification & Structured Compliance Output

Evaluates against: Benchmarking/data/indiafinbench_test.jsonl (324 questions)
Saves results to:  Benchmarking/results/enhanced_v1_1_indiafinbench_generations.jsonl
"""

import os
import sys
import json
import time
import re
import logging
from pathlib import Path
from typing import Dict, Any, List
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

# Force UTF-8 for console output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("enhanced_benchmark_runner")

ROOT_DIR = Path(r"c:\Users\Varun\Desktop\Main\Sem 7\Major Project")
DATA_PATH = ROOT_DIR / "Benchmarking" / "data" / "indiafinbench_test.jsonl"
MODEL_PATH = ROOT_DIR / "Phase 4 - Second Approach" / "runs" / "stage2_r1_7b_dpo" / "merged"
OUTPUT_DIR = ROOT_DIR / "Benchmarking" / "results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "enhanced_v1_1_indiafinbench_generations.jsonl"

PHASE_5_SRC = ROOT_DIR / "Phase 5 - Inference" / "src"
sys.path.insert(0, str(PHASE_5_SRC))

from rag_engine import RegulatoryRAGEngine
from repl_sandbox import REPLSandbox
from verifier import ComplianceVerifier
from best_of_n_search import TestTimeSearchEngine

def run_enhanced_benchmark(max_items: int = None, use_cloud_reranker: bool = True):
    logger.info("=" * 80)
    logger.info("STARTING FINREG-SLM ENHANCED INFERENCE BENCHMARK ON INDIAFINBENCH")
    logger.info(f"Target Dataset:  {DATA_PATH}")
    logger.info(f"Output File:     {OUTPUT_FILE}")
    logger.info(f"Cloud Reranker:  {use_cloud_reranker}")
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
    logger.info("Initializing RAG Engine, REPL Sandbox, and Verifiers...")
    rag = RegulatoryRAGEngine()
    sandbox = REPLSandbox()
    verifier = ComplianceVerifier(rag)
    search_engine = TestTimeSearchEngine(rag)

    # 4. Load DeepSeek-R1-7B Model in 4-bit NF4
    logger.info(f"Loading Model from: {MODEL_PATH}...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_PATH), trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        str(MODEL_PATH),
        quantization_config=bnb_config,
        device_map={"": 0},
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )
    model.eval()
    logger.info("Model loaded into GPU VRAM successfully.")

    # 5. Process Benchmark Items
    start_total_time = time.time()

    with open(OUTPUT_FILE, "a", encoding="utf-8") as out_f:
        for idx, item in enumerate(items_to_evaluate, 1):
            q_id = item["id"]
            task_type = item.get("task_type", "Regulatory Interpretation")
            question = item.get("question", "")
            raw_context = item.get("context", "")
            ref_ans = item.get("reference_answer", "")

            item_start = time.time()

            # --- Step A: Enhanced RAG / Context Reranking ---
            # If provided context has multiple paragraphs, rerank them via cloud BGE cross-encoder
            passages = [p.strip() for p in raw_context.split("\n\n") if len(p.strip()) > 30]
            if not passages:
                passages = [raw_context]

            if use_cloud_reranker and len(passages) > 1:
                try:
                    from client import CloudBGERerankerClient
                    cloud_client = CloudBGERerankerClient()
                    ranked = cloud_client.rerank(question, passages, top_k=min(3, len(passages)))
                    refined_context = "\n\n".join([r["text"] for r in ranked])
                except Exception as e:
                    refined_context = raw_context
            else:
                refined_context = raw_context

            # --- Step B: Construct Grounded R1 Prompt ---
            system_msg = (
                "You are an expert Indian financial regulatory compliance assistant. "
                "Carefully reason step-by-step inside <think> ... </think> tags based strictly on the provided regulatory context. "
                "For any arithmetic, CRAR calculations, penal tax computations, or day-count deadlines, write verified Python code blocks inside <think>. "
                "Then provide a concise, direct, and legally grounded final answer citing statutory provisions in [doc_id / provision] format."
            )
            user_msg = f"REGULATORY CONTEXT:\n{refined_context}\n\nQUESTION:\n{question}\n\nRESPONSE:"

            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ]

            prompt_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer(prompt_text, return_tensors="pt", truncation=True, max_length=2048).to(model.device)

            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=384,
                    do_sample=False,
                    repetition_penalty=1.12,
                    pad_token_id=tokenizer.pad_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                )

            gen_tokens = outputs[0][inputs["input_ids"].shape[1]:]
            raw_response = tokenizer.decode(gen_tokens, skip_special_tokens=True).strip()

            # --- Step C: Program-Aided Python REPL Execution ---
            repl_executed = False
            repl_output_str = ""
            if "```python" in raw_response:
                code_blocks = re.findall(r"```python(.*?)```", raw_response, re.DOTALL)
                for block in code_blocks:
                    ok, out = sandbox.execute_code(block)
                    if ok:
                        repl_executed = True
                        repl_output_str = out.strip()
                        # If REPL output not in raw_response, inject verification tag
                        if "[REPL Output:" not in raw_response:
                            raw_response = raw_response.replace(
                                f"```python{block}```",
                                f"```python{block}```\n[REPL Output: {repl_output_str}]"
                            )

            # --- Step D: Parse Reasoning & Final Answer ---
            reasoning = ""
            final_answer = raw_response
            if "<think>" in raw_response and "</think>" in raw_response:
                parts = raw_response.split("</think>")
                reasoning = parts[0].replace("<think>", "").strip()
                final_answer = parts[1].strip()
            elif "</think>" in raw_response:
                parts = raw_response.split("</think>")
                reasoning = parts[0].strip()
                final_answer = parts[1].strip()

            # --- Step E: Test-Time Verification Check ---
            verif_score = search_engine.score_candidate(raw_response)
            item_latency = time.time() - item_start

            # Record result
            result_record = {
                "id": q_id,
                "task_type": task_type,
                "question": question,
                "reference_answer": ref_ans,
                "model_raw_response": raw_response,
                "model_reasoning": reasoning,
                "model_final_answer": final_answer,
                "repl_executed": repl_executed,
                "repl_output": repl_output_str,
                "verification_score": verif_score["final_score"],
                "verification_status": verif_score["verification_status"],
                "latency_seconds": round(item_latency, 2),
            }

            out_f.write(json.dumps(result_record, ensure_ascii=False) + "\n")
            out_f.flush()

            if idx % 10 == 0 or idx == len(items_to_evaluate):
                elapsed = time.time() - start_total_time
                qps = idx / elapsed
                logger.info(f"[{idx}/{len(items_to_evaluate)}] Evaluated ({qps:.2f} q/s) | QID: {q_id} | Type: {task_type} | Latency: {item_latency:.2f}s | REPL: {repl_executed}")

    total_elapsed = time.time() - start_total_time
    logger.info(f"Finished evaluating {len(items_to_evaluate)} items in {total_elapsed/60:.2f} minutes.")

if __name__ == "__main__":
    run_enhanced_benchmark(use_cloud_reranker=True)
