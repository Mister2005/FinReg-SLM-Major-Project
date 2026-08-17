# 14 — Retrieval Baseline Specification

This baseline must be **genuinely strong**. The entire experiment is a comparison against it, and a weak baseline would manufacture a positive result for fine-tuning — the most likely way this project produces a conclusion that does not survive review.

Build this before the fine-tune. If it turns out to be sufficient on its own, that is valuable to know before spending training compute.

## Chunking

Regulatory text has structure that generic chunkers destroy. Split on the document's own hierarchy first, falling back to size-based splitting only within an oversized leaf.

**Rules.**
- Split at numbered provision boundaries (paragraph, clause, sub-rule, section) parsed in Phase 1, never mid-provision.
- Target 512 tokens, hard maximum 1,024, with 64-token overlap only when a provision must be split.
- **Every chunk carries a header prefix** injected into its embedded text: document title, document number, issue date, regulator, and the provision path (e.g. `Master Direction — KYC / Chapter VI / para 38`). Without this, a retrieved chunk is unattributable and the model cannot cite it.
- Tables extracted in Phase 1 are kept whole as single chunks regardless of size. Splitting a rate table produces confidently wrong answers, which is the worst failure mode in this domain.
- Every chunk inherits `doc_id`, `in_force_from`, `in_force_to`, `status` and `statutory_regime` from the Phase 1 manifest.

## Index

**Hybrid, because neither half is sufficient.** Dense retrieval misses exact statutory references; lexical retrieval misses paraphrased concepts.

- **Dense:** BGE-M3 or E5-large embeddings. Justify the choice with a small retrieval-only comparison on a 50-question subset, and record it.
- **Lexical:** BM25 over the same chunks.
- **Fusion:** reciprocal rank fusion, k=60. Simple, parameter-light, and defensible.
- **Reranking:** a cross-encoder reranker over the top 50 fused results, returning top 8 to the generator. Report retrieval quality with and without reranking — reranking usually helps enough to justify its latency, but this must be measured, not assumed.

## Temporal filtering — the distinctive component

This is what makes the baseline *ours* rather than generic, and it is the axis the whole project claims novelty on.

Every query carries an `as_of` date (from the benchmark record, or defaulting to today in real use). Retrieval applies:

```
candidate is eligible if:
    in_force_from <= as_of
    AND (in_force_to IS NULL OR in_force_to > as_of)
    AND status != 'withdrawn'
```

Chunks with `status = 'unknown'` are retrieved into a **separate, clearly-labelled bucket** and passed to the generator marked as uncertain-validity. Per Phase 1 invariant I6, unknown is never silently treated as in-force. The generator is instructed to flag when its answer rests on an uncertain-validity source.

**Run an ablation with temporal filtering disabled.** The difference on C3 questions is a headline result — it quantifies what version-awareness buys, which is precisely our contribution. Expect it to be the largest single effect in the whole phase.

## Generation

**One prompt template, used identically by every arm** (invariant E3). It must require:
- An answer grounded only in the provided chunks.
- An inline citation for every substantive claim, using the chunk's document number and provision path.
- Explicit abstention when the chunks do not contain the answer, in a fixed parseable form (e.g. beginning `INSUFFICIENT_CORPUS_EVIDENCE:`) so abstention can be scored automatically.
- A statement of the as-of date the answer is given for.
- A flag when relying on an uncertain-validity chunk.

Decoding: temperature 0, fixed seed, max 512 new tokens, identical across arms.

**Do not few-shot one arm and zero-shot another.** If few-shot examples are used, the same examples appear in every arm, and they are drawn from documents excluded from both the benchmark and the SFT set.

## Retrieval quality measurement (independent of generation)

Measure retrieval on its own before touching generation, because a generation failure and a retrieval failure need completely different fixes.

- **Recall@k** (k = 5, 8, 20) against the benchmark's `gold_citations`.
- **MRR** of the first gold document.
- **Temporal precision:** fraction of retrieved chunks that were actually in force on the query's as-of date.

If Recall@8 is below roughly 0.70, generation cannot succeed and there is no point evaluating arms. Fix retrieval first — this is a hard gate in `docs/18`.

## Known weaknesses to record honestly

- Chunk-level retrieval struggles when an answer requires a provision plus its definition clause from elsewhere in the same instrument.
- Cross-document amendment chains (Master Direction plus three amending circulars) are exactly the C2 case and will be the baseline's weakest category.
- OCR-derived chunks from Phase 1 carry error risk; report results with and without them.

These are stated here so they appear in the write-up as anticipated limitations rather than surprises.
