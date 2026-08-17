# AGENTS-PHASE2.md — Experimental Invariants

Phase 1's invariants (I1–I12) still apply to anything touching the corpus. These are additional and specific to running experiments. An experiment that violates any of them produces a number you cannot report.

## E1 — The benchmark is frozen before any model is run against it

Author and freeze `seed-benchmark-v1.jsonl`, commit it, tag it. **After the freeze, no question may be edited, removed or reworded because a model got it wrong.** If a question is discovered to be genuinely defective (ambiguous, wrong gold answer, unanswerable-but-not-labelled-so), it is recorded in `bench/defects.jsonl` with the reason and *excluded from all arms equally* in a documented v1.1 — never silently fixed.

The failure mode this prevents is the most common one in student projects: tuning the test set until the method looks good.

## E2 — Every run is fully specified and immutable

Each run writes `runs/<run_id>/` containing: the git commit, the full resolved config, the model identifier and revision hash, the benchmark version, the random seeds, the complete raw generations, and the environment lockfile. Nothing in a run directory is ever edited after the run completes.

If you cannot reconstruct exactly what produced a number, the number does not go in the report.

## E3 — Arms differ in exactly one dimension at a time

The six arms in `docs/12` differ by retrieval on/off and fine-tuning on/off. **Prompt templates, decoding parameters, max tokens, and system messages are identical across arms** except where the arm definition explicitly requires otherwise, and every such exception is recorded in the run config.

Changing the prompt for one arm because "it works better that way" invalidates the comparison. If a prompt change helps, apply it to all arms and re-run all arms.

## E4 — Decoding is deterministic for evaluation

Temperature 0, fixed seed, fixed max tokens. Sampling-based decoding is permitted only for a separately-labelled variance study, never for the headline comparison.

## E5 — No number is reported without an uncertainty interval

With 300 questions, a difference of a few points is noise. Every reported metric carries a bootstrap 95% confidence interval (10,000 resamples, seed recorded). Claims of the form "arm A beats arm B" require non-overlapping intervals or an explicit paired test — see `docs/16`.

## E6 — The judge is validated before it is trusted

Any automated grader is validated against human labels on a stratified subsample before its scores are used. Report the agreement statistic. If agreement is below the threshold in `docs/16`, the judge is not used for that metric and human scoring is required.

## E7 — Training data never overlaps the benchmark

SFT pairs are generated from corpus documents. **Every document used to author a benchmark question is excluded from SFT generation**, tracked by `doc_id`. This exclusion is enforced in code and asserted in a test, not maintained by hand.

Additionally, no benchmark question or gold answer is ever fed to the SFT generation process.

## E8 — Forgetting is measured, not assumed

The general-capability suite is run against the base model **before** any training, and against every fine-tuned checkpoint. The delta is a first-class reported result. A run without a before-measurement cannot report forgetting and is incomplete.

## E9 — Negative results are results

If fine-tuning does not beat retrieval, that is written up as the finding, with the same rigour as a positive result would receive. No re-running with different hyperparameters until the desired outcome appears. Hyperparameter search is permitted and expected — but it is declared in advance in the run plan, its full grid is reported, and the selection is made on a validation split, never on the benchmark.

## E10 — Abstention counts

A system that says "I cannot determine this from the corpus" is behaving correctly when the corpus does not contain the answer. Metrics that punish abstention equally with a wrong confident answer are wrong for this domain. Scoring must separate: correct answer, correct abstention, wrong answer, wrong abstention.

## E11 — Cost and latency are measured on real hardware, once, under stated conditions

Record the exact GPU, batch size, quantization, serving stack and concurrency. Do not extrapolate. Do not quote vendor figures. State the conditions alongside every number.

## E12 — Stop at the gate

When `docs/17` resolves to an outcome, Phase 2 ends. Do not continue "just to see" — the next phase is scoped by which outcome was reached, and starting it early wastes the decision the spike was built to produce.
