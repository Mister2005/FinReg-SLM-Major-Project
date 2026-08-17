# 15 — Fine-Tuning Specification

## What the fine-tune is for

**Not** for memorising regulatory facts. Ovadia et al. (EMNLP 2024) established that fine-tuning is poor at knowledge injection and retrieval is much better; our corpus changes monthly, so baking facts into weights is the wrong architecture regardless.

The fine-tune targets four behaviours retrieval alone does not supply:

1. **Citation discipline** — citing the provision path in a consistent, parseable format, every time.
2. **Abstention calibration** — saying "not in the corpus" instead of confabulating, which is the documented failure in Magesh et al. (2025).
3. **Temporal hygiene** — stating the as-of date, and refusing to answer a dated question with an undated source.
4. **Indian regulatory register** — the structure and vocabulary of a compliance answer, which a general instruct model does not have.

Frame the hypothesis this way in the write-up. It is narrower than "our model knows Indian regulation" and it is the version that the literature supports and that the experiment can actually test.

## Training data construction

**Format: retrieval-augmented SFT.** Each training example contains retrieved chunks in the prompt and a grounded, cited answer as the target. Training the model on the same input shape it sees at inference is what makes A4 (fine-tuned + retrieval) coherent; training on bare question-answer pairs and then adding retrieval at test time is a train/test mismatch.

**Source documents.** Corpus documents **excluding** every `doc_id` appearing in any benchmark gold citation (invariant E7, enforced by test).

**Generation procedure per example:**
1. Sample a provision from an eligible document.
2. Use a teacher model to draft a question that provision answers, plus a grounded answer citing it.
3. Run the real retrieval pipeline on that question to obtain the chunks that will form the prompt.
4. **Validate:** the gold provision must appear in the retrieved chunks. If it does not, discard the example — otherwise the target teaches the model to answer from information it was not given, which trains hallucination directly.
5. Reject any answer containing a claim not supported by the retrieved chunks, checked by an entailment pass.

**Target mix (~6,000 examples):**

| Type | n | Purpose |
|---|---|---|
| Grounded answer with citations | 3,000 | Core behaviour |
| Abstention (retrieval deliberately returns nothing relevant) | 1,200 | Teaches refusal |
| False-premise correction | 600 | Teaches contradicting the user |
| As-of-date reasoning | 900 | Teaches temporal statement |
| Multi-document synthesis | 300 | The hardest category |

Abstention and false-premise examples are 30% of the data on purpose. A model trained only on answerable questions learns that every question has an answer, which is precisely the behaviour we are trying to prevent.

**Honest limitation to state in the write-up:** teacher-generated SFT data means the student partly learns the teacher's style and errors. Mitigations: validate every example against retrieved evidence (step 4–5), hand-review a 200-example random sample and report the error rate found, and keep the benchmark entirely human-authored so evaluation is never teacher-contaminated.

## Training configuration

Declared in advance. Deviations require a recorded reason.

```yaml
base_model: Qwen2.5-7B-Instruct        # record exact revision hash
method: QLoRA
quantization: nf4, double_quant: true, compute_dtype: bfloat16
lora:
  r: 16
  alpha: 32
  dropout: 0.05
  target_modules: [q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj]
sequence_length: 4096                   # long, because prompts carry retrieved chunks
epochs: 3
lr: 2.0e-4
scheduler: cosine
warmup_ratio: 0.03
effective_batch_size: 16                # per_device 1, grad_accum 16
optimizer: paged_adamw_8bit
loss_on: completion_only                # never train on the prompt/context tokens
seed: 42
checkpoints_every: 0.5 epoch
```

`loss_on: completion_only` matters. Computing loss over the retrieved chunks teaches the model to reproduce corpus text rather than to reason over it.

**Replay.** Mix in 10% general instruction data from a permissively-licensed public set. This is the standard forgetting mitigation and it costs almost nothing. Run one ablation without replay to measure what it bought — that is a reportable result in its own right.

**Pre-registered grid** (validation split only, never the benchmark): `r ∈ {8, 16, 32}`, `lr ∈ {1e-4, 2e-4}`, `epochs ∈ {2, 3}`. Report the full grid, not just the winner.

## Validation split

500 held-out SFT examples, disjoint from training and from the benchmark. Selection of hyperparameters and checkpoints happens here. **The benchmark is touched once, at the end, with the selected configuration.** Every additional look at the benchmark inflates the result.

## Forgetting measurement

Per invariant E8, run **before** training and at every checkpoint:

- MMLU (5-shot), a fixed 2,000-question subset, seed recorded.
- ARC-Challenge and HellaSwag, standard splits.
- GSM8K (8-shot) — arithmetic matters given C4 computation questions.
- A 100-prompt open-generation set scored for coherence, to catch degeneration that multiple-choice benchmarks miss.

Report the **delta from base**, per checkpoint. A drop beyond the threshold in `docs/17` is a finding that constrains the whole project, not a footnote.

## Compute

QLoRA on 7B at 4,096 sequence length fits comfortably in 24 GB and runs in bf16 on a single A100 40 GB with room to spare. Expected wall-clock for 6,000 examples × 3 epochs: roughly 4–8 hours on an A100, 12–20 on a T4-class card. Free-tier Colab is workable but will need checkpoint-resume across sessions — build that in from the start, not after the first disconnect.

Record actual GPU, wall-clock, and peak memory for every run. These numbers go in the paper.
