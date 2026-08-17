"""Export IndiaFinBench dataset to Benchmarking/data/ directory."""

import json
from pathlib import Path
from datasets import load_dataset

BENCH_DIR = Path(r"c:\Users\Varun\Desktop\Main\Sem 7\Major Project\Benchmarking")
DATA_DIR = BENCH_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

print("Loading Rajveer-code/IndiaFinBench from Hugging Face...")
ds = load_dataset("Rajveer-code/IndiaFinBench")

for split_name in ds.keys():
    out_file = DATA_DIR / f"indiafinbench_{split_name}.jsonl"
    split_data = ds[split_name]
    print(f"Exporting {split_name} split ({len(split_data)} records) to {out_file}...")
    with open(out_file, "w", encoding="utf-8") as f:
        for row in split_data:
            f.write(json.dumps(row) + "\n")

print("Export completed successfully!")
