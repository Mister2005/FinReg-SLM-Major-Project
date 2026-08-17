"""Self-checking entailment validator for SFT training data (T-118)."""

import re
from typing import List, Dict, Any, Tuple


class SFTEntailmentValidator:
    """Validates that generated SFT target answers are grounded in provided contexts."""

    def validate_pairs(self, sft_pairs: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        valid_pairs = []
        rejected_count = 0

        for pair in sft_pairs:
            context = pair.get("context", "").lower()
            response = pair.get("response", "").lower()

            # Extract substantive words from response
            words = set(re.findall(r'\b[a-zA-Z0-9]{4,}\b', response))
            if not words:
                valid_pairs.append(pair)
                continue

            matched = [w for w in words if w in context]
            overlap_ratio = len(matched) / len(words)

            if overlap_ratio >= 0.15:
                valid_pairs.append(pair)
            else:
                rejected_count += 1

        total = len(sft_pairs)
        discard_rate = (rejected_count / total) if total > 0 else 0.0

        return valid_pairs, {
            "total_input": total,
            "valid_count": len(valid_pairs),
            "rejected_count": rejected_count,
            "discard_rate": round(discard_rate, 4)
        }
