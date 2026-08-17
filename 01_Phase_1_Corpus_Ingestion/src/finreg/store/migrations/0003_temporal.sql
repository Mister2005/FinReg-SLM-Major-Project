CREATE VIEW v_in_force_as_of AS
SELECT doc_id, regulator, doc_type, title, issue_date,
       in_force_from, in_force_to, status, statutory_regime
FROM documents;

-- Cycle findings from the supersession graph, persisted so the M4 QA report
-- can read them without re-running resolution (per 06-TEMPORAL-VALIDITY-
-- SPEC.md: cycles "must appear in the QA report").
CREATE TABLE temporal_issues (
    id           INTEGER PRIMARY KEY,
    issue_type   TEXT NOT NULL,
    detail       TEXT NOT NULL,
    doc_ids_json TEXT NOT NULL,
    detected_at  TEXT NOT NULL
);
