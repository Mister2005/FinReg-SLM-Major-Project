# 17 — Decision Gates

**This is the most important document in Phase 2, and it must be read and agreed before any results exist.** Thresholds set after seeing results are not thresholds; they are rationalisations.

Print this. Show it to your guide. Get agreement now.

## Preconditions — no gate is evaluated unless all hold

| # | Condition | Why |
|---|---|---|
| P1 | Benchmark frozen and tagged before any arm ran | Otherwise every number is suspect |
| P2 | Judge validated at κ ≥ 0.6, with the value reported | Otherwise the scores are unmeasured |
| P3 | Retrieval Recall@8 ≥ 0.70 | Below this, generation cannot succeed and arms measure retrieval failure, not model quality |
| P4 | Zero `doc_id` overlap between SFT data and benchmark gold citations, test-asserted | Otherwise A4 is contaminated |
| P5 | All six arms run with identical prompts and decoding | Otherwise arms are not comparable |
| P6 | Forgetting measured before and after training | Otherwise capability cost is unknown |

**If P3 fails, do not proceed to the fine-tune.** Fix retrieval. This is the most likely precondition to fail and the cheapest to fix.

## The primary gate

**G1 — Does fine-tuning beat retrieval alone?**

Compare **A4 (fine-tuned + retrieval)** against **A2 (base + retrieval)**, paired, on M1 answer correctness and M2 citation precision.

| Result | Reading |
|---|---|
| A4 − A2 ≥ +10 points on M1, CI excludes zero | **Clear win** |
| A4 − A2 between +4 and +10, CI excludes zero | **Modest win** |
| A4 − A2 within ±4, or CI includes zero | **No detected difference** |
| A4 − A2 ≤ −4, CI excludes zero | **Fine-tuning hurts** |

**G2 — Capability cost.** M7 general-capability delta.

| Result | Reading |
|---|---|
| Loss ≤ 3 points mean across suites | Acceptable |
| Loss 3–8 points | Concerning — mitigate before proceeding |
| Loss > 8 points | Unacceptable at this configuration |

**G3 — Did fine-tuning inject knowledge?** A3 vs A1, without retrieval. The literature predicts a small effect. Confirming that on Indian regulatory data is a reportable contribution either way, and it is not a gate that can fail the project — it is a measurement.

## The four outcomes

Exactly one applies. Each has a pre-committed Phase 3.

---

### Outcome 1 — Fine-tuning wins
*G1 clear or modest win, G2 acceptable.*

**Phase 3:** Scale up. Expand the benchmark to 1,000+ questions with expert annotation. Run the Llama 3.1 8B confirmation. Explore continued pretraining on the full corpus. Full ablation suite. Target the RegNLP workshop.

**The paper writes itself:** domain fine-tuning improves retrieval-grounded compliance QA on Indian regulatory text, with quantified capability cost.

---

### Outcome 2 — Retrieval alone is sufficient
*G1 shows no detected difference.*

**This is the most likely outcome, and it is a good one.** It replicates Ovadia et al. in a new jurisdiction and domain — a genuine, publishable contribution.

**Phase 3 pivots to retrieval:** the temporal-versioning ablation becomes the headline (it will likely be the largest effect in the whole study), plus better chunking for amendment chains, cross-document synthesis, and hybrid retrieval tuning. Fine-tuning is reported as a measured null result.

**Reframe the project as:** *a version-aware retrieval system and benchmark for Indian regulatory compliance QA, with a controlled negative result on domain fine-tuning.* This is a stronger paper than a marginal positive result, and examiners respect a well-measured null far more than a suspiciously convenient win.

**Do not** respond to this outcome by hyperparameter-hunting until fine-tuning wins. That is invariant E9.

---

### Outcome 3 — Fine-tuning wins but costs too much capability
*G1 win, G2 unacceptable.*

**Phase 3:** Mitigation study. Compare replay ratios, lower LoRA rank, fewer epochs, elastic weight consolidation. The capability/performance trade-off curve becomes the contribution — it directly extends Biderman et al. into a new domain and is a genuinely interesting result.

---

### Outcome 4 — The corpus or the task is the bottleneck
*P3 fails repeatedly, or error analysis shows corpus gaps dominate.*

**Phase 3 returns to Phase 1:** fill corpus gaps, improve extraction for the failing categories, revisit chunking. Report honestly which regulators and question types the corpus cannot currently support.

Unwelcome but valuable — and far better discovered in week four than in week sixteen.

---

## Secondary readings worth recording regardless of outcome

- **A5 − A2 small?** Frontier advantage is modest; the small-model cost argument is strong. Lead with it.
- **A0 already high?** The corpus adds less than assumed. Investigate whether questions are too easy or leaked, and say so.
- **Temporal ablation large?** This is the novelty axis paying off. Make it the headline whatever else happens.
- **Failures dominated by "retrieval present but ignored"?** Fine-tuning is the right lever even if this round's fine-tune underperformed — worth one more configured attempt.
- **Failures dominated by retrieval misses?** No fine-tune will fix this. Move effort to retrieval.

## Recording the decision

On resolution, write `reports/phase2-decision.md` containing: which outcome, every gate value with its interval, the preconditions status, the error-cause distribution, and the agreed Phase 3 scope. Have your guide sign off on it.

This document is what protects you at the final viva. When an examiner asks why you did not simply train a bigger model, the answer is a pre-registered threshold and a measured result — not an opinion formed after the fact.
