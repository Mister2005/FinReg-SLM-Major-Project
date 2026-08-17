# 18 — Implementation Plan

Six weeks, five milestones, each with a hard gate. Effort assumes 3–4 focused days per week alongside coursework.

---

## M6 — Benchmark authoring (Week 1, 5 days)

**Build.** All 300 questions per `docs/13`. Schema validator. Freeze tooling. Excluded-`doc_id` extraction.

**Gate M6**
- 300 questions, category and regulator counts match spec.
- Every `gold_citation` resolves to a Phase 1 `doc_id` and the cited text supports the gold answer.
- Second-person verification complete; Cohen's κ computed and ≥ 0.7 (or the weaker single-annotator protocol explicitly disclosed).
- File hashed, committed, tagged `bench-v1`.
- Excluded-`doc_id` set exported and a test asserts SFT generation respects it.

**This is the milestone people rush. Don't.** Every downstream number inherits this file's quality, and unlike code, you cannot fix it later without invalidating results.

---

## M7 — Retrieval baseline (Weeks 2–3, 7 days)

**Build.** Structure-aware chunking, hybrid index, reranker, temporal filter, generation prompt, retrieval-only metrics, arms A1 and A2.

**Gate M7 — this gate can stop the phase**
- **Recall@8 ≥ 0.70** on benchmark gold citations. This is precondition P3.
- Temporal filter demonstrably changes results on C3 (ablation run and recorded).
- A2 produces parseable citations and parseable abstentions on ≥ 95% of questions.
- Retrieval-quality report generated.

**If Recall@8 < 0.70:** stop and fix retrieval. Do not proceed to training. Likely causes in order: chunking splitting provisions, missing header prefixes in embedded text, temporal filter over-excluding, embedding model unsuited to legal register. Budget up to 3 extra days; if it is still failing, that is Outcome 4 territory and worth raising with your guide immediately.

---

## M8 — SFT data and training (Week 4, 5 days)

**Build.** SFT generation pipeline with the validation steps from `docs/15`, exclusion enforcement, QLoRA training, checkpointing with resume, forgetting harness.

**Gate M8**
- ~6,000 validated examples with the specified mix; discard rate recorded.
- Hand-review of 200 random examples complete, error rate reported.
- Zero `doc_id` overlap with benchmark — test passes.
- Base-model forgetting baseline measured **before** training.
- Training completes; loss curves recorded; checkpoints saved.
- Hyperparameter selection made on the validation split, full grid reported.

---

## M9 — Evaluation (Week 5, 5 days)

**Build.** All six arms, judge with bias controls, judge validation against 100 human labels, bootstrap statistics, cost/latency measurement, error-cause classification.

**Gate M9**
- Six arms complete, identical prompts and decoding verified by config diff.
- Judge κ computed; scoring path chosen per `docs/16`.
- All metrics carry bootstrap CIs.
- Error-cause distribution hand-classified for A2 and A4.
- Forgetting deltas at every checkpoint.

**Watch the clock here.** The judge validation requires 100 human-scored answers, which is roughly half a day of concentrated work and is routinely underestimated.

---

## M10 — Decision and write-up (Week 6, 4 days)

**Build.** `finreg eval report`, gate evaluation, `reports/phase2-decision.md`, guide sign-off, Phase 3 scope.

**Gate M10 — Phase 2 exit**
- All preconditions P1–P6 assessed and recorded.
- Gates G1–G3 evaluated with values and intervals.
- Exactly one outcome selected from `docs/17`.
- Phase 3 scope written and agreed.
- Everything reproducible from `runs/`.

---

## Kill criteria

Stop and escalate to your guide rather than pushing through:

| Trigger | Why it matters |
|---|---|
| Recall@8 still < 0.60 after 3 extra days | Corpus or chunking problem, not a model problem |
| Judge κ < 0.6 and human scoring infeasible at scale | Reduce to a 150-question human-scored subset and report reduced power |
| Benchmark authoring not done by end of Week 2 | Cut to 200 questions (keep C3, C5, C6 proportions) rather than compressing verification |
| Training will not fit available compute | Drop to a 3B base model and state it; a clean 3B result beats an unfinished 7B one |
| Any precondition unfixable | Declare Outcome 4 and pivot — this is a legitimate result, not a failure |

## If you fall behind

Cut in this order:
1. The Llama 3.1 8B confirmation run (nice-to-have).
2. Arms A0 and A5 (frontier comparisons) — keep A5 if at all possible, since the cost argument needs it.
3. Benchmark from 300 to 200 questions — **never below 200**, and never by dropping C3, C5 or C6.
4. Hyperparameter grid to a single declared configuration.

Do **not** cut: benchmark verification, judge validation, forgetting measurement, or the error-cause analysis. Those are what make the result trustworthy, which is the entire deliverable.
