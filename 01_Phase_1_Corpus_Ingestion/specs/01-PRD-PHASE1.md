# 01 — Product Requirements, Phase 1

## Users of this deliverable

| User | Need |
|---|---|
| Phase 2 (retrieval + fine-tuning) | A Parquet corpus with clean text, stable IDs, and in-force metadata that can be filtered by date, regulator and status. |
| Phase 3 (benchmark authoring) | The ability to locate the authoritative source for any compliance question and cite it by URL and paragraph. |
| Project reviewers / examiners | Reproducibility: a single command that reconstructs the corpus from scratch, and a report showing what was collected and what failed. |
| The paper | Corpus statistics that are defensible and stated with their measurement method. |

## Functional requirements

### FR-1 Source acquisition
The system fetches documents from every source in `config/sources.yaml` within the configured date window. Each source declares its own discovery strategy (ID enumeration, paginated POST, API, DSpace handle traversal, static HTML index).

### FR-2 Provenance capture
For each fetched artefact the system records: canonical source URL, final URL after redirects, HTTP status, response headers of interest (`ETag`, `Last-Modified`, `Content-Type`, `Content-Length`), retrieval timestamp in UTC, SHA-256 of the response body, and the byte length.

### FR-3 Content-addressed storage
Raw bytes are written to `data/raw/<sha256[0:2]>/<sha256[2:4]>/<sha256>.<ext>`. Identical bytes fetched from two URLs are stored once and referenced twice.

### FR-4 Text extraction
PDFs and HTML are converted to plain text preserving paragraph and list boundaries, section headings, and table structure where present. Extraction records the extractor used and its version.

### FR-5 OCR fallback
When a PDF's embedded text layer yields fewer than a configured number of characters per page, the page is rasterised and OCR'd. OCR output is tagged `text_source: ocr` and carries a mean confidence score.

### FR-6 Structural parsing
Where a source exposes it, the system parses: document number (e.g. RBI circular reference, SEBI circular number, CBDT Circular No. n/YYYY), issue date, issuing department, addressee class, and subject line. These come from the listing page or document header, never from inference (invariant I3).

### FR-7 Citation extraction
The system extracts outbound references from document text — references to other circulars, to statutory sections, to regulations, and to superseded documents — into a `citations` table. Extraction is pattern-based and every extracted citation stores the exact matched span so it can be audited.

### FR-8 Temporal validity resolution
The system ingests RBI's withdrawn-circulars list and SEBI's archive listing, plus Master Direction / Master Circular consolidation statements, and populates `status`, `in_force_from`, `in_force_to` and `superseded_by`. See `06-TEMPORAL-VALIDITY-SPEC.md`.

### FR-9 Statutory regime tagging
Every direct-tax document is tagged with the statutory regime it operates under (`ITA_1961` or `ITA_2025`) based on its date and, where present, explicit statutory references. Documents that straddle or discuss both are tagged `both`.

### FR-10 Deduplication
Near-duplicate detection across the corpus (a circular reproduced verbatim inside a Master Circular, a document published in both English and a bilingual PDF). Duplicates are linked, not deleted.

### FR-11 Licence tagging
Every record carries a licence tag and attribution string per `07-LEGAL-AND-CRAWL-ETHICS.md`.

### FR-12 Quality gates
Records failing configured quality thresholds are flagged, counted in the QA report, and excluded from the default export view while remaining in the manifest.

### FR-13 Export
`finreg export` writes a Parquet dataset partitioned by `regulator` and `year`, plus a JSON corpus card recording generation timestamp, code commit, per-source counts, and known gaps.

### FR-14 Refresh
`finreg crawl --since <date>` performs an incremental update, fetching only documents not already in the manifest and re-checking a configurable sample of existing documents for revision.

### FR-15 Reporting
`finreg report` produces a Markdown + HTML QA report: per-source counts, date coverage histogram, extraction failure rates, OCR share, status distribution, duplicate clusters, and the top 50 unresolved failures.

## Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 | Full cold crawl completes in ≤ 72 h wall clock at 1 req/2 s/host with 6 hosts crawled concurrently. |
| NFR-2 | Any command is resumable after `SIGKILL` with no data loss and no duplicate work. |
| NFR-3 | Peak memory ≤ 4 GB; the pipeline must run on a laptop or a free-tier Colab instance. |
| NFR-4 | Total raw storage ≤ 40 GB. If exceeded, the crawl warns and continues; it does not silently truncate. |
| NFR-5 | No credentials, API keys or authenticated sessions are required. All sources are public. |
| NFR-6 | The manifest schema is versioned; migrations are explicit files, never implicit `ALTER` at runtime. |

## Acceptance criteria (Phase 1 exit gate)

All of the following must hold. Each is a check implemented in `finreg qa gate` and each prints PASS/FAIL with the measured value.

1. **AC-1 Provenance.** `SELECT COUNT(*) FROM documents WHERE source_url IS NULL OR retrieved_at IS NULL OR sha256 IS NULL` returns 0.
2. **AC-2 Resolvability.** A random sample of 200 records, stratified by regulator and year, has every `source_url` returning HTTP 200 and a document whose title matches the stored title (manual confirmation, logged in `reports/audit-YYYYMMDD.md`).
3. **AC-3 Extraction fidelity.** In the same 200-record audit, ≥ 95% of records have text that a human reader judges complete and correctly ordered. Failures are itemised by cause.
4. **AC-4 Coverage.** Every (regulator, quarter) cell in the window 2016-Q2 to the current quarter has at least one document, or an explicit documented explanation of why not.
5. **AC-5 Temporal status.** ≥ 80% of RBI and SEBI circulars have `status != 'unknown'`. Overall corpus ≥ 60%.
6. **AC-6 Licence.** 100% of records carry a licence tag. Records tagged `unverified` are excluded from the `training` export view and their count is reported.
7. **AC-7 Idempotency.** Running the full crawl twice back to back adds zero new blobs and zero new document rows.
8. **AC-8 Reproducibility.** `finreg export` writes a corpus card containing the git commit hash, and re-running export from an unchanged manifest produces byte-identical Parquet files.
9. **AC-9 Failure accounting.** `fetch_failures` is non-empty only with entries that have a terminal, classified reason. No `unknown error` rows.

## Deliberate non-goals

- No natural-language question answering, retrieval or ranking in Phase 1.
- No Hindi or other Indic-language documents in the initial corpus. Bilingual PDFs are captured but only the English text is extracted; the Hindi extraction path is a documented Phase 4 extension.
- No state-level regulation. Central regulators only.
- No case law, tribunal orders or judgments. SEBI adjudication orders are captured as an optional source but are off by default.
