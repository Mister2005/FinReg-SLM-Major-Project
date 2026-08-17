# 20 — Runbook

## Environment

```bash
uv sync --extra train        # adds torch, transformers, peft, trl, bitsandbytes,
                             # accelerate, sentence-transformers, rank_bm25, faiss
finreg env check             # asserts GPU visible, CUDA version, VRAM, disk headroom
```

`finreg env check` refuses to start training if VRAM is below the configured minimum, rather than failing forty minutes in.

## Command sequence

```bash
# Benchmark
finreg bench new --doc-id <id>                  # scaffold a question
finreg bench validate                           # schema + citation support + counts
finreg bench agreement --overlap 60             # Cohen's kappa
finreg bench freeze                             # hash, tag, export exclusions

# Retrieval
finreg index build --chunker structure          # chunk + embed + BM25
finreg retrieve eval --k 5,8,20                 # Recall@k, MRR, temporal precision
finreg run arm --name A2                        # base + retrieval
finreg run ablation --no-temporal-filter

# Training
finreg sft generate --target 6000
finreg sft validate                             # entailment + exclusion assertion
finreg eval capability --model base             # forgetting baseline, BEFORE training
finreg train qlora --config config/train.yaml
finreg eval capability --checkpoint <path>      # per checkpoint

# Evaluation
finreg run arm --name A0,A1,A2,A3,A4,A5
finreg judge run --validate-first
finreg eval bootstrap --resamples 10000 --seed 42
finreg eval errors --arms A2,A4                 # hand-classification UI
finreg eval report
finreg eval gate                                # P1-P6, G1-G3, outcome
```

## Compute guidance

| Setup | Feasibility |
|---|---|
| A100 40 GB | Comfortable. Full run in a day. |
| RTX 4090 / 3090 (24 GB) | Works at 4,096 sequence length with QLoRA. Reduce to 2,048 if OOM. |
| T4 16 GB (free Colab) | Workable but slow (12–20 h). **Requires checkpoint-resume from the start.** |
| CPU only | Not viable for training. Retrieval-only arms (A1, A2) can run on CPU slowly. |

**Colab specifically.** Sessions disconnect. Write checkpoints to Drive every half epoch, and make `finreg train qlora` resume automatically from the latest checkpoint with no flags. Test the resume path deliberately by killing a run — do not discover it is broken at 3 a.m.

If compute is genuinely unavailable, drop to a 3B base model, state it plainly, and note that the capability/scale interaction from Luo et al. means results at 3B may not transfer to 7B. A clean, honest 3B result is a good project outcome.

## Incident procedures

### Out of memory during training
In order: reduce sequence length 4096 → 2048; increase gradient accumulation while reducing per-device batch to 1; enable gradient checkpointing; reduce LoRA rank. **Record which mitigation was used** — it changes the effective configuration and must appear in the run config.

### Retrieval Recall@8 below threshold
Diagnose in this order, not at random:
1. Are provisions being split mid-clause? Inspect 20 chunks by hand.
2. Is the header prefix present in the *embedded* text, or only in metadata? This is the most common bug and it silently halves recall.
3. Is the temporal filter excluding gold chunks? Run with the filter off and compare.
4. Is the embedding model handling legal register? Try the alternative and compare on the same 50 questions.

### Judge disagrees with humans
Do not tune the judge prompt until it agrees — that is fitting the grader to the desired result. Instead: inspect the disagreements, determine whether the judge or the human is right, and if the judge is systematically wrong on a category, exclude that category from judge scoring and score it by hand.

### Results look too good
Treat this as a bug report. Check in order: benchmark leakage into SFT (run T-120); the judge seeing arm identity; arms accidentally using different prompts (compare config hashes); a gold answer copied from a model output during authoring. Suspiciously strong results are far more often contamination than breakthrough.

### A run is interrupted
All runs are resumable. `finreg run arm --name A2 --resume` continues from the last completed question. Never merge a partial run with a completed one — re-run the whole arm if in doubt, since arms must be internally consistent.

## Artefact hygiene

Every run directory is immutable once written. Before the final report:

```bash
finreg runs verify        # asserts every run has config, commit, seeds, raw generations
```

Any run failing this cannot contribute to a reported number.

## Handover at Phase 2 exit

Committed and tagged `phase2-freeze`:
- `data/bench/seed-benchmark-v1.jsonl` plus annotation records and κ values
- `runs/` for all six arms plus ablations
- `reports/phase2-eval.md` and `reports/phase2-decision.md`
- `config/train.yaml` with the selected configuration and the full grid results
- The agreed Phase 3 scope

Phase 3 starts from the decision record, not from a conversation.

## A closing note

The temptation across this phase will be to make the fine-tuned model look good. Resist it specifically and deliberately. The examiners will not be impressed by a 4-point improvement with an overlapping confidence interval, and they will notice if the benchmark was touched after results appeared. What survives scrutiny is a pre-registered threshold, a validated judge, and an honest number — whichever way it points.
