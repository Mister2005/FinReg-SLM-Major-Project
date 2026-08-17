"""Freeze procedure and benchmark exclusion set export (T-106)."""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Set, Dict, Any
from finreg.bench.schema import BenchmarkQuestionRecord
from finreg.bench.validator import validate_benchmark_file


def compute_file_sha256(file_path: Path) -> str:
    """Computes SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def freeze_benchmark(
    benchmark_path: Path,
    output_dir: Path,
    db_path: Path
) -> Dict[str, Any]:
    """Freezes benchmark file: validates, computes SHA-256, exports excluded_doc_ids.json and freeze_manifest.json."""
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    val_result, records = validate_benchmark_file(
        benchmark_path=benchmark_path,
        db_path=db_path,
        enforce_target_counts=True
    )

    if not val_result.is_valid:
        raise ValueError(
            f"Cannot freeze benchmark: Validation failed with {len(val_result.errors)} errors:\n" +
            "\n".join(val_result.errors)
        )

    file_sha256 = compute_file_sha256(benchmark_path)

    # Collect excluded doc_ids from gold citations
    excluded_doc_ids: Set[str] = set()
    for rec in records:
        for citation in rec.gold_citations:
            if citation.doc_id:
                excluded_doc_ids.add(citation.doc_id)

    excluded_list = sorted(list(excluded_doc_ids))

    # Export excluded_doc_ids.json
    exclusion_path = output_dir / "excluded_doc_ids.json"
    with open(exclusion_path, "w", encoding="utf-8") as f:
        json.dump({
            "benchmark_sha256": file_sha256,
            "freeze_date": datetime.now().isoformat(),
            "excluded_doc_ids": excluded_list,
            "total_excluded_docs": len(excluded_list)
        }, f, indent=2)

    # Export freeze_manifest.json
    manifest_path = output_dir / "freeze_manifest.json"
    manifest_data = {
        "benchmark_file": benchmark_path.name,
        "sha256": file_sha256,
        "tag": "bench-v1",
        "freeze_date": datetime.now().isoformat(),
        "total_records": len(records),
        "total_excluded_docs": len(excluded_list),
        "category_counts": val_result.category_counts,
        "regulator_counts": val_result.regulator_counts,
        "excluded_doc_ids_file": exclusion_path.name,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    return manifest_data


def assert_sft_exclusion_safety(sft_doc_ids: Set[str], exclusion_file_path: Path) -> bool:
    """Assertion test for CI and SFT generator to verify zero overlap with excluded_doc_ids.json (Invariant E7)."""
    if not exclusion_file_path.exists():
        raise FileNotFoundError(
            f"SFT exclusion check failed: '{exclusion_file_path}' does not exist. Benchmark must be frozen first!"
        )

    with open(exclusion_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    excluded_set = set(data.get("excluded_doc_ids", []))
    overlap = sft_doc_ids.intersection(excluded_set)

    if overlap:
        raise ValueError(
            f"INVARIANT E7 VIOLATION: SFT dataset contains {len(overlap)} document IDs present in benchmark exclusions: {sorted(list(overlap))[:5]}"
        )

    return True
