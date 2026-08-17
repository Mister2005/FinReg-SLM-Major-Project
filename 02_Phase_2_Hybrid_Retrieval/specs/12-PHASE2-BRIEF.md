# 12 — Phase 2 Brief: The Feasibility Spike

## The decision this phase exists to make

> Does domain fine-tuning add measurable value over a strong retrieval baseline on Indian regulatory compliance question answering — and if so, on which question types, at what cost, and with how much general-capability loss?

Everything in Phase 2 is subordinate to answering that. Anything that does not help answer it is out of scope.

## Why not just train the model

Three published findings make "train first, evaluate later" the wrong order.

1. **Retrieval dominates fine-tuning for factual knowledge.** Ovadia et al. (EMNLP 2024) measured 0.875 for retrieval against 0.504 for unsupervised fine-tuning on knowledge genuinely absent from pretraining. Indian regulatory text is almost entirely absent from pretraining, so this is the regime we are in.

2. **Retrieval does not fix hallucination on its own.** Magesh et al. (*Journal of Empirical Legal Studies*, 2025) found commercial retrieval-augmented legal tools hallucinating 17–33% of the time. So retrieval is necessary but not sufficient, which is exactly the space where fine-tuning might contribute — citation discipline, abstention, answer structure.

3. **Fine-tuning costs capability.** Luo et al. (EMNLP 2023) showed forgetting worsens with scale; Biderman et al. (TMLR 2024) showed parameter-efficient tuning learns less even as it forgets less. Fine-tuning is not free, so it must be shown to pay for itself.

Put together: the honest hypothesis is not "our fine-tuned model will beat GPT" but **"fine-tuning improves how the model uses retrieved regulatory text, without unacceptable capability loss."** That is a narrower, testable, and far more defensible claim — and it is cheap to test.

## The six arms

Every arm answers the same 300 questions with identical prompts and decoding.

| Arm | Model | Retrieval | What it tells us |
|---|---|---|---|
| **A0** | Frontier API, zero-shot | No | How much the task needs the corpus at all |
| **A1** | Base SLM (Qwen 2.5 7B Instruct), zero-shot | No | The floor. Establishes that Indian regulation is genuinely out-of-distribution |
| **A2** | Base SLM | **Yes** | **The baseline that matters.** How far retrieval alone gets us |
| **A3** | Fine-tuned SLM | No | Did fine-tuning inject knowledge? (Expect: barely) |
| **A4** | Fine-tuned SLM | **Yes** | **The proposed system.** Compared against A2, this is the whole experiment |
| **A5** | Frontier API | Yes | The practical ceiling, and the cost/latency comparison point |

**The headline comparison is A4 versus A2.** A3 versus A1 is the secondary comparison, testing whether fine-tuning injected any knowledge at all — the literature predicts it will not, and confirming that on Indian data is itself a contribution.

A0 and A5 bracket the problem. If A0 already scores well, our corpus adds little and the project premise weakens. If A5 barely beats A2, the frontier advantage is small and the cost argument for a small model becomes very strong.

## What Phase 2 deliberately does not do

- No continued pretraining on the full corpus. That is expensive and is a Phase 3 decision contingent on the outcome here.
- No hyperparameter tournament. One declared configuration plus a small pre-registered grid on a validation split.
- No full 1,000+ question benchmark. 300 hand-verified questions is enough to detect a meaningful effect and is achievable in the time available. Scaling the benchmark is Phase 3 work.
- No production serving, no UI, no deployment.
- No multilingual work.

## Model choice

**Qwen 2.5 7B Instruct** as the primary base model. Rationale: strong open-weight instruct baseline at a size that fits QLoRA on a single accessible GPU, permissive licence, and good long-context handling which matters because regulatory chunks are long.

**Llama 3.1 8B Instruct** as a secondary confirmation run for the headline A2/A4 comparison only, if time permits. Running two base models guards against a result that is an artefact of one model family — a reviewer will ask, and having the second run is a cheap answer.

Record the exact model revision hash. "Qwen 2.5 7B" is not a reproducible identifier.

## Success is not "our model wins"

Phase 2 succeeds if it produces a **trustworthy answer**, whichever direction it points. Four outcomes are pre-committed in `docs/17`, and three of them are perfectly good project outcomes. The only genuine failure mode is an untrustworthy number — from a leaked benchmark, an unvalidated judge, or arms that differ in more than one dimension.

## Expected effort

Six weeks at 3–4 focused days per week. Roughly: one week benchmark authoring, one and a half weeks retrieval baseline, one week SFT data plus training, one and a half weeks evaluation and analysis, half a week write-up. Milestones and kill criteria in `docs/18`.
