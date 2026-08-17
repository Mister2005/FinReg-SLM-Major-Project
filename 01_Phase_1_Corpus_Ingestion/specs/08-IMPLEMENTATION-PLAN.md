# 08 — Implementation Plan

Five milestones. Each has a **hard gate**: a measurable condition that must hold before the next milestone starts. Gates exist to kill bad assumptions cheaply. A milestone that fails its gate is a result, not a disaster — it just needs to be reported and the plan adjusted.

Effort is stated in working days for one implementer with an agent, assuming other coursework continues.

---

## M0 — Skeleton and HTTP substrate (3 days)

**Build**
- Repository layout, `pyproject.toml`, `uv` lock, CLI skeleton with `typer`.
- `finreg.http.client` complete: throttle, robots, retry/backoff, conditional requests, structured logging.
- `finreg.store`: manifest DDL applied, migration runner, blob writer.
- `config/sources.yaml` with all sources declared but disabled.
- Test harness with `respx`; committed HTML fixtures for one RBI and one SEBI page.

**Gate M0**
- `finreg fetch <url>` writes a blob and a `fetches` row, and a second identical call produces a 304 or a cache hit with **zero** new blobs.
- Throttle test: 10 requests to one mocked host take ≥ 18 s wall clock.
- Killing a run mid-fetch and re-running loses nothing.

If the HTTP layer is not right here, every later milestone inherits the defect. Do not proceed on "good enough".

---

## M1 — RBI end to end (5 days)

RBI first because it is the largest source, has the cleanest identifier scheme, and has the withdrawn-circulars list that everything else's temporal logic is modelled on.

**Build**
- `sources/rbi.py`: `verify()`, boundary bisection, ID enumeration, listing and detail parsers, PDF href extraction.
- Ingest Circulars Withdrawn, Master Directions, Master Circulars, Amendment Directions.
- PDF and HTML extraction paths, no OCR yet.
- Document-number parsing for RBI formats.

**Gate M1**
- ≥ 95% of enumerated RBI IDs in a 500-ID contiguous probe range resolve to either a parsed document or a classified 4xx. No unclassified outcomes.
- Boundary bisection locates the 2016-04-01 boundary in ≤ 25 requests.
- Manual spot-check of 25 RBI documents: title, date and reference number correct in ≥ 24.
- The withdrawn list is parsed and matched to ≥ 80% of its entries by `doc_id`.

**If the withdrawn-list match rate is below 50%, stop and re-examine `doc_id` construction before crawling anything else.** Every source's temporal logic depends on this join working.

---

## M2 — SEBI, CBDT, CBIC, MeitY, India Code (8 days)

**Build**
- `sources/sebi.py`: form-POST pagination, date-windowed queries, Active/Archive dual crawl.
- `sources/cbdt.py`: `verify()` determines pagination mechanism first, then crawl; legacy `.htm` and modern PDF paths.
- `sources/cbic.py`: `verify()` probes for the SPA's JSON API; falls back to legacy static tables; records which.
- `sources/meity.py`: small, mostly hand-listed document set; `verify()` locates current canonical URLs.
- `sources/indiacode.py`: probe OAI-PMH and REST first; fall back to handle traversal.
- OCR fallback path, table extraction, full normalisation pipeline.

**Gate M2**
- Every enabled source's `verify()` passes and prints the access method it selected.
- Every (regulator, quarter) cell from 2016-Q2 to current has ≥ 1 document, or a written explanation.
- OCR path demonstrated on ≥ 20 real scanned documents with mean confidence recorded.
- Aggregate `fetch_failures` rate below each source's configured `max_failure_rate`.

**Risk to watch.** CBIC's SPA and CBDT's SharePoint pagination are the two most likely to consume more time than budgeted. If either exceeds 3 days on its own, ship the other sources, mark it degraded in the corpus card, and move on. A corpus missing GST circulars is still a corpus; a semester spent on one scraper is not a project.

---

## M3 — Temporal resolution and citations (5 days)

**Build**
- Citation extraction with span recording and confidence.
- Supersession graph construction, cycle detection.
- Master Circular / Master Direction subsumption table parsing.
- `statutory_regime` tagging.
- DPDP phased-commencement table parsing.
- `v_in_force_as_of` and `finreg.temporal.query`.

**Gate M3**
- ≥ 80% of RBI and SEBI circulars have `status != 'unknown'`.
- Zero cycles remain unhandled in the supersession graph.
- 100% of direct-tax documents carry a `statutory_regime` value.
- Manual audit of 30 supersession links: ≥ 27 correct. Errors classified by cause.

**This is the milestone most likely to under-deliver, and that is acceptable.** If status resolution lands at 60% instead of 80%, report the real number, document why, and continue. A corpus that honestly says "I don't know if this is in force" is more useful than one that guesses.

---

## M4 — Quality, dedup, export, reporting (4 days)

**Build**
- MinHash dedup and canonical selection.
- All quality flags.
- `finreg export` with three views and the corpus card.
- `finreg report` producing Markdown + HTML QA report.
- `finreg qa gate` implementing all nine acceptance criteria as PASS/FAIL checks.

**Gate M4 — this is the Phase 1 exit gate.**
All nine acceptance criteria in `01-PRD-PHASE1.md` pass, including the 200-document stratified manual audit at ≥ 95% extraction fidelity.

---

## M5 — Full cold crawl and freeze (3 days, mostly waiting)

**Build**
- Run the complete cold crawl at default politeness.
- Regenerate export and corpus card.
- Write `reports/phase1-summary.md`: what was collected, per-source counts, coverage gaps, failure analysis, tuned threshold values with their evidence, and the honest limitations list.
- Tag the release.

**Gate M5**
- Cold crawl completes within 72 h.
- Immediate re-run adds zero blobs (AC-7).
- `phase1-summary.md` exists and its numbers are generated from the manifest, not typed by hand.

---

## Timeline

Roughly 28 working days of build plus crawl wall-clock. At 3–4 focused days a week alongside coursework, that is **8–10 calendar weeks**. Plan for 12.

## What to do if you fall behind

Cut in this order. Each cut is safe; the corpus remains coherent.

1. Drop MeitY DPDP (small corpus contribution, though it costs the best temporal benchmark material).
2. Drop CBIC GST (largest scraping risk, cleanly separable).
3. Reduce the window from 2016 to 2019 — but **never past 2025-11**, because the RBI consolidation and the ITA-2025 commencement must both stay inside it. Those two events are the corpus's distinguishing feature.
4. Drop table extraction to text-only — accepting that rate-table questions become unanswerable and saying so.

Do **not** cut: provenance, temporal status, licence tagging, or the manual audit. Those are what make it research rather than scraping.
