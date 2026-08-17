-- A document can carry two independent reference numbers: its own
-- doc_number (RBI/<dept>/<FY>/<seq>) and, for Master Directions, a separate
-- self-identifying series number (e.g. "Master Direction No. 2/2016-17")
-- that OTHER documents cite it by. See normalize/doc_number.py's
-- match_rbi_master_direction_series.
ALTER TABLE documents ADD COLUMN alias_doc_number TEXT;
CREATE INDEX idx_documents_alias_number ON documents(alias_doc_number);
