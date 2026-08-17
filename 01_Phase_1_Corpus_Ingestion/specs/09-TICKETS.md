# 09 — Tickets

Dependency-ordered. Each ticket states its dependencies, the work, and acceptance criteria written as assertions that a test can express. Do not start a ticket whose dependencies are open.

---

## M0 — Skeleton and HTTP substrate

**T-001 Repository scaffold** — deps: none
Create the tree from `README.md`. `pyproject.toml` with pinned deps: `httpx`, `selectolax`, `pypdfium2`, `pdfplumber`, `datasketch`, `pyarrow`, `typer`, `structlog`, `pytest`, `respx`. `.gitignore` excludes `data/`.
*AC:* `uv sync` succeeds; `python -c "import finreg"` succeeds; `data/` is gitignored.

**T-002 Config loader** — deps: T-001
Load and validate `config/sources.yaml`. Fail loudly with a named field on any missing required key.
*AC:* Loading a config with `contact_email` absent raises `ConfigError` naming the field. Loading the shipped config succeeds. Config SHA-256 is exposed as a property.

**T-003 Structured logging** — deps: T-001
`structlog` to JSONL at `reports/logs/<run_id>.jsonl` plus human-readable console output.
*AC:* Every log line is valid JSON with `run_id`, `ts`, `level`, `event`.

**T-004 Manifest schema and migrations** — deps: T-001
Apply the DDL from doc 04. Migration runner reads numbered SQL files from `src/finreg/store/migrations/`.
*AC:* Fresh DB applies to the latest version; re-running applies nothing; `schema_version` reflects the applied version; all CHECK constraints reject invalid values in a test.

**T-005 Blob store** — deps: T-004
Content-addressed write and read.
*AC:* Writing identical bytes twice creates one file and one `blobs` row. Path matches `data/raw/xx/yy/<sha>.<ext>`. Extension falls back to magic-byte sniffing then `bin`.

**T-006 Token-bucket throttle** — deps: T-001
Per-host minimum interval.
*AC:* 10 sequential requests at `min_interval_seconds=2.0` take ≥ 18 s. Two different hosts do not block each other.

**T-007 robots.txt handling** — deps: T-006
Fetch, cache per host per run, evaluate paths.
*AC:* A disallowed path raises `RobotsDisallowed` and records a skip row; robots.txt is fetched once per host per run; an unreachable robots.txt is treated as allow-with-warning and logged.

**T-008 HTTP client** — deps: T-005, T-006, T-007
`get`/`post` per the TRD contract, retry/backoff with jitter, `Retry-After`, conditional requests, mandatory User-Agent.
*AC:* Client construction without `contact_email` raises. A mocked 429 with `Retry-After: 5` waits ≥ 5 s. A mocked 304 produces no new blob and `from_cache=True`. Five 503s exhaust retries and raise a classified error.

**T-009 Failure recorder** — deps: T-004, T-008
Write and upsert `fetch_failures` with classified reason codes.
*AC:* Every code in the TRD taxonomy is produced by at least one test. No code path can write a failure without a `reason_code`.

**T-010 CLI skeleton** — deps: T-002, T-003, T-008
`finreg` with subcommands `fetch`, `crawl`, `extract`, `resolve`, `dedup`, `export`, `report`, `qa`. Each records a `crawl_runs` row with git commit and config hash.
*AC:* `finreg --help` lists all subcommands; every invocation opens and closes a `crawl_runs` row including on exception.

---

## M1 — RBI

**T-011 Source protocol and registry** — deps: T-010
`Source` protocol, registry, `finreg sources verify` command.
*AC:* A source disabled in config is not registered. `verify` runs all enabled sources and exits non-zero if any fails.

**T-012 RBI listing parser** — deps: T-011
Parse the notification listing into `(date, title, detail_url, pdf_url)`. Fixture-driven.
*AC:* Committed fixture yields the expected records with correct dates; a fixture with the table element removed raises `ListingParseFailed`.

**T-013 RBI detail parser** — deps: T-012
Extract title, date, `RBI/<FY>/<seq>` reference, departmental reference, addressee, body region, PDF href.
*AC:* On three committed fixtures spanning 2016, 2021 and 2026 layouts, all fields parse or are explicitly NULL with a `metadata_gaps` entry. Never a fabricated value.

