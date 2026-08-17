# 04 — Data Model

## Blob store

```
data/raw/<sha[0:2]>/<sha[2:4]>/<sha>.<ext>
```

`ext` is derived from `Content-Type`, falling back to magic-byte sniffing, falling back to `bin`. Blobs are immutable and never deleted by the pipeline.

Rationale for content addressing: RBI publishes the same PDF under differently-named URLs, and Master Circulars reproduce circular text verbatim. Deduplicating at the byte level costs nothing and removes a whole class of double-counting error from corpus statistics.

## Manifest DDL (`data/manifest.db`, SQLite, WAL)

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE schema_version (
    version     INTEGER NOT NULL,
    applied_at  TEXT    NOT NULL
);

CREATE TABLE blobs (
    sha256        TEXT PRIMARY KEY,
    byte_length   INTEGER NOT NULL,
    content_type  TEXT,
    extension     TEXT,
    stored_path   TEXT NOT NULL,
    first_seen_at TEXT NOT NULL
);

CREATE TABLE fetches (
    id             INTEGER PRIMARY KEY,
    source_url     TEXT NOT NULL,
    final_url      TEXT NOT NULL,
    http_status    INTEGER NOT NULL,
    etag           TEXT,
    last_modified  TEXT,
    content_type   TEXT,
    byte_length    INTEGER,
    sha256         TEXT REFERENCES blobs(sha256),
    retrieved_at   TEXT NOT NULL,
    from_cache     INTEGER NOT NULL DEFAULT 0,
    source_name    TEXT NOT NULL
);
CREATE INDEX idx_fetches_url  ON fetches(source_url);
CREATE INDEX idx_fetches_time ON fetches(retrieved_at);

CREATE TABLE documents (
    doc_id            TEXT PRIMARY KEY,
    regulator         TEXT NOT NULL,
    source_name       TEXT NOT NULL,
    doc_type          TEXT NOT NULL,
    doc_number        TEXT,
    departmental_ref  TEXT,
    title             TEXT NOT NULL,
    issue_date        TEXT,
    department        TEXT,
    addressee         TEXT,
    source_url        TEXT NOT NULL,
    pdf_url           TEXT,
    html_sha256       TEXT REFERENCES blobs(sha256),
    pdf_sha256        TEXT REFERENCES blobs(sha256),
    retrieved_at      TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'unknown',
    in_force_from     TEXT,
    in_force_to       TEXT,
    superseded_by     TEXT REFERENCES documents(doc_id),
    statutory_regime  TEXT,
    licence           TEXT NOT NULL,
    attribution       TEXT,
    revision_of       TEXT REFERENCES documents(doc_id),
    metadata_gaps     TEXT,
    CHECK (status IN ('in_force','superseded','withdrawn','repealed','unknown')),
    CHECK (licence IN ('godl_india','statutory_s52_1_q','gov_site_terms','unverified'))
);
CREATE INDEX idx_documents_reg_date ON documents(regulator, issue_date);
CREATE INDEX idx_documents_status   ON documents(status);
CREATE INDEX idx_documents_number   ON documents(doc_number);

CREATE TABLE texts (
    text_id            INTEGER PRIMARY KEY,
    doc_id             TEXT NOT NULL REFERENCES documents(doc_id),
    blob_sha256        TEXT NOT NULL REFERENCES blobs(sha256),
    text_source        TEXT NOT NULL,
    extractor          TEXT NOT NULL,
    extractor_version  TEXT NOT NULL,
    page_count         INTEGER,
    char_count         INTEGER NOT NULL,
    mean_ocr_conf      REAL,
    body               TEXT NOT NULL,
    extracted_at       TEXT NOT NULL,
    CHECK (text_source IN ('pdf_layer','pdftotext','ocr','html'))
);
CREATE INDEX idx_texts_doc ON texts(doc_id);

CREATE TABLE tables_extracted (
    table_id     INTEGER PRIMARY KEY,
    doc_id       TEXT NOT NULL REFERENCES documents(doc_id),
    page_number  INTEGER,
    n_rows       INTEGER NOT NULL,
    n_cols       INTEGER NOT NULL,
    cells_json   TEXT NOT NULL,
    extractor    TEXT NOT NULL
);

CREATE TABLE citations (
    citation_id     INTEGER PRIMARY KEY,
    doc_id          TEXT NOT NULL REFERENCES documents(doc_id),
    raw_span        TEXT NOT NULL,
    char_start      INTEGER NOT NULL,
    char_end        INTEGER NOT NULL,
    citation_type   TEXT NOT NULL,
    target_doc_id   TEXT REFERENCES documents(doc_id),
    target_act      TEXT,
    target_section  TEXT,
    relation        TEXT,
    confidence      REAL NOT NULL,
    CHECK (citation_type IN ('circular','master_direction','statute_section','regulation','rule','notification','unresolved')),
    CHECK (relation IS NULL OR relation IN ('supersedes','amends','withdraws','refers','issued_under'))
);
CREATE INDEX idx_citations_doc    ON citations(doc_id);
CREATE INDEX idx_citations_target ON citations(target_doc_id);

