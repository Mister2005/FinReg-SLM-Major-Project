from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterator
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from finreg.config import DateWindow
from finreg.http.client import Client, HostPolicy, RetriesExhausted
from finreg.sources.base import DocumentMeta, DocumentRef, VerifyReport
from finreg.sources.registry import register
from finreg.store.documents import NewDocument, upsert_document

REGULATOR = "cbic"

# The modern SPA (taxinformation.cbic.gov.in) fails TLS certificate
# verification for a standards-compliant client — verified 2026-08-03,
# httpx.ConnectError: [SSL: CERTIFICATE_VERIFY_FAILED]. This is a
# certificate-chain problem on the site's end, not a bot-defense block, and
# it is NOT something this project bypasses (disabling TLS verification is a
# categorically different, much more dangerous workaround than a UA header
# and is never done silently). Per doc 03's own contingency, this is treated
# as "no API reachable" and the module falls back to the legacy static
# portal, which serves correctly over TLS with the honest UA.
MODERN_SPA_URL = "https://taxinformation.cbic.gov.in/"
LEGACY_CIRCULARS_URL = "https://cbic-gst.gov.in/circulars-cgst.html"

_DATE_RE = re.compile(r"\d{2}-\d{2}-\d{4}")


def parse_cbic_date(text: str) -> date | None:
    match = _DATE_RE.search(text.strip())
    if not match:
        return None
    try:
        return datetime.strptime(match.group(0), "%d-%m-%Y").date()
    except ValueError:
        return None


def doc_id(natural_id: str) -> str:
    return f"{REGULATOR}:cbic_circulars:{natural_id}"


@dataclass(frozen=True)
class CBICEntry:
    circular_no: str
    pdf_url: str | None
    issue_date: date | None
    subject: str


def parse_legacy_circulars_page(html: bytes | str, base_url: str = LEGACY_CIRCULARS_URL) -> list[CBICEntry]:
    tree = HTMLParser(html)
    entries: list[CBICEntry] = []

    for row in tree.css("table.table tbody tr"):
        cells = row.css("td")
        if len(cells) < 5:
            continue
        circular_no = cells[0].text(deep=True).strip()
        if not circular_no:
            continue

        english_link = cells[1].css_first("a")
        pdf_url = urljoin(base_url, english_link.attributes["href"]) if english_link and english_link.attributes.get("href") else None

        issue_date = parse_cbic_date(cells[3].text(deep=True))
        subject = cells[4].text(deep=True).strip()

        entries.append(
            CBICEntry(circular_no=circular_no, pdf_url=pdf_url, issue_date=issue_date, subject=subject)
        )
    return entries


class CBICCircularsSource:
    name = "cbic_circulars"
    regulator = REGULATOR

    def verify(self, client: Client) -> VerifyReport:
        policy = HostPolicy(min_interval_seconds=2.0)
        checks: dict[str, bool] = {}
        access_method = "legacy_static"

        try:
            spa_result = client.get(MODERN_SPA_URL, host_policy=policy)
            checks["modern_spa_reachable"] = spa_result.status == 200
        except Exception:  # noqa: BLE001
            checks["modern_spa_reachable"] = False

        try:
            legacy_result = client.get(LEGACY_CIRCULARS_URL, host_policy=policy)
            entries = parse_legacy_circulars_page(legacy_result.body)
            checks["legacy_fallback_yields_entries"] = len(entries) > 0
        except Exception as exc:  # noqa: BLE001
            return VerifyReport(
                source_name=self.name, ok=False, access_method="none",
                detail=f"both modern SPA and legacy fallback failed: {exc}", checks=checks,
            )

        ok = checks["legacy_fallback_yields_entries"]
        detail = (
            "Modern SPA unreachable (TLS cert failure) — using legacy static fallback, which works"
            if not checks["modern_spa_reachable"]
            else "Modern SPA reachable but this module targets the legacy fallback pending API integration"
        )
        return VerifyReport(source_name=self.name, ok=ok, access_method=access_method, detail=detail, checks=checks)

    def discover(self, client: Client, window: DateWindow) -> Iterator[DocumentRef]:
        policy = HostPolicy(min_interval_seconds=2.0)
        result = client.get(LEGACY_CIRCULARS_URL, host_policy=policy)
        for entry in parse_legacy_circulars_page(result.body):
            yield DocumentRef(
                source_url=entry.pdf_url or LEGACY_CIRCULARS_URL,
                doc_meta=DocumentMeta(
                    doc_id=doc_id(entry.circular_no),
                    title=entry.subject,
                    issue_date=entry.issue_date,
                    detail_url=LEGACY_CIRCULARS_URL,
                    pdf_url=entry.pdf_url,
                ),
            )

    def parse_listing_meta(self, raw: bytes) -> list[DocumentMeta]:
        return [
            DocumentMeta(
                doc_id=doc_id(e.circular_no),
                title=e.subject,
                issue_date=e.issue_date,
                detail_url=LEGACY_CIRCULARS_URL,
                pdf_url=e.pdf_url,
            )
            for e in parse_legacy_circulars_page(raw)
        ]


def crawl_legacy_circulars(client: Client, conn: sqlite3.Connection, policy: HostPolicy) -> int:
    result = client.get(LEGACY_CIRCULARS_URL, host_policy=policy)
    entries = parse_legacy_circulars_page(result.body)

    for entry in entries:
        gaps: list[str] = []
        if entry.pdf_url is None:
            gaps.append("pdf_url: no English PDF link present for this row")
        if entry.issue_date is None:
            gaps.append("issue_date: unparseable date in Date of issue column")

        doc_type = "order" if entry.circular_no.lower().startswith("order") else "circular"

        pdf_sha256 = None
        if entry.pdf_url:
            try:
                pdf_result = client.get(entry.pdf_url, host_policy=policy)
                if pdf_result.status < 400:
                    pdf_sha256 = pdf_result.sha256 or None
            except RetriesExhausted:
                pass  # already recorded in fetch_failures by the client; keep pdf_sha256 NULL

        upsert_document(
            conn,
            NewDocument(
                doc_id=doc_id(entry.circular_no),
                regulator=REGULATOR,
                source_name="cbic_circulars",
                doc_type=doc_type,
                title=entry.subject,
                source_url=LEGACY_CIRCULARS_URL,
                licence="gov_site_terms",
                doc_number=entry.circular_no,
                issue_date=entry.issue_date,
                pdf_url=entry.pdf_url,
                pdf_sha256=pdf_sha256,
                metadata_gaps=gaps,
            ),
        )
    return len(entries)


register(CBICCircularsSource())
