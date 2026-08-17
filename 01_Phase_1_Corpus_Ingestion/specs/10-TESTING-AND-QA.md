# 10 — Testing and Quality Assurance

## Principle

The corpus is the experimental apparatus for the whole project. An undetected extraction bug does not produce a visible crash — it produces a fine-tune that is quietly wrong and a benchmark that cannot distinguish model error from data error. Testing here is not hygiene; it is the difference between a result and a rumour.

## Test taxonomy

### 1. Unit tests — no network, ever

Every parser, every normalisation step, every classifier. Network access in the unit suite is blocked at the fixture level (`respx` intercepts all `httpx` traffic; an un-mocked request fails the test).

**Fixtures.** Committed under `tests/fixtures/<source>/`, captured from real pages with their capture date in the filename. At minimum, per source: one current-layout listing page, one current-layout detail page, one historical-layout detail page from near the window start, one text PDF, one scanned PDF, one malformed PDF.

Fixtures are real captured bytes. Never hand-write a fixture that approximates what a site returns — the approximation will be cleaner than reality and the test will pass while production fails.

### 2. Property-based tests

Use `hypothesis` for the normalisation pipeline. The core property:

> For any input string, normalisation preserves every digit, every currency symbol, every percentage sign, and every substring matching a section-reference pattern.

This one property catches the class of bug that would otherwise silently corrupt tax rates — the most damaging possible failure for this corpus.

### 3. Contract tests — network, run on demand

Marked `@pytest.mark.contract`, excluded from the default run, executed by `finreg sources verify`. These assert that live sites still match doc 03: a known document ID resolves, a listing element still exists, a record count still parses.

Run weekly during development and before every crawl. When one fails, the site changed — update the source module and doc 03 together.

### 4. Integration tests

End-to-end on a fixed 50-document sample with committed fixtures: discover → fetch → extract → normalise → resolve → export. Asserts final Parquet row counts, schema, and specific field values.

### 5. Idempotency and resumption tests

- Run the sample crawl twice: assert zero new blobs, zero new document rows on the second pass.
- Kill the process at three different stages via a fault-injection hook; resume; assert the final state matches an uninterrupted run exactly.

### 6. Regression corpus

A frozen set of 100 documents with committed expected extraction output. Any change to `extract/` or `normalize/` runs against it and produces a diff report. A diff is not automatically a failure — but it must be reviewed and the reviewer must record whether it is an improvement. This is how extractor changes stop being guesswork.

## Corpus quality metrics

Computed by `finreg report`, all from manifest queries.

| Metric | Definition | Healthy range |
|---|---|---|
| Provenance completeness | share of documents with URL + timestamp + hash | 100% |
| Extraction success rate | documents with ≥ 1 `texts` row / total documents | ≥ 98% |
| OCR share | `text_source = ocr` / total | report; expect low for RBI/SEBI, higher for legacy CBDT |
| Mean chars/document | by regulator and doc_type | report; sharp drops flag extraction regressions |
| Status resolution rate | `status != 'unknown'` / total | ≥ 80% RBI+SEBI, ≥ 60% overall |
| Citation resolution rate | citations with non-null `target_doc_id` / total citations | report; low is expected and fine |
| Duplicate share | non-canonical / total | report; a sudden rise means the ID scheme broke |
| Coverage | (regulator, quarter) cells with ≥ 1 document | 100% of cells or explained |
| Failure rate | `fetch_failures` unresolved / attempted | below each source's `max_failure_rate` |
| Flag share | documents with ≥ 1 quality flag / total | report; investigate above 15% |

Every metric is reported **with its measurement method** in the QA report. A number without a method is not a result.

## Manual audit protocol (AC-2 and AC-3)

This is the only part of Phase 1 that cannot be automated, and it is the part that decides whether the corpus is trustworthy. Budget one full day.

### Sampling

200 documents, stratified:
- Proportional to document count by regulator, minimum 15 per regulator.
- Within each regulator, stratified by year across the window.
- Force-include: 20 OCR-derived documents, 20 documents carrying any quality flag, 10 documents with `char_count` in the bottom decile, 10 with extracted tables.

Sampling is deterministic given a seed, and the seed is recorded. `finreg qa sample --seed <n> --out reports/audit-<date>.md` generates the worksheet.

### Per-document checks

For each sampled document, open the `source_url` in a browser alongside the stored text and record:

1. **Resolves?** Does the URL return the document the manifest claims? (yes / no / redirected-elsewhere)
2. **Complete?** Is the whole operative text present — no truncation, no dropped final section? (yes / partial / no)
3. **Ordered?** Is reading order correct, especially in multi-column or table-heavy pages? (yes / no)
4. **Numbers intact?** Spot-check every rate, threshold, date and section number visible on the first page against the source. (yes / no + detail)
5. **Metadata correct?** Title, date, document number. (yes / no + which field)
6. **Boilerplate removed?** Any navigation, footer or disclaimer text leaked into the body? (yes / no)

A document passes AC-3 only if checks 2, 3 and 4 are all clean. Check 4 is non-negotiable: **one wrong digit in a TDS rate is a worse defect than a whole missing document**, because a missing document is visible and a wrong digit is not.

### Recording

`reports/audit-<date>.md` records the seed, every sampled `doc_id`, every check result, and a classified cause for each failure. Failure causes feed directly into the tuned threshold values reported in `phase1-summary.md`.

If fidelity lands below 95%, the audit output tells you exactly which extraction path is responsible. Fix it, re-extract the affected subset, re-audit a fresh sample with a new seed. Do not re-audit the same sample — that measures the fix against the documents you fixed it for.

## Continuous checks during development

- Unit suite on every commit.
- Contract suite weekly and before any crawl.
- Regression corpus diff on every change to `extract/` or `normalize/`.
- `finreg report` after every crawl session; watch mean chars/document per source for step changes.

## What "done" does not mean

A passing test suite does not mean the corpus is correct. It means the corpus is correct **in the ways you thought to check**. The manual audit exists because it is the only check that can find the failure you did not anticipate. Do not skip it, do not shrink the sample, and do not let the agent self-report it.
