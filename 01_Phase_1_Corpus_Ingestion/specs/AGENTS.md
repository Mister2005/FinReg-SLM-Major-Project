# AGENTS.md — Engineering Invariants

Read before writing any code. These are not preferences. A change that violates any invariant is rejected regardless of test status.

## I1 — Provenance is mandatory and immutable

Every stored artefact carries, at minimum: `source_url`, `retrieved_at` (UTC, ISO 8601), `sha256` of the exact bytes retrieved, and `http_status`. A record missing any of these is invalid and must fail the manifest write, not warn.

Derived text records additionally carry `blob_sha256` (the parent raw file) and `extractor_version`. Never write derived text without a resolvable parent blob.

## I2 — Raw bytes are never mutated

`data/raw/` is append-only and content-addressed. Extraction, normalisation and cleanup produce new files under `data/work/`. If a re-crawl returns different bytes for the same logical document, that is a **new blob and a new manifest row**, never an overwrite. Document revisions are first-class data, not a cache-invalidation problem.

## I3 — No fabricated metadata

If a field cannot be determined from the source, it is `NULL`. Never infer a circular date from a filename, never guess a department, never synthesise a document number. A `NULL` with a `metadata_gaps` entry is correct; a plausible-looking guess is a defect that silently corrupts every downstream evaluation.

This extends to counts and progress reporting: report what was actually fetched, never an estimate presented as a fact.

## I4 — Politeness is enforced in one place

All outbound HTTP goes through `finreg.http.client`. No module may use `requests`/`httpx` directly. The client enforces per-host rate limiting, robots.txt, retry/backoff, caching and the identifying User-Agent. There is no bypass flag.

Default: **1 request per 2 seconds per host, concurrency 1 per host.** Raising this requires editing `config/sources.yaml` and is a deliberate, reviewed act.

## I5 — Every run is resumable and idempotent

Any command may be killed at any point and re-run. Work already completed is skipped by consulting the manifest, not by a local in-memory set. Re-running a completed crawl must produce zero new blobs and zero new manifest rows.

## I6 — Temporal validity is never assumed

A document's presence in the corpus does not mean it is in force. Every record carries `in_force_from`, `in_force_to` (nullable), and `status` ∈ {`in_force`, `superseded`, `withdrawn`, `repealed`, `unknown`}. `unknown` is an acceptable and honest value. Defaulting to `in_force` because it is convenient is prohibited.

## I7 — Failures are recorded, not swallowed

Every fetch or extraction failure writes a row to `fetch_failures` with the URL, attempt count, terminal error and timestamp. A crawl that "succeeded" while silently dropping 400 documents is worse than one that fails loudly. The QA report surfaces failure counts per source; a source with an unexplained failure rate above its configured threshold blocks the export.

## I8 — Code style

Python 3.11+. Type-annotated. No inline comments explaining what the code does — the code says that. Docstrings only on public module entry points and only where behaviour is non-obvious. No placeholder functions, no `TODO` stubs committed, no mock data paths. If a component is not implemented, it does not exist in the tree.

Dependencies are pinned in `pyproject.toml`. Prefer the standard library. Justify each third-party dependency in the PR description.

## I9 — Configuration over code

Source endpoints, date windows, rate limits, thresholds and retry policy live in `config/sources.yaml`. Changing which years are crawled must never require a code edit.

## I10 — The manifest is the single source of truth

The SQLite manifest at `data/manifest.db` is authoritative. The filesystem is a blob store; Parquet exports are snapshots. Any question about corpus state is answered by querying the manifest, never by walking directories.

## I11 — Licence tags travel with the data

Every record carries `licence` and `attribution_required`. Records whose licence status could not be established are tagged `licence: unverified` and are **excluded from any training-data export** while remaining available for retrieval-only use. See `docs/07-LEGAL-AND-CRAWL-ETHICS.md`.

## I12 — Do not build Phase 2 in Phase 1

No tokenisation, no chunking-for-embedding, no model code, no benchmark authoring. Phase 1 stops at a clean, queryable, versioned corpus with a Parquet export. Scope creep here is the most likely way this project runs out of semester.