CREATE TABLE duplicates (
    cluster_id   INTEGER NOT NULL,
    doc_id       TEXT NOT NULL REFERENCES documents(doc_id),
    is_canonical INTEGER NOT NULL,
    similarity   REAL NOT NULL,
    PRIMARY KEY (cluster_id, doc_id)
);

CREATE TABLE quality_flags (
    doc_id  TEXT NOT NULL REFERENCES documents(doc_id),
    flag    TEXT NOT NULL,
    detail  TEXT,
    PRIMARY KEY (doc_id, flag)
);

CREATE TABLE fetch_failures (
    id           INTEGER PRIMARY KEY,
    source_url   TEXT NOT NULL,
    source_name  TEXT NOT NULL,
    reason_code  TEXT NOT NULL,
    detail       TEXT,
    attempts     INTEGER NOT NULL,
    first_seen   TEXT NOT NULL,
    last_seen    TEXT NOT NULL,
    resolved     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_failures_code ON fetch_failures(reason_code);

CREATE TABLE crawl_runs (
    run_id        TEXT PRIMARY KEY,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    git_commit    TEXT NOT NULL,
    config_sha256 TEXT NOT NULL,
    command       TEXT NOT NULL,
    exit_status   TEXT
);

CREATE TABLE source_state (
    source_name  TEXT PRIMARY KEY,
    cursor_json  TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
```

### Field notes

**`doc_id`** is deterministic and stable: `<regulator>:<source_name>:<natural_key>`, where the natural key is the site's own identifier — RBI's `Id`, SEBI's trailing document integer, CBIC's `view-pdf` ID, India Code's handle. Never hash the title; titles get corrected.

**`doc_type`** controlled vocabulary: `circular`, `master_circular`, `master_direction`, `amendment_direction`, `notification`, `regulation`, `rule`, `act`, `guideline`, `instruction`, `office_memorandum`, `faq`, `press_release`, `order`.

**`statutory_regime`** ∈ {`ITA_1961`, `ITA_2025`, `both`, `NULL`}. `NULL` for non-direct-tax documents.

**`revision_of`** links a re-fetched document whose bytes changed to its earlier version. Both rows persist (invariant I2).

**`metadata_gaps`** is a JSON array of strings naming fields that could not be determined and why — e.g. `["issue_date: not present on listing or in document header", "gazette_date: sources disagree 13 vs 14 Nov 2025"]`. This field is how invariant I3 becomes auditable.

**`confidence`** on citations is the pattern-matcher's own score, not a model output. A regex with an exact document-number match scores 1.0; a fuzzy title match scores lower and stays `unresolved` below the configured threshold.

## Parquet export schema

`data/export/corpus/regulator=<r>/year=<yyyy>/part-*.parquet`

| Column | Type | Note |
|---|---|---|
| `doc_id` | string | |
| `regulator` | string | partition key |
| `doc_type` | string | |
| `doc_number` | string | nullable |
| `title` | string | |
| `issue_date` | date32 | nullable |
| `year` | int16 | partition key, derived from `issue_date`; documents with no date go to `year=0000` |
| `department` | string | nullable |
| `text` | string | canonical extracted text |
| `text_source` | string | |
| `char_count` | int32 | |
| `status` | string | |
| `in_force_from` | date32 | nullable |
| `in_force_to` | date32 | nullable |
| `superseded_by` | string | nullable |
| `statutory_regime` | string | nullable |
| `source_url` | string | |
| `pdf_url` | string | nullable |
| `sha256` | string | of the canonical source blob |
| `retrieved_at` | timestamp[us, UTC] | |
| `licence` | string | |
| `attribution` | string | |
| `quality_flags` | list\<string\> | |
| `is_duplicate` | bool | true for non-canonical cluster members |

### Export views

- **`corpus/`** — everything, including `unverified` licence and flagged records.
- **`corpus_clean/`** — excludes duplicates, quality-flagged records, and `licence = 'unverified'`. This is the view Phase 2 consumes by default.
- **`corpus_in_force/`** — `corpus_clean` filtered to `status = 'in_force'` as of the export date.

Three views, one manifest. Never maintain three corpora.

## Corpus card

`data/export/corpus_card.json`, regenerated on every export:

```json
{
  "generated_at": "<UTC ISO 8601>",
  "git_commit": "<sha>",
  "config_sha256": "<sha>",
  "window": {"start": "2016-04-01", "end": "<export date>"},
  "counts": {
    "by_regulator": {},
    "by_doc_type": {},
    "by_status": {},
    "by_text_source": {},
    "by_licence": {}
  },
  "coverage": {"missing_quarters": []},
  "quality": {
    "ocr_share": 0.0,
    "flagged_share": 0.0,
    "duplicate_clusters": 0,
    "extraction_failure_count": 0
  },
  "known_gaps": [],
  "source_access_methods": {}
}
```

`known_gaps` is populated from `metadata_gaps` aggregation and from any source whose `verify()` reported a degraded access path. It is written to the corpus card so that the paper's limitations section is generated from measurement, not memory.
