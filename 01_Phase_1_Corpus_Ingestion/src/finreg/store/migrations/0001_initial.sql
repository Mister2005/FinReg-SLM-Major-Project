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
