-- No FK on matched_doc_id: the withdrawn listing is crawled before the
-- notification crawl per source priority order, so the referenced doc_id
-- usually does not exist yet. Resolved later by the temporal resolver (T-038).
CREATE TABLE withdrawn_circulars (
    id              INTEGER PRIMARY KEY,
    source_name     TEXT NOT NULL,
    source_url      TEXT NOT NULL,
    raw_circular_no TEXT NOT NULL,
    raw_title       TEXT NOT NULL,
    raw_date        TEXT,
    parsed_date     TEXT,
    matched_doc_id  TEXT,
    retrieved_at    TEXT NOT NULL
);
CREATE INDEX idx_withdrawn_matched ON withdrawn_circulars(matched_doc_id);
