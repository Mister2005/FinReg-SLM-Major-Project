"""Fast programmatic exact-match & keyword containment evaluator for IndiaFinBench."""

import json
import re
from pathlib import Path

GEN_PATH = Path(r"Benchmarking/results/stage2_r1_7b_indiafinbench_generations.jsonl")

def normalize_text(text):
    text = text.lower()
    text = re.sub(r"[^\w\s\d\.\%\₹]", " ", text)
    return " ".join(text.split())

def main():
    rows = [json.loads(line) for line in GEN_PATH.read_text(encoding="utf-8").strip().split("\n") if line.strip()]
    
    # Deduplicate by ID
    unique_rows = {}
    for r in rows:
        unique_rows[r["id"]] = r
        
    print(f"Total Unique Samples: {len(unique_rows)}")
    
    task_scores = {}
    source_scores = {}
    
    total_exact = 0
    total_substring = 0
    
    for item_id, item in unique_rows.items():
        ref = normalize_text(item.get("reference_answer", ""))
        ans = normalize_text(item.get("model_final_answer", "") or item.get("model_raw_response", ""))
        
        is_exact = (ref == ans)
        is_sub = (ref in ans) or any(part in ans for part in ref.split(" and ") if len(part) > 3)
        
        t_type = item.get("task_type", "unknown")
        src = item.get("source", "unknown")
        
        if t_type not in task_scores:
            task_scores[t_type] = {"total": 0, "correct": 0}
        if src not in source_scores:
            source_scores[src] = {"total": 0, "correct": 0}
            
        task_scores[t_type]["total"] += 1
        source_scores[src]["total"] += 1
        
        if is_sub:
            task_scores[t_type]["correct"] += 1
            source_scores[src]["correct"] += 1
            total_substring += 1
        if is_exact:
            total_exact += 1
            
    print("==================================================================")
    print("      INDIAFINBENCH DETERMINISTIC STRING CONTAINMENT SCORES       ")
    print(f"   Overall Substring Match Accuracy: {total_substring / len(unique_rows) * 100:.2f}%")
    print(f"   Strict Exact Match Accuracy     : {total_exact / len(unique_rows) * 100:.2f}%")
    print("==================================================================")
    print("Task Breakdown:")
    for t, data in task_scores.items():
        print(f"   {t:25s}: {data['correct'] / data['total'] * 100:.2f}% ({data['correct']}/{data['total']})")
    print("Source Breakdown:")
    for s, data in source_scores.items():
        print(f"   {s:10s}: {data['correct'] / data['total'] * 100:.2f}% ({data['correct']}/{data['total']})")

if __name__ == "__main__":
    main()
