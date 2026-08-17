from __future__ import annotations

import sqlite3
import unicodedata

MIN_OCR_CONFIDENCE_DEFAULT = 0.70
SHORT_DOCUMENT_MIN_CHARS = 200
HIGH_NONASCII_RATIO_THRESHOLD = 0.15
TABLE_HEAVY_MIN_TABLES = 3
TABLE_HEAVY_MAX_CHARS = 500

_DEVANAGARI_START, _DEVANAGARI_END = 0x0900, 0x097F


def flag_low_ocr_confidence(
    text_source: str, mean_ocr_conf: float | None, min_confidence: float = MIN_OCR_CONFIDENCE_DEFAULT
) -> bool:
    if text_source != "ocr" or mean_ocr_conf is None:
        return False
    return mean_ocr_conf < min_confidence


def flag_short_document(char_count: int, doc_type: str) -> bool:
    if doc_type == "notification":
        return False
    return char_count < SHORT_DOCUMENT_MIN_CHARS


def flag_high_nonascii_ratio(text: str) -> bool:
    if not text:
        return False
    devanagari_count = sum(1 for ch in text if _DEVANAGARI_START <= ord(ch) <= _DEVANAGARI_END)
    if devanagari_count / len(text) > 0.5:
        return False  # known-Devanagari document, exempted per doc 05
    nonascii_count = sum(1 for ch in text if ord(ch) > 127)
    return (nonascii_count / len(text)) > HIGH_NONASCII_RATIO_THRESHOLD


def flag_no_date(issue_date: str | None) -> bool:
    return issue_date is None


def flag_table_heavy_low_text(table_count: int, char_count: int) -> bool:
    return table_count >= TABLE_HEAVY_MIN_TABLES and char_count < TABLE_HEAVY_MAX_CHARS


def flag_extraction_partial(page_count: int | None, chars_per_page: list[int]) -> bool:
    """Pure function over an ExtractionResult's own fields (extract/pdf.py's
    PdfExtractionResult) — evaluate this at extraction time. The `texts`
    table doesn't persist a per-page character-count breakdown, so this flag
    cannot be recomputed later from stored data alone; a caller wiring a real
    extraction pipeline should call this immediately after extract_pdf()
    and pass the result into set_flag(), not try to reconstruct it here."""
    if page_count is None:
        return False
    pages_with_text = sum(1 for c in chars_per_page if c > 0)
    return pages_with_text < page_count


def set_flag(conn: sqlite3.Connection, doc_id: str, flag: str, detail: str | None = None) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO quality_flags (doc_id, flag, detail) VALUES (?, ?, ?)",
        (doc_id, flag, detail),
    )
    conn.commit()


def compute_and_store_flags(conn: sqlite3.Connection) -> int:
    """Applies every flag computable from stored manifest data (all except
    extraction_partial, which needs per-page data only available at
    extraction time — see flag_extraction_partial's docstring — and
    duplicate_non_canonical, which dedup/minhash.py's run_dedup() sets
    directly since it already has that information)."""
    rows = conn.execute(
        """
        SELECT d.doc_id, d.doc_type, d.issue_date, t.text_source, t.mean_ocr_conf,
               t.char_count, t.body
        FROM documents d
        LEFT JOIN texts t ON t.doc_id = d.doc_id
        """
    ).fetchall()

    count = 0
    for row in rows:
        if flag_no_date(row["issue_date"]):
            set_flag(conn, row["doc_id"], "no_date")
            count += 1

        if row["char_count"] is not None:
            if flag_short_document(row["char_count"], row["doc_type"]):
                set_flag(conn, row["doc_id"], "short_document")
                count += 1
            if flag_low_ocr_confidence(row["text_source"], row["mean_ocr_conf"]):
                set_flag(conn, row["doc_id"], "low_ocr_confidence")
                count += 1

        if row["body"]:
            if flag_high_nonascii_ratio(row["body"]):
                set_flag(conn, row["doc_id"], "high_nonascii_ratio")
                count += 1

        table_count = conn.execute(
            "SELECT COUNT(*) FROM tables_extracted WHERE doc_id = ?", (row["doc_id"],)
        ).fetchone()[0]
        if row["char_count"] is not None and flag_table_heavy_low_text(table_count, row["char_count"]):
            set_flag(conn, row["doc_id"], "table_heavy_low_text")
            count += 1

    return count


def set_duplicate_non_canonical_flags(conn: sqlite3.Connection) -> int:
    rows = conn.execute("SELECT doc_id FROM duplicates WHERE is_canonical = 0").fetchall()
    for row in rows:
        set_flag(conn, row["doc_id"], "duplicate_non_canonical")
    return len(rows)


def persist_normalization_flags(conn: sqlite3.Connection, doc_id: str, flags: list[str]) -> None:
    """charspace_repaired (and any future normalize/pipeline.py flag) is only
    knowable at normalization time — the stored `texts.body` is already
    normalized, so it can't be reconstructed afterward. A caller running
    normalize.pipeline.normalize() should pass its NormalizationResult.flags
    straight through here."""
    for flag in flags:
        set_flag(conn, doc_id, flag)
