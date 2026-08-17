# 19 — Tickets

Dependency-ordered. A ticket is done when its acceptance criteria are passing tests, not when the code runs.

---

## M6 — Benchmark

**T-101 Benchmark schema and validator** — deps: Phase 1 manifest
Pydantic model for the question record in `docs/13`; validator CLI.
*AC:* A record missing `gold_citations` is rejected. A `doc_id` absent from the manifest is rejected. Category counts are asserted against spec.

**T-102 Authoring worksheet tooling** — deps: T-101
`finreg bench new` opens a corpus document and scaffolds a question record with `doc_id` and provision path pre-filled.
*AC:* A question authored via the tool passes the validator without hand-editing.

**T-103 Citation-support checker** — deps: T-101
Verifies that the cited provision text actually contains support for the gold answer.
*AC:* A deliberately mismatched citation is flagged. Runs across all 300 in under a minute.

**T-104 C3 stem-pair validator** — deps: T-101
*AC:* Every C3 stem has ≥ 2 dated variants; variants sharing a stem have different gold citations (otherwise the date is not decisive and the question is defective).

**T-105 Annotation agreement tooling** — deps: T-101
*AC:* Computes Cohen's κ for binary labels and for the 3-point correctness scale over an overlap subsample; outputs a per-question disagreement list.

**T-106 Freeze and exclusion export** — deps: T-103, T-104, T-105
*AC:* Emits file SHA-256, writes `bench/excluded_doc_ids.json`, and a test asserts the SFT generator refuses to run without it.

---

## M7 — Retrieval

**T-107 Structure-aware chunker** — deps: Phase 1 corpus
*AC:* No chunk splits a numbered provision. Tables remain whole. Every chunk carries the header prefix and inherits temporal fields. Property test: concatenating a document's chunks recovers its full text modulo overlap.

**T-108 Embedding and dense index** — deps: T-107
*AC:* Index builds over the full corpus; a known provision is retrievable by paraphrase; build is resumable.

**T-109 BM25 lexical index** — deps: T-107
*AC:* An exact statutory reference ("Section 194-IA") retrieves its provision at rank 1.

**T-110 Reciprocal rank fusion** — deps: T-108, T-109
*AC:* Fusion output is deterministic given the same inputs; k is configurable.

**T-111 Cross-encoder reranker** — deps: T-110
*AC:* Reranking measurably changes ordering; latency overhead recorded; can be disabled by config for ablation.

**T-112 Temporal filter** — deps: T-110
*AC:* A withdrawn chunk is excluded for a post-withdrawal `as_of`. An `unknown`-status chunk lands in the separate bucket, never the main one. Disabling the filter is a single config flag for ablation.

**T-113 Generation prompt and parser** — deps: T-112
*AC:* Abstention emits the fixed parseable prefix. Citations parse into `(doc_id, provision_path)` tuples. One template, shared by all arms, loaded from a single file.

**T-114 Retrieval metrics** — deps: T-112
*AC:* Recall@k, MRR, temporal precision computed against gold citations; report generated.

**T-115 Arms A1 and A2** — deps: T-113
*AC:* Both run end to end at temperature 0 with a fixed seed; run directories contain full raw generations and resolved configs.

**T-116 Temporal ablation run** — deps: T-112, T-115
*AC:* A2 with and without temporal filtering, C3 delta reported.

---

## M8 — Training

**T-117 SFT generation pipeline** — deps: T-106, T-112
*AC:* Refuses to run if `excluded_doc_ids.json` is absent. Every generated example has its gold provision present in the retrieved chunks or is discarded; discard rate logged.

**T-118 Entailment validation** — deps: T-117
*AC:* An answer containing an unsupported claim is rejected; rejection rate reported.

**T-119 SFT mix builder** — deps: T-118
*AC:* Produces the specified type mix within ±5%; abstention examples genuinely have no supporting chunk.

**T-120 Overlap assertion test** — deps: T-119
*AC:* Test fails if any SFT example's source `doc_id` appears in the benchmark exclusion set. This test runs in CI.

**T-121 Forgetting harness** — deps: none
*AC:* Runs MMLU subset, ARC-C, HellaSwag, GSM8K and the coherence set against any checkpoint; results written to the run directory; base measurement completed before training starts.

**T-122 QLoRA training** — deps: T-119, T-121
*AC:* Trains with the declared config; `loss_on: completion_only` verified by inspecting a masked batch; checkpoints resume correctly after interruption; peak memory and wall-clock recorded.

**T-123 Replay ablation** — deps: T-122
*AC:* One run with and one without the 10% general-data mix; forgetting delta compared.

**T-124 Hyperparameter grid** — deps: T-122
*AC:* Full declared grid run on the validation split; all results reported, not just the selected configuration; the benchmark is not touched.

---

## M9 — Evaluation

**T-125 Arm runner** — deps: T-115, T-122
*AC:* Runs any arm from a config; asserts prompt and decoding identity across arms by config hash; refuses to run if they differ.

**T-126 Arms A3, A4** — deps: T-125
*AC:* Complete runs with artefacts.

**T-127 Arms A0, A5 (frontier)** — deps: T-125
*AC:* Token counts and costs recorded per query; same prompt template.

**T-128 Judge implementation** — deps: T-126
*AC:* Arm identity stripped; presentation order randomised; judge model family differs from every arm; structured verdict with rationale.

**T-129 Judge validation** — deps: T-128
*AC:* 100 stratified answers human-scored; κ computed and recorded; the scoring path selected per `docs/16` thresholds and written into the report.

**T-130 Programmatic citation checker** — deps: T-113
*AC:* Citation precision computed by manifest join where resolvable; unresolvable citations counted separately, never silently marked correct.

**T-131 Abstention scorer** — deps: T-113
*AC:* Produces the full 2×2 per arm; false-premise detection rate on C5.

**T-132 Bootstrap and paired tests** — deps: T-129
*AC:* 10,000 resamples with recorded seed; paired differences with CIs; McNemar on binarised outcomes; confirmatory versus exploratory comparisons labelled per the pre-declared plan.

**T-133 Cost and latency measurement** — deps: T-126, T-127
*AC:* p50/p95 at concurrency 1 and 4; hardware, quantization and serving stack recorded alongside every number.

**T-134 Error-cause classifier UI** — deps: T-126
*AC:* Presents each A2/A4 failure with its retrieved chunks for hand-classification into the `docs/16` taxonomy; exports the distribution.

---

## M10 — Decision

**T-135 Evaluation report generator** — deps: T-132, T-133, T-134
*AC:* Every number derives from a run artefact; the generator contains no hardcoded figures; report renders to Markdown and HTML.

**T-136 Gate evaluator** — deps: T-135
*AC:* Evaluates P1–P6 and G1–G3, printing measured values against thresholds; identifies the applicable outcome from `docs/17`; exits non-zero if any precondition fails.

**T-137 Decision record** — deps: T-136
*AC:* `reports/phase2-decision.md` generated with outcome, all gate values, precondition status and error distribution; contains a sign-off field.

**T-138 Reproducibility check** — deps: T-135
*AC:* A fresh checkout at the tagged commit reproduces the headline A2/A4 numbers from stored artefacts.