**T-014 RBI boundary bisection** — deps: T-013
Binary search for the lowest ID with date ≥ window start.
*AC:* Against a mocked ID→date function, converges in ≤ 25 requests over a 14,000-ID range and returns the exact boundary.

**T-015 RBI ID enumeration** — deps: T-014, T-009
Walk the ID range, resumable via `source_state.cursor_json`.
*AC:* Interrupting after N IDs and resuming continues at N+1. 404s record `http_4xx` and do not halt the walk. Re-running a completed range issues zero non-conditional requests.

**T-016 RBI withdrawn-circulars ingest** — deps: T-013
Parse the withdrawn listing into a join-ready table.
*AC:* ≥ 80% of parsed entries match an existing `doc_id`; unmatched entries are retained with their raw text for later resolution.

**T-017 RBI Master Directions / Master Circulars / Amendment Directions** — deps: T-013
Three additional listing crawlers reusing the detail parser.
*AC:* Each produces `documents` rows with the correct `doc_type`; subsumption appendices are stored as `tables_extracted` rows.

**T-018 PDF extraction — text layer** — deps: T-005
`pypdfium2` per-page extraction with per-page char counts and the decision rule from doc 05.
*AC:* A text PDF yields `pdf_layer`; a scanned PDF is routed to OCR; a corrupt PDF records `pdf_corrupt` after both extractors fail.

**T-019 pdftotext fallback** — deps: T-018
*AC:* A PDF that pypdfium2 renders with < 250 chars/page but has a text layer is recovered as `pdftotext` and its char count exceeds the pypdfium2 result.

**T-020 HTML extraction with per-source selectors** — deps: T-013
*AC:* Extracted RBI text contains the operative paragraphs and contains none of: navigation labels, "More Links", "Follow RBI", the accessibility controls, or the footer disclaimer. Numbered clause lists retain their numbering.

**T-021 Document-number parsing** — deps: T-020
Patterns from doc 05 for all regulators.
*AC:* Each documented pattern is matched by a test using a real observed example. A string matching no pattern yields NULL plus a `metadata_gaps` entry, never a partial guess.

---

## M2 — Remaining sources and extraction depth

**T-022 SEBI form-POST pagination** — deps: T-011
Replay the listing form POST; support the date-range filter.
*AC:* Page 2 returns 25 hrefs disjoint from page 1; a date-windowed query returns only in-window dates; the record-count string parses to an integer.

**T-023 SEBI detail parser** — deps: T-022
*AC:* `doc_id` is derived from the trailing integer in the detail URL; title, date and department parse; SEBI reference number parses when present and is NULL with a gap note when not.

**T-024 SEBI Active/Archive dual crawl** — deps: T-023
*AC:* Both views are crawled; Archive membership sets `status`; Active membership sets `status = in_force`; a document in neither remains `unknown`.

**T-025 SEBI Regulations, Master Circulars, Rules, Guidelines, Gazette** — deps: T-023
*AC:* Each `sid/ssid` pair from doc 03 yields documents with the correct `doc_type`.

**T-026 CBDT source verify and pagination discovery** — deps: T-011
`verify()` determines whether listings paginate by query string or postback and logs the finding.
*AC:* `verify()` prints the discovered mechanism and the module crawls using it; if neither is determinable, `verify()` fails with a message naming what was tried.

**T-027 CBDT crawl (circulars, notifications, instructions)** — deps: T-026, T-018
*AC:* Legacy `.htm` and modern PDF documents both ingest; `Circular No. n/YYYY` parses; character-spacing repair fires on affected legacy pages and is flagged.

**T-028 CBIC API probe and crawl** — deps: T-011
`verify()` probes for the SPA's JSON API; falls back to legacy static tables.
*AC:* The selected access method is recorded in `source_access_methods`; documents ingest via whichever path succeeded; if both fail, the source is marked degraded and does not block other sources.

**T-029 MeitY DPDP document set** — deps: T-011
*AC:* The Act, the Rules, the enforcement/commencement notifications and the Board notifications are all present; the phased-commencement schedule is stored as a `tables_extracted` row; the 13-vs-14 November date discrepancy is recorded in `metadata_gaps`.

**T-030 India Code OAI/REST probe** — deps: T-011
*AC:* `verify()` probes OAI-PMH and REST and records which, if either, responded; the crawler uses the best available; the fallback handle traversal works against a committed fixture.

