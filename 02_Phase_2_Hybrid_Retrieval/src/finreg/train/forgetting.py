"""General capability forgetting harness (T-121, Invariant E8).

REWRITE NOTE (2026-08-15):
Previous implementation used hardcoded scores — completely synthetic.
Now delegates to Phase 3's real capability probe (ARC-C + HellaSwag subset).
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Re-use Phase 3's capability probe logic (avoids duplication)
_P3_EVAL = Path(__file__).parents[5] / "Phase 3" / "src"


class ForgettingHarness:
    """Evaluates general-capability benchmarks (ARC-C, HellaSwag) to track forgetting delta.

    Uses Phase 3's capability_probe module for real evaluation.
    50 items per task, ARC-Challenge + HellaSwag subsets.
    """

    def evaluate_model_capability(
        self, model_identifier: str, checkpoint_path: Optional[str] = None
    ) -> Dict[str, float]:
        """
        Runs standardized capability evaluation suite via Phase 3 capability_probe.
        Returns dictionary of benchmark scores (0.0 to 1.0).
        """
        import sys
        if str(_P3_EVAL) not in sys.path:
            sys.path.insert(0, str(_P3_EVAL))

        try:
            from finreg3.eval.capability_probe import evaluate_capability_subset
            model_path = checkpoint_path if checkpoint_path else model_identifier
            result = evaluate_capability_subset(model_path, n_per_task=50)
            # result keys: arc_challenge, hellaswag, mean_score
            return {
                "arc_challenge": result.get("arc_challenge", 0.0),
                "hellaswag": result.get("hellaswag", 0.0),
                "mean_score": result.get("mean_score", 0.0),
            }
        except Exception as e:
            logger.error(f"ForgettingHarness: real capability probe failed — {e}. "
                         "Returning null scores. DO NOT report these as real results.")
            return {"arc_challenge": 0.0, "hellaswag": 0.0, "mean_score": 0.0}

    def compute_forgetting_delta(
        self, base_scores: Dict[str, float], checkpoint_scores: Dict[str, float]
    ) -> Dict[str, Any]:
        """Computes capability loss delta (Gate G2 evaluation)."""
        delta = {}
        for k in base_scores:
            if k in checkpoint_scores:
                delta[k] = round((checkpoint_scores[k] - base_scores[k]) * 100, 2)

        mean_loss = abs(delta.get("mean_score", 0.0))
        g2_status = (
            "Acceptable (<= 3 pts)" if mean_loss <= 3.0 else
            "Concerning (3-8 pts)" if mean_loss <= 8.0 else
            "Unacceptable (> 8 pts)"
        )

        return {
            "deltas_percentage_points": delta,
            "mean_capability_loss_pts": mean_loss,
            "gate_g2_status": g2_status,
        }
