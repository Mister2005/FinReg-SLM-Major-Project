# FinReg-SLM — Phase 2 Documentation Set
## Feasibility Spike

**Phase 2 is not a build phase. Its deliverable is a decision.**

Phase 1 produced a licensed, version-aware corpus. The obvious next move is "train the model" — but that is the wrong next move, and the literature says so plainly. Ovadia et al. (EMNLP 2024) found retrieval beats unsupervised fine-tuning for knowledge injection by a wide margin (0.875 vs 0.504 on genuinely new knowledge). If that result holds on Indian regulatory text, a fine-tune trained over three months would be beaten by a retrieval baseline built in two weeks.

So Phase 2 answers one question, cheaply, before any large commitment:

> **Does domain fine-tuning add measurable value over a strong retrieval baseline on Indian regulatory compliance QA — and if so, on which question types?**

Six weeks. A 300-question seed benchmark. Six evaluation arms. Four possible outcomes, each with a pre-committed next step. A null result is a valid, publishable outcome and does **not** mean the project failed.

## Read order

| # | Document | Purpose |
|---|---|---|
| — | [`AGENTS-PHASE2.md`](AGENTS-PHASE2.md) | Invariants specific to experimentation. Read first. |
| 12 | [`docs/12-PHASE2-BRIEF.md`](docs/12-PHASE2-BRIEF.md) | The decision, the arms, why this ordering. |
| 13 | [`docs/13-SEED-BENCHMARK-SPEC.md`](docs/13-SEED-BENCHMARK-SPEC.md) | 300 questions: taxonomy, authoring, annotation, agreement. |
| 14 | [`docs/14-RAG-BASELINE-SPEC.md`](docs/14-RAG-BASELINE-SPEC.md) | Chunking, embedding, retrieval, temporal filtering, citation grounding. |
| 15 | [`docs/15-FINETUNE-SPEC.md`](docs/15-FINETUNE-SPEC.md) | Training data construction, LoRA/QLoRA config, forgetting measurement. |
| 16 | [`docs/16-EVALUATION-PROTOCOL.md`](docs/16-EVALUATION-PROTOCOL.md) | Metrics, judge validation, statistics, what counts as a real difference. |
| 17 | [`docs/17-DECISION-GATES.md`](docs/17-DECISION-GATES.md) | **The most important document.** Pre-committed thresholds and outcomes. |
| 18 | [`docs/18-IMPLEMENTATION-PLAN.md`](docs/18-IMPLEMENTATION-PLAN.md) | Six weeks, five milestones, kill criteria. |
| 19 | [`docs/19-TICKETS.md`](docs/19-TICKETS.md) | 38 dependency-ordered tickets. |
| 20 | [`docs/20-RUNBOOK.md`](docs/20-RUNBOOK.md) | Commands, environment, compute, incident procedures. |

## Repository additions

```
finreg-slm/
├── src/finreg/
│   ├── bench/        seed benchmark authoring, loading, validation
│   ├── retrieve/     chunking, embedding, index, temporal filter, reranker
│   ├── generate/     prompt templates, citation-grounded generation, abstention
│   ├── train/        SFT data construction, LoRA/QLoRA, checkpointing
│   └── eval/         arms, metrics, judge, bootstrap, reports
├── data/
│   ├── bench/        seed-benchmark-v1.jsonl + annotation records
│   ├── index/        vector + lexical indices
│   └── sft/          generated training pairs
├── runs/             one directory per experiment run, immutable
└── reports/
```

## The one-sentence exit condition

Phase 2 is complete when `finreg eval report` produces a six-arm comparison on the seed benchmark with bootstrap confidence intervals, a validated judge, a measured general-capability delta, and `docs/17` has been resolved to exactly one of its four outcomes with the evidence recorded.