**T-031 India Code statute ingest** — deps: T-030
The 15 statutes listed in doc 03.
*AC:* All 15 present with full text and `doc_type = act`; each carries `licence = statutory_s52_1_q`.

**T-032 OCR fallback** — deps: T-018
`ocrmypdf` invocation, confidence capture, OCR'd PDF stored as a linked blob.
*AC:* A scanned fixture yields text with a recorded mean confidence; text below threshold is flagged `low_ocr_confidence`; `text_source = ocr`.

**T-033 Table extraction** — deps: T-018
`pdfplumber` lattice and stream, best-of selection, pipe-delimited serialisation into linear text.
*AC:* A fixture rate table extracts with correct row and column counts and its serialisation appears in the document text with headers intact.

**T-034 Normalisation pipeline** — deps: T-020, T-032
All eight steps from doc 05, in order.
*AC:* Each step has a unit test with a real observed input. Character-spacing repair converts `C i r c u l a r  N o .` to `Circular No.` and sets the flag. No step alters any digit, currency symbol, percentage or section reference in a property-based test over 1,000 generated strings.

---

## M3 — Temporal and citations

**T-035 Citation extraction** — deps: T-034
Circular references, statutory sections, supersession language, with spans and confidence.
*AC:* Each citation type is matched by a test on a real observed sentence; every row stores `char_start`/`char_end` that slice back to `raw_span` exactly; unresolvable targets are `unresolved`, never dropped.

**T-036 Supersession graph** — deps: T-035, T-016, T-024
Build edges, detect cycles.
*AC:* A synthetic cycle is detected, both nodes set to `unknown`, and the cycle logged. Withdrawn beats superseded when both apply.

**T-037 Master consolidation parsing** — deps: T-017, T-035
Parse subsumption appendices into supersession edges.
*AC:* On a real Master Circular fixture, the subsumed-circular list parses to the correct count and each entry resolves or is retained as unresolved.

**T-038 Temporal resolver** — deps: T-036, T-037
The six-step algorithm from doc 06.
*AC:* Step 5 is enforced — a test asserts that a document with no supersession evidence remains `unknown` and is never promoted to `in_force`. `v_in_force_as_of` and `in_force_as_of()` return in-force and unknown as **separate** lists.

**T-039 Statutory regime tagging** — deps: T-035
*AC:* 100% of direct-tax documents receive a regime value; a document citing both Acts is tagged `both`; a pre-2026-04-01 document citing only ITA 2025 is tagged `ITA_2025` (date alone does not decide).

---

## M4 — Quality, export, reporting

**T-040 Deduplication** — deps: T-034
MinHash LSH, cluster formation, canonical selection by the documented precedence.
*AC:* Two byte-different but textually identical documents cluster; the canonical choice follows the precedence rules; non-canonical members retain their rows and are excluded from `corpus_clean`.

**T-041 Quality flags** — deps: T-040
All eight flags from doc 05.
*AC:* Each flag has a test that triggers it and one that does not. Flags are additive, never mutually exclusive.

**T-042 Export and corpus card** — deps: T-041, T-038
Three Parquet views, partitioned; corpus card JSON.
*AC:* Partition paths match the documented layout; documents with no date land in `year=0000`; re-running export on an unchanged manifest produces byte-identical files; the corpus card contains the git commit and non-empty `known_gaps` if any gaps exist.

**T-043 QA report** — deps: T-042
Markdown + HTML with per-source counts, coverage histogram, failure breakdown, OCR share, status distribution, duplicate clusters, top 50 unresolved failures.
*AC:* Every number in the report is produced by a manifest query; the report generator contains no hardcoded figures.

**T-044 `finreg qa gate`** — deps: T-043
All nine acceptance criteria as PASS/FAIL checks with measured values.
*AC:* Each of AC-1 … AC-9 is implemented and prints its measured value; the command exits non-zero if any FAILs; AC-2 and AC-3 prompt for the manual audit file and fail if it is absent or older than the last export.

---

## Ticket hygiene

- A ticket is done when its acceptance criteria are expressed as passing tests, not when the code "works".
- No ticket may introduce a `TODO`, a stub, or a code path that returns mock data (invariant I8).
- Any ticket that discovers a source behaves differently from doc 03 must **update doc 03 in the same commit**, marking the corrected pattern as verified with the date. The spec is a living record of what is true, not a record of what was assumed.
