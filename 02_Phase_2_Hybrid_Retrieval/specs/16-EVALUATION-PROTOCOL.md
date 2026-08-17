# 16 — Evaluation Protocol

## Metrics

### Primary

**M1 — Answer correctness.** Three-point scale: correct (2), partially correct (1), incorrect (0). Scored by validated judge; reported as mean normalised score with bootstrap CI.

**M2 — Citation accuracy.** Two components, reported separately because they fail differently:
- *Citation precision:* fraction of cited provisions that actually support the claim they are attached to.
- *Citation recall:* fraction of gold citations the answer includes.

A confidently wrong citation is worse than a missing one in this domain, so precision is the headline of the two.

**M3 — Temporal correctness (C3 only).** Two components:
- *Per-variant accuracy.*
- *Stem consistency:* fraction of stems where every dated variant is correct. This is the metric that catches a system that is right by accident.

**M4 — Abstention quality (C6 and C5).** A 2×2, never collapsed into a single accuracy figure (invariant E10):

| | Answerable | Unanswerable |
|---|---|---|
| **Answered** | scored by M1 | **false answer** — the harmful error |
| **Abstained** | **false abstention** — unhelpful | **correct abstention** |

Report all four cells. Also report **false-premise detection rate** on C5: the fraction where the system explicitly contradicts the premise rather than playing along.

### Secondary

**M5 — Cost per query.** For local arms: measured GPU-seconds converted at a stated cloud rate. For API arms: actual token counts at published prices. State the rate and date used.

**M6 — Latency.** p50 and p95, end to end including retrieval, measured on stated hardware at concurrency 1 and 4.

**M7 — General capability delta.** From `docs/15`. Reported as absolute points lost per suite.

**M8 — Retrieval quality.** Recall@k, MRR, temporal precision. Reported per arm that uses retrieval, since fine-tuning does not change retrieval but the ablations do.

## The judge

**Design.** A frontier model grades each answer against the gold answer and the gold citations, returning a structured verdict with a brief rationale. It sees the question, the gold answer, the gold citations, and the candidate answer — **never which arm produced it**.

**Bias controls, per Zheng et al. (NeurIPS 2023):**
- Arm identity stripped from all inputs.
- Presentation order randomised.
- Answer length is recorded and checked for correlation with score; if verbose answers score systematically higher, report it and consider length-controlled scoring.
- **The judge model family must differ from every arm's model family**, to avoid self-enhancement bias. If a frontier model appears as arm A0 or A5, a different provider's model judges.

**Validation, per invariant E6.** Before any judge score is reported:
1. Human-score a stratified 100-answer sample spanning all arms and categories.
2. Compute Cohen's κ between judge and human.
3. **κ ≥ 0.7 → the judge is used.** 0.6–0.7 → used for M1 only, with the limitation stated prominently. **Below 0.6 → the judge is not used**; scoring reverts to human on a reduced sample, and the reduced power is reported.

Citation precision (M2) is checked **programmatically** against the corpus wherever the citation is machine-resolvable — a cited `doc_id` and provision path either exists and contains the claim, or does not. Do not delegate to a judge what a database join can answer.

## Statistics

**Bootstrap.** 10,000 resamples over questions, 95% percentile intervals, seed recorded. Every reported metric carries its interval.

**Paired comparison.** All arms answer the same questions, so use paired tests. For A4 vs A2 (the headline), report the paired difference with its bootstrap CI and a McNemar test on the binarised correct/incorrect outcome.

**Multiple comparisons.** Six arms means many possible pairs. **Declare in advance that A4 vs A2 and A3 vs A1 are the confirmatory comparisons**; everything else is exploratory and labelled as such. Apply Holm correction within the exploratory family. This declaration goes in the run plan before results are seen.

**What 300 questions can and cannot support.** With n=300 and a baseline accuracy near 0.6, the detectable paired difference at 80% power is roughly 7–9 points. Therefore:
- Differences above ~10 points: reportable as real.
- Differences of 4–10 points: reportable as suggestive, with the interval shown.
- Differences below ~4 points: **report as no detected difference.** Do not describe a 2-point gap as an improvement.

Per-category claims rest on 40–60 questions each and support only large effects. Say so.

## Error analysis

Numbers alone will not tell you what to do next, and the decision in `docs/17` needs the *why*. Hand-classify every A2 and A4 failure into:

| Cause | Meaning | Fix lives in |
|---|---|---|
| Retrieval miss | gold chunk not in top-k | retrieval |
| Retrieval present, ignored | model had it, did not use it | generation / fine-tuning |
| Temporal error | right provision, wrong version | temporal filter |
| Citation fabrication | cited something that does not exist | fine-tuning |
| Computation error | right provision, wrong arithmetic | tooling |
| Wrong abstention | refused an answerable question | fine-tuning calibration |
| Corpus gap | answer genuinely not in Phase 1 corpus | Phase 1 |

**The split between "retrieval miss" and "retrieval present but ignored" is the single most decision-relevant number in Phase 2.** If most failures are retrieval misses, fine-tuning cannot help and effort belongs in retrieval. If most are ignored-context failures, fine-tuning is exactly the right lever. Compute this early — it is available from A2 alone, before the fine-tune exists.

## Reporting

`finreg eval report` emits, from run artefacts only with no hand-entered numbers:
- Six-arm table for M1–M4 with CIs.
- Per-category breakdown with a visible caveat on sample size.
- Abstention 2×2 per arm.
- Judge validation statistics.
- Forgetting deltas per checkpoint.
- Cost/latency with measurement conditions stated.
- Error-cause distribution for A2 and A4.
- The `docs/17` gate evaluation with each threshold marked met or not met.
