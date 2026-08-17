from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from finreg.extract.pdf import PdfCorrupt
from finreg.extract.router import ContentTypeUnexpected, extract
from finreg.http.client import Client, HostPolicy
from finreg.normalize.pipeline import normalize
from finreg.qa.flags import persist_normalization_flags
from finreg.store.citations import extract_and_store_citations
from finreg.store.failures import ReasonCode, record_failure

@dataclass(frozen=True)
class SourceCrawlResult:
    source_name: str
    documents_touched: int


def _crawl_rbi_notifications(
    client: Client, conn: sqlite3.Connection, policy: HostPolicy, limit: int | None, window_start: date
) -> SourceCrawlResult:
    from finreg.sources.rbi import bisect_window_boundary, find_id_max, ingest_withdrawn_circulars, enumerate_ids

    ingest_withdrawn_circulars(client, conn, policy)

    id_max = find_id_max(client, policy)
    id_min = bisect_window_boundary(client, policy, 1, id_max, window_start)

    range_end = id_max if limit is None else min(id_max, id_min + limit - 1)
    count = sum(1 for _ in enumerate_ids(client, conn, policy, id_min, range_end))
    return SourceCrawlResult("rbi_notifications", count)


def _crawl_rbi_master_directions(
    client: Client, conn: sqlite3.Connection, policy: HostPolicy, limit: int | None, window_start: date
) -> SourceCrawlResult:
    from finreg.sources.rbi import SUPPLEMENTAL_LISTINGS, ingest_supplemental_listing

    total = 0
    for listing in SUPPLEMENTAL_LISTINGS:
        total += ingest_supplemental_listing(client, conn, policy, listing, limit=limit)
    return SourceCrawlResult("rbi_master_directions", total)


def _crawl_sebi_circulars(
    client: Client, conn: sqlite3.Connection, policy: HostPolicy, limit: int | None, window_start: date
) -> SourceCrawlResult:
    from finreg.sources.sebi import SECTIONS, crawl_section_all_pages

    section = SECTIONS["sebi_circulars"]
    count = crawl_section_all_pages(client, conn, policy, section, archive=False, max_pages=limit)
    return SourceCrawlResult("sebi_circulars", count)


def _crawl_indiacode_statutes(
    client: Client, conn: sqlite3.Connection, policy: HostPolicy, limit: int | None, window_start: date
) -> SourceCrawlResult:
    from finreg.sources.indiacode import STATUTE_TARGETS, crawl_statutes

    not_found = crawl_statutes(client, conn, policy)
    return SourceCrawlResult("indiacode_statutes", len(STATUTE_TARGETS) - len(not_found))


def _crawl_cbic_circulars(
    client: Client, conn: sqlite3.Connection, policy: HostPolicy, limit: int | None, window_start: date
) -> SourceCrawlResult:
    from finreg.sources.cbic import crawl_legacy_circulars

    count = crawl_legacy_circulars(client, conn, policy)
    return SourceCrawlResult("cbic_circulars", count)


CRAWL_WRAPPERS = {
    "rbi_notifications": _crawl_rbi_notifications,
    "rbi_master_directions": _crawl_rbi_master_directions,
    "sebi_circulars": _crawl_sebi_circulars,
    "indiacode_statutes": _crawl_indiacode_statutes,
    "cbic_circulars": _crawl_cbic_circulars,
}


def crawl_source(
    source_name: str,
    client: Client,
    conn: sqlite3.Connection,
    policy: HostPolicy,
    limit: int | None = None,
    window_start: date = date(2016, 4, 1),
) -> SourceCrawlResult:
    wrapper = CRAWL_WRAPPERS.get(source_name)
    if wrapper is None:
        return SourceCrawlResult(source_name, 0)
    return wrapper(client, conn, policy, limit, window_start)


# RBI notifications' real content lives in the HTML body (extract/router
# needs a content_selector for that path). Everything else — including RBI's
# own Master Directions/Circulars/Amendment Directions, whose detail pages
# are just navigation chrome around a linked PDF, same as SEBI/India
# Code/CBIC — is PDF-only and never needs a selector. Keyed by source_name,
# not regulator, since rbi_notifications and rbi_master_directions share a
# regulator but not a content shape.
_CONTENT_SELECTOR_BY_SOURCE = {"rbi_notifications": "tr.tablecontent2"}


