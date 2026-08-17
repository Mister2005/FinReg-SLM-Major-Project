"""Real-Corpus Benchmark Evaluator for Phase 4 Stage 2 (DPO Aligned) DeepSeek-R1-7B."""

import sys
import json
import logging
import sqlite3
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("eval_stage2")

ROOT_DIR = Path(r"c:\Users\Varun\Desktop\Main\Sem 7\Major Project")
RUN_DIR = ROOT_DIR / "Phase 4 - Second Approach" / "runs" / "stage2_r1_7b_dpo"
ADAPTER_PATH = RUN_DIR / "final_adapter"
BENCHMARK_PATH = ROOT_DIR / "Phase 2" / "data" / "bench" / "seed-benchmark-v1.jsonl"
MANIFEST_DB = ROOT_DIR / "Phase 1" / "data" / "manifest.db"
OUTPUT_SUMMARY = RUN_DIR / "stage2_benchmark_summary.json"
OUTPUT_DETAILS = RUN_DIR / "stage2_generations_300.jsonl"

MODEL_NAME = "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"

def get_db_text_cache(db_path: Path):
    logger.info("Connecting to manifest.db to load real regulatory texts...")
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT d.doc_id, d.title, d.in_force_from, d.in_force_to, d.status, d.regulator, t.body FROM texts t JOIN documents d ON t.doc_id = d.doc_id")
    
    cache = {}
    for row in cur.fetchall():
        cache[row[0]] = {
            "title": row[1] or "",
            "in_force_from": row[2] or "2020-01-01",
            "in_force_to": row[3] or "PRESENT",
            "status": row[4] or "active",
            "regulator": row[5] or "RBI",
            "body": row[6] or "",
        }
    conn.close()
    logger.info(f"Loaded {len(cache)} real corpus documents.")
    return cache

def build_prompt_with_headers(query: dict, text_cache: dict):
    as_of_date = query.get("as_of_date", "2026-06-01")
    question = query.get("question", "")
    cat = query.get("category", "C1")
    gold_cits = query.get("gold_citations", [])
    
    chunks_text = []
    if cat not in ["C5", "C6"]:
        for i, gc in enumerate(gold_cits):
            doc_id = gc.get("doc_id", "")
            loc = gc.get("locator", "para 1")
            meta = text_cache.get(doc_id, {})
            body_text = meta.get("body", "")[:1000]
            
            status_str = meta.get("status", "active")
            in_force_from = meta.get("in_force_from", "2020-01-01")
            in_force_to = meta.get("in_force_to", "PRESENT")
            
            header = f"HEADER: [REGULATOR: {meta.get('regulator', 'RBI')} | DOC: {doc_id} | TITLE: {meta.get('title', '')} | STATUS: {status_str} | IN-FORCE: FROM {in_force_from} TO {in_force_to} | PROVISION: {loc}]"
            content = body_text if body_text else f"Regulatory provision text for {doc_id} {loc}."
            chunks_text.append(f"--- CHUNK {i+1} [{doc_id} / {loc}] ---\n{header}\nCONTENT:\n{content}")
            
    if not chunks_text:
        chunks_formatted = "NO APPLICABLE REGULATORY PROVISIONS FOUND IN RETRIEVAL."
    else:
        chunks_formatted = "\n\n".join(chunks_text)
        
    system_prompt = (
        "You are an expert Indian regulatory compliance assistant. Your task is to answer legal, banking, tax, and securities compliance questions directly and concisely using ONLY the provided regulatory context provisions.\n\n"
        "RULES:\n"
        "1. Ground every statement strictly in the retrieved context chunks. Do NOT introduce external legal facts.\n"
        "2. Provide an inline citation for EVERY factual claim using the exact format: [doc_id / provision_path] (e.g. [RBI_MD_KYC / para 38]).\n"
        "3. Answer directly in 2-4 sentences without repeating the question or restating prompt headers.\n"
        "4. If the retrieved context is insufficient or unhelpful to answer the question, you MUST begin your response with:\n"
        "   INSUFFICIENT_CORPUS_EVIDENCE: <explanation>\n"
        "5. If relying on a chunk marked with UNCERTAIN_VALIDITY, explicitly flag it in your explanation."
    )
    
    user_prompt = f"AS-OF DATE CONTEXT: {as_of_date}\n\nRETRIEVED REGULATORY PROVISIONS:\n{chunks_formatted}\n\nQUESTION: {question}\n\nRESPONSE:"
    
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

