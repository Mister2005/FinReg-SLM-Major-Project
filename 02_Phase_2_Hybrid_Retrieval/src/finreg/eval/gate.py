"""Decision Gate Evaluator and Decision Record generator (T-136, T-137, docs/17)."""

import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
from datetime import datetime


class DecisionGateEvaluator:
    """Evaluates preconditions P1-P6 and gates G1-G3 to resolve Phase 2 to 1 of 4 outcomes."""

    def evaluate_gates(
        self,
        precondition_status: Dict[str, bool],
        a2_m1_score: float,
        a4_m1_score: float,
        g1_ci_excludes_zero: bool,
        capability_loss_pts: float,
        a1_score: float,
        a3_score: float
    ) -> Dict[str, Any]:
        p1_pass = precondition_status.get("P1_benchmark_frozen", False)
        p2_pass = precondition_status.get("P2_judge_validated", False)
        p3_pass = precondition_status.get("P3_recall8_gte_70", False)
        p4_pass = precondition_status.get("P4_zero_sft_overlap", False)
        p5_pass = precondition_status.get("P5_identical_prompts", False)
        p6_pass = precondition_status.get("P6_forgetting_measured", False)

        all_p_pass = p1_pass and p2_pass and p3_pass and p4_pass and p5_pass and p6_pass

        # Primary Gate G1: A4 vs A2
        delta_m1 = (a4_m1_score - a2_m1_score) * 100.0  # Percentage points

        if delta_m1 >= 10.0 and g1_ci_excludes_zero:
            g1_reading = "Clear win"
        elif delta_m1 >= 4.0 and g1_ci_excludes_zero:
            g1_reading = "Modest win"
        elif abs(delta_m1) < 4.0 or not g1_ci_excludes_zero:
            g1_reading = "No detected difference"
        else:
            g1_reading = "Fine-tuning hurts"

        # Gate G2: Capability Cost
        if capability_loss_pts <= 3.0:
            g2_reading = "Acceptable"
        elif capability_loss_pts <= 8.0:
            g2_reading = "Concerning"
        else:
            g2_reading = "Unacceptable"

        # Resolve Outcome (1..4)
        if not p3_pass:
            selected_outcome = "OUTCOME_4"
            outcome_title = "Outcome 4 — The corpus or the task is the bottleneck"
            next_steps = "Phase 3 returns to Phase 1: fill corpus gaps, improve extraction, revisit chunking."
        elif g1_reading in ["Clear win", "Modest win"] and g2_reading == "Acceptable":
            selected_outcome = "OUTCOME_1"
            outcome_title = "Outcome 1 — Fine-tuning wins"
            next_steps = "Scale up in Phase 3. Expand benchmark to 1,000+ questions. Run Llama 3.1 8B confirmation."
        elif g1_reading == "No detected difference":
            selected_outcome = "OUTCOME_2"
            outcome_title = "Outcome 2 — Retrieval alone is sufficient"
            next_steps = "Phase 3 pivots to retrieval: temporal versioning, chunking for amendment chains. Report negative fine-tune result."
        elif g1_reading in ["Clear win", "Modest win"] and g2_reading != "Acceptable":
            selected_outcome = "OUTCOME_3"
            outcome_title = "Outcome 3 — Fine-tuning wins but costs too much capability"
            next_steps = "Phase 3 mitigation study: compare replay ratios, lower LoRA rank, fewer epochs."
        else:
            selected_outcome = "OUTCOME_2"
            outcome_title = "Outcome 2 — Retrieval alone is sufficient"
            next_steps = "Report negative result for domain fine-tuning over retrieval baseline."

        return {
            "preconditions": precondition_status,
            "all_preconditions_met": all_p_pass,
            "gate_g1": {
                "a2_baseline_m1": a2_m1_score,
                "a4_finetuned_m1": a4_m1_score,
                "delta_percentage_points": round(delta_m1, 2),
                "reading": g1_reading
            },
            "gate_g2": {
                "capability_loss_pts": capability_loss_pts,
                "reading": g2_reading
            },
            "gate_g3": {
                "a1_zero_shot": a1_score,
                "a3_finetuned_no_rag": a3_score,
                "knowledge_injection_delta": round((a3_score - a1_score) * 100.0, 2)
            },
            "selected_outcome": selected_outcome,
            "outcome_title": outcome_title,
            "next_steps": next_steps
        }

    def generate_decision_record(self, evaluation_summary: Dict[str, Any], output_path: Path):
        """Generates reports/phase2-decision.md."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        content = f"""# FinReg-SLM Phase 2 Decision Record

**Date:** {datetime.now().strftime('%Y-%m-%d')}

**Status:** RESOLVED

---

## 1. Selected Outcome

### {evaluation_summary['outcome_title']}

**Next Steps:**
{evaluation_summary['next_steps']}

---

## 2. Preconditions Assessment

| Precondition | Description | Status |
|---|---|---|
| P1 | Benchmark frozen before runs | {'PASS' if evaluation_summary['preconditions']['P1_benchmark_frozen'] else 'FAIL'} |
| P2 | Judge validated (kappa >= 0.60) | {'PASS' if evaluation_summary['preconditions']['P2_judge_validated'] else 'FAIL'} |
| P3 | Retrieval Recall@8 >= 0.70 | {'PASS' if evaluation_summary['preconditions']['P3_recall8_gte_70'] else 'FAIL'} |
| P4 | Zero SFT benchmark overlap | {'PASS' if evaluation_summary['preconditions']['P4_zero_sft_overlap'] else 'FAIL'} |
| P5 | Identical prompts across arms | {'PASS' if evaluation_summary['preconditions']['P5_identical_prompts'] else 'FAIL'} |
| P6 | Forgetting measured before/after | {'PASS' if evaluation_summary['preconditions']['P6_forgetting_measured'] else 'FAIL'} |

---

## 3. Decision Gates Evaluation

- **G1 Primary Gate (A4 vs A2):** Delta = {evaluation_summary['gate_g1']['delta_percentage_points']} pts -> **{evaluation_summary['gate_g1']['reading']}**
- **G2 Capability Cost:** Loss = {evaluation_summary['gate_g2']['capability_loss_pts']} pts -> **{evaluation_summary['gate_g2']['reading']}**
- **G3 Knowledge Injection (A3 vs A1):** Delta = {evaluation_summary['gate_g3']['knowledge_injection_delta']} pts
"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
