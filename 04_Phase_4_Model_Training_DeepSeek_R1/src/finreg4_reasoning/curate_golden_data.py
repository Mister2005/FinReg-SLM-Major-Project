"""Curate Pristine Single-Document Golden SFT and DPO Datasets for Phase 4."""

import json
import re
from pathlib import Path

ROOT_DIR = Path(r"c:\Users\Varun\Desktop\Main\Sem 7\Major Project")
INPUT_FILE = ROOT_DIR / "Phase 3" / "data" / "sft" / "raft-chat-v2-balanced-500.jsonl"
OUT_DIR = ROOT_DIR / "Phase 4 - Second Approach" / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SFT_OUT = OUT_DIR / "golden_sft_250.jsonl"
DPO_OUT = OUT_DIR / "dpo_pairs_250.jsonl"

def extract_golden_chunk_from_prompt(user_content: str):
    # Splits retrieved chunks and identifies the golden one or returns the single most relevant chunk
    chunk_pattern = re.compile(r"(--- CHUNK \d+ \[([^\]]+)\] ---[\s\S]*?)(?=--- CHUNK \d+|\n\nQUESTION:)", re.MULTILINE)
    matches = list(chunk_pattern.finditer(user_content))
    
    q_match = re.search(r"QUESTION:\s*([\s\S]+?)\s*RESPONSE:", user_content)
    question = q_match.group(1).strip() if q_match else ""
    
    date_match = re.search(r"AS-OF DATE CONTEXT:\s*([^\n]+)", user_content)
    as_of_date = date_match.group(1).strip() if date_match else "2024-01-01"
    
    chunks = [m.group(1).strip() for m in matches]
    return as_of_date, chunks, question

def main():
    print("=== Curating High-Precision Datasets for Phase 4 (Second Approach) ===")
    
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        raw_samples = [json.loads(line) for line in f]
    
    print(f"Loaded {len(raw_samples)} raw samples from {INPUT_FILE}")
    
    sft_records = []
    dpo_records = []
    
    for idx, sample in enumerate(raw_samples[:250]):
        messages = sample["messages"]
        sys_msg = messages[0]["content"]
        user_msg = messages[1]["content"]
        asst_msg = messages[2]["content"].strip()
        skill_type = sample.get("skill_type", "general")
        
        as_of_date, chunks, question = extract_golden_chunk_from_prompt(user_msg)
        
        if not question or not chunks:
            continue
            
        # Single golden chunk isolation (Chunk 1 or identified golden)
        golden_chunk = chunks[0]
        
        # Format Stage 1 Single-Doc User Prompt
        single_doc_user_prompt = (
            f"AS-OF DATE CONTEXT: {as_of_date}\n\n"
            f"RETRIEVED REGULATORY PROVISION:\n"
            f"{golden_chunk}\n\n"
            f"QUESTION: {question}\n\n"
            f"RESPONSE:"
        )
        
        # 1. Clean SFT Record
        sft_entry = {
            "id": f"phase4-sft-{idx:04d}",
            "skill_type": skill_type,
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": single_doc_user_prompt},
                {"role": "assistant", "content": asst_msg}
            ]
        }
        sft_records.append(sft_entry)
        
        # 2. DPO Preference Pair (Chosen vs Rejected)
        # Chosen: Exact grounded answer with citations
        # Rejected: Answer without citations or false refusal
        if "INSUFFICIENT_CORPUS_EVIDENCE" in asst_msg:
            rejected_msg = (
                "Under the applicable regulatory guidelines, entities must comply with all standard "
                "provisions and submit quarterly regulatory disclosures as mandated by the regulator."
            )
        else:
            # Strip citations to create ungrounded rejected completion
            rejected_msg = re.sub(r"\[[^\]]+ / [^\]]+\]", "", asst_msg).strip()
            if not rejected_msg or rejected_msg == asst_msg:
                rejected_msg = (
                    "INSUFFICIENT_CORPUS_EVIDENCE: The retrieved context does not contain sufficient "
                    "details to verify this compliance query."
                )
                
        dpo_entry = {
            "id": f"phase4-dpo-{idx:04d}",
            "system": sys_msg,
            "prompt": single_doc_user_prompt,
            "chosen": asst_msg,
            "rejected": rejected_msg,
        }
        dpo_records.append(dpo_entry)

    # Save SFT records
    with open(SFT_OUT, "w", encoding="utf-8") as f:
        for r in sft_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Saved {len(sft_records)} pristine Stage-1 SFT samples to {SFT_OUT}")

    # Save DPO records
    with open(DPO_OUT, "w", encoding="utf-8") as f:
        for r in dpo_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Saved {len(dpo_records)} Stage-2 DPO preference pairs to {DPO_OUT}")

if __name__ == "__main__":
    main()