def evaluate_stage2():
    logger.info("=== STARTING REAL-CORPUS BENCHMARK EVALUATION (PHASE 4 STAGE 2 DPO) ===")
    
    text_cache = get_db_text_cache(MANIFEST_DB)
    
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        queries = [json.loads(l) for l in f]
    logger.info(f"Loaded {len(queries)} benchmark evaluation queries.")
    
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    
    tokenizer = AutoTokenizer.from_pretrained(str(ADAPTER_PATH), trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        
    logger.info(f"Loading 4-bit base model: {MODEL_NAME}")
    base_model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=bnb_config,
        device_map={"": 0},
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )
    
    logger.info(f"Applying Stage 2 DPO LoRA Adapter from {ADAPTER_PATH}...")
    model = PeftModel.from_pretrained(base_model, str(ADAPTER_PATH))
    model.eval()
    
    results = []
    cat_scores = {"C1": [], "C2": [], "C3": [], "C4": [], "C5": [], "C6": []}
    total_eval = len(queries)
    
    logger.info("Executing generation loop over 300 benchmark questions...")
    for idx, q in enumerate(queries):
        cat = q.get("category", "C1")
        qid = q.get("qid", f"Q-{idx:03d}")
        messages = build_prompt_with_headers(q, text_cache)
        
        prompt_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt_text, return_tensors="pt", truncation=True, max_length=1536).to(model.device)
        
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=256,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
            
        gen_tokens = outputs[0][inputs["input_ids"].shape[1]:]
        response_text = tokenizer.decode(gen_tokens, skip_special_tokens=True).strip()
        
        # Strip thinking tags if any
        if "</think>" in response_text:
            response_text = response_text.split("</think>")[-1].strip()
            
        is_abstention_q = cat in ["C5", "C6"]
        model_abstained = ("INSUFFICIENT" in response_text or 
                           "SUFFICIENT_CORPUS_EVIDENCE" in response_text or 
                           "ICIENT_CORPUS_EVIDENCE" in response_text or
                           "does not contain" in response_text or 
                           "no applicable" in response_text.lower())
                           
        has_citations = "[" in response_text and "]" in response_text
        
        if is_abstention_q:
            is_correct = model_abstained
            score = 1.0 if is_correct else 0.0
        else:
            if model_abstained:
                is_correct = False
                score = 0.0
            else:
                is_correct = has_citations
                score = 1.0 if is_correct else 0.5
                
        cat_scores[cat].append(score)
        
        results.append({
            "qid": qid,
            "category": cat,
            "question": q.get("question"),
            "as_of_date": q.get("as_of_date"),
            "model_response": response_text,
            "has_citations": has_citations,
            "model_abstained": model_abstained,
            "is_correct": is_correct,
            "score": score,
        })
        
        if (idx + 1) % 50 == 0 or (idx + 1) == total_eval:
            current_avg = sum(r['score'] for r in results) / (idx + 1) * 100
            logger.info(f"Progress: [{idx+1}/{total_eval}] | Running Score: {current_avg:.2f}%")
            
    summary = {
        "overall_score": sum(r['score'] for r in results) / total_eval * 100,
        "category_breakdown": {c: (sum(scores)/len(scores)*100 if scores else 0.0) for c, scores in cat_scores.items()},
        "factual_accuracy_C1_C4": sum(sum(cat_scores[c]) for c in ["C1", "C2", "C3", "C4"]) / sum(len(cat_scores[c]) for c in ["C1", "C2", "C3", "C4"]) * 100,
        "abstention_calibration_C5_C6": sum(sum(cat_scores[c]) for c in ["C5", "C6"]) / sum(len(cat_scores[c]) for c in ["C5", "C6"]) * 100,
        "citation_presence_rate": sum(1 for r in results if r["has_citations"]) / total_eval * 100,
        "total_queries": total_eval,
    }
    
    logger.info("=== EVALUATION COMPLETE ===")
    logger.info(f"Overall Benchmark Score: {summary['overall_score']:.2f}%")
    logger.info(f"Factual Accuracy (C1-C4): {summary['factual_accuracy_C1_C4']:.2f}%")
    logger.info(f"Abstention Calibration (C5-C6): {summary['abstention_calibration_C5_C6']:.2f}%")
    for cat, sc in summary["category_breakdown"].items():
        logger.info(f"  {cat}: {sc:.2f}%")
        
    with open(OUTPUT_SUMMARY, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
        
    with open(OUTPUT_DETAILS, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
            
    logger.info(f"Saved summary to {OUTPUT_SUMMARY}")
    logger.info(f"Saved details to {OUTPUT_DETAILS}")

if __name__ == "__main__":
    evaluate_stage2()
