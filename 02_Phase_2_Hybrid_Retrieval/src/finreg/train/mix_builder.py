"""Dataset mix builder and Invariant E7 overlap assertion test (T-119, T-120)."""

import json
from pathlib import Path
from typing import List, Dict, Any, Set
from finreg.train.sft_generator import SFTDataGenerator
from finreg.train.entailment import SFTEntailmentValidator


def build_sft_dataset(
    db_path: Path,
    exclusion_file: Path,
    output_path: Path,
    target_count: int = 6000
) -> Dict[str, Any]:
    """Generates, validates, and exports SFT dataset with zero benchmark exclusion overlap."""
    generator = SFTDataGenerator(db_path=db_path, exclusion_file=exclusion_file)
    raw_pairs = generator.generate_sft_pairs(target_count=target_count)

    validator = SFTEntailmentValidator()
    valid_pairs, val_stats = validator.validate_pairs(raw_pairs)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for pair in valid_pairs:
            f.write(json.dumps(pair) + "\n")

    return {
        "output_path": str(output_path),
        "total_pairs": len(valid_pairs),
        "validation_stats": val_stats,
    }
