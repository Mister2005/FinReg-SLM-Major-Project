# 00 — Project Brief

## The project

**FinReg-SLM** is a domain-specialised small language model for Indian financial and regulatory compliance. The full project trains a ~7–8B open-weight model on Indian regulatory primary sources using parameter-efficient fine-tuning, pairs it with retrieval over a version-aware corpus, and benchmarks it against frontier LLM APIs on accuracy, cost per query and latency — reporting general-capability regression honestly rather than hiding it.

Final-year major project, A.Y. 2026-27.

## Why the corpus is Phase 1 and not an afterthought

Three findings from the research phase determine this ordering.

1. **Retrieval beats naive fine-tuning for knowledge injection.** The published comparisons (Ovadia et al. 2023; Balaguer et al. 2024; RAFT) consistently show that retrieval-augmented generation outperforms unsupervised fine-tuning for factual knowledge, and that the best results come from combining both. A fine-tune sitting on a corpus with no retrieval index and no version metadata cannot express either half of that finding. The corpus is therefore the substrate for the whole project, not a preprocessing step.

2. **Regulatory text is temporal, and most corpora ignore this.** A circular that was correct in 2019 may have been withdrawn in 2023. A model trained on a flat pile of ten years of circulars will confidently state repealed rules. Both RBI and SEBI publish explicit withdrawal/archive lists — capturing them is cheap now and impossible to reconstruct later.

3. **The corpus is itself a contribution.** No public benchmark or open corpus unifies RBI + SEBI + direct tax + GST + DPDP for Indian compliance QA. A clean, licensed, version-aware corpus with reproducible acquisition code is publishable even if the model result is null.

## Scope of Phase 1

**In scope.** Source discovery; polite crawling; raw blob storage with provenance; text and table extraction with OCR fallback; normalisation; citation and document-number parsing; supersession/withdrawal graph; statutory regime tagging; licence tagging; quality gates; Parquet export; refresh tooling.

**Explicitly out of scope.** Chunking strategy for embeddings, embedding models, vector stores, tokenizer analysis, training data formatting, instruction-pair synthesis, benchmark question authoring, any model weights. These are Phases 2 and 3. See invariant I12.

## Corpus window

**2016-04-01 to present.** This is deliberate, not round-number convenience:

- Captures the GST regime from pre-rollout preparation (2016) through implementation (July 2017) to the present, so the corpus contains a complete tax-regime introduction.
- Captures the Insolvency and Bankruptcy Code (2016) and its downstream RBI stressed-asset circulars.
- Captures RBI's Scale Based Regulation framework for NBFCs (2021) and the November 2025 consolidation of circulars into Master Directions.
- Captures the DPDP Act (2023) and DPDP Rules (2025) with their phased commencement running to 2027.
- Captures the Income-tax Act 2025 coming into force on 2026-04-01 and repealing the 1961 Act — a complete statutory replacement inside the window.

That last item is the single most valuable temporal feature in the corpus and the reason the window must not be shortened. See `06-TEMPORAL-VALIDITY-SPEC.md`.

Statutes themselves are pulled at full text regardless of enactment year, because the 1961 Act, the 1962 Rules, the CGST Act 2017 and the SEBI Act 1992 are all load-bearing for documents inside the window.

## Success criteria for Phase 1

| Criterion | Target |
|---|---|
| Sources ingested | RBI, SEBI, CBDT/Income Tax, CBIC/GST, MeitY (DPDP), India Code statutes |
| Provenance completeness | 100% of records carry URL + timestamp + hash |
| Extraction fidelity (manual audit, n=200 stratified) | ≥ 95% |
| Records with resolved in-force status (not `unknown`) | ≥ 80% for RBI and SEBI; ≥ 60% overall |
| Licence-tagged records | 100% |
| Re-run idempotency | Zero new blobs on immediate re-crawl |
| Full refresh wall-clock | ≤ 72 hours at default politeness settings |

## Known risks carried into Phase 1

- **SEBI and CBIC use JavaScript-driven pagination.** Mitigation: reproduce the underlying POST/API call rather than driving a browser. Fallback to Playwright is permitted only for a source where the API approach is demonstrably blocked, and must be documented.
- **RBI archive navigation is ASP.NET postback-based.** Mitigation: crawl by sequential document ID rather than by archive pagination. Verified feasible — see `03-DATA-SOURCES.md`.
- **Scanned or image-only PDFs in older CBDT and CBIC material.** Mitigation: OCR fallback with an explicit quality gate; OCR-derived text is tagged and can be excluded downstream.
- **Sites change.** Every source module declares a `verify()` health check that asserts its assumptions still hold. A failing `verify()` blocks the crawl for that source with a clear message rather than silently returning zero documents.