def extract_pending_documents(conn: sqlite3.Connection, ocr_work_dir: Path | None = None) -> int:
    """The extraction pass every smoke test this session did by hand:
    extract -> normalize -> store text -> extract citations -> persist
    normalization flags. Applied once per document that has a blob but no
    `texts` row yet, regardless of source. extract.router.extract() already
    runs OCR internally when a PDF needs it (OCRRequired never propagates
    out of it — see extract/router.py) and stores the OCR'd PDF under
    `ocr_work_dir` if given; a genuinely corrupt PDF or an unexpected
    content type is recorded via fetch_failures and does not stop the
    pass (I7)."""
    rows = conn.execute(
        """
        SELECT d.doc_id, d.regulator, d.source_name, d.html_sha256, d.pdf_sha256, d.source_url
        FROM documents d
        LEFT JOIN texts t ON t.doc_id = d.doc_id
        WHERE t.doc_id IS NULL AND (d.html_sha256 IS NOT NULL OR d.pdf_sha256 IS NOT NULL)
        """
    ).fetchall()

    extracted_count = 0
    for row in rows:
        selector = _CONTENT_SELECTOR_BY_SOURCE.get(row["source_name"])
        # A source with a registered HTML content_selector has its real
        # content in the HTML body (RBI notifications); everyone else's real
        # content is PDF-only, so prefer the PDF blob when both were fetched.
        if selector is not None and row["html_sha256"] is not None:
            sha256 = row["html_sha256"]
        else:
            sha256 = row["pdf_sha256"] or row["html_sha256"]

        blob = conn.execute(
            "SELECT stored_path, content_type FROM blobs WHERE sha256 = ?", (sha256,)
        ).fetchone()
        if blob is None:
            continue

        blob_path = Path(blob["stored_path"])
        content_type = blob["content_type"] or ""

        try:
            result = extract(blob_path, content_type, content_selector=selector, ocr_work_dir=ocr_work_dir)
        except PdfCorrupt as exc:
            record_failure(
                conn, source_url=row["source_url"], source_name=row["regulator"],
                reason_code=ReasonCode.PDF_CORRUPT, detail=str(exc), attempts=1,
            )
            continue
        except ContentTypeUnexpected as exc:
            record_failure(
                conn, source_url=row["source_url"], source_name=row["regulator"],
                reason_code=ReasonCode.CONTENT_TYPE_UNEXPECTED, detail=str(exc), attempts=1,
            )
            continue
        except ValueError as exc:
            # HTML content with no registered selector for this source — e.g.
            # a PDF-only source (SEBI, India Code, CBIC) fell back to its
            # HTML detail page because no PDF was found. Real 2026-08-05
            # finding: this used to be silently skipped with no record at
            # all, violating I7 ("failures are recorded, not swallowed").
            record_failure(
                conn, source_url=row["source_url"], source_name=row["regulator"],
                reason_code=ReasonCode.EXTRACTION_EMPTY, detail=str(exc), attempts=1,
            )
            continue

        if not result.text:
            record_failure(
                conn, source_url=row["source_url"], source_name=row["regulator"],
                reason_code=ReasonCode.EXTRACTION_EMPTY, detail="extractor returned no text", attempts=1,
            )
            continue

        norm_result = normalize(result.text)

        conn.execute(
            """
            INSERT INTO texts (doc_id, blob_sha256, text_source, extractor, extractor_version,
                                page_count, char_count, body, extracted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                row["doc_id"], sha256, result.text_source, result.extractor,
                result.extractor_version, result.page_count, len(norm_result.text), norm_result.text,
            ),
        )
        conn.commit()

        extract_and_store_citations(conn, row["doc_id"], norm_result.text)
        persist_normalization_flags(conn, row["doc_id"], norm_result.flags)
        extracted_count += 1

    return extracted_count
