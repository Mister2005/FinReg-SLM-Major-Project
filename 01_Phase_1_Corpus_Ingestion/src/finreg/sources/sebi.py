from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterator
from urllib.parse import parse_qs, urljoin, urlparse

from selectolax.parser import HTMLParser

from finreg.config import DateWindow
from finreg.http.client import Client, HostPolicy, RetriesExhausted
from finreg.sources.base import DocumentMeta, DocumentRef, VerifyReport
from finreg.sources.registry import register
from finreg.store.documents import NewDocument, upsert_document

REGULATOR = "sebi"
BASE = "https://www.sebi.gov.in/sebiweb/home/HomeAction.do"
ACTIVE_LISTING_URL = f"{BASE}?doListing=yes&sid=1&ssid=7&smid=0"
ARCHIVE_LISTING_URL = f"{BASE}?doListingCirArchive=yes&sid=1&ssid=7&smid=0"

# Pagination beyond page 1 is NOT a plain query-string GET (a bare `nextValue=N`
# on HomeAction.do is silently ignored and always returns page 1 — confirmed by
# repeated live testing 2026-08-03). The real mechanism, found in
# https://www.sebi.gov.in/js/entry.js's searchFormNewsList(): a stateful AJAX
# POST to this JSP, requiring the JSESSIONID cookie set by an initial GET of
# the listing page, a Referer header, and X-Requested-With: XMLHttpRequest.
# `doDirect` is the target page, 0-based. The response is two chunks joined by
# "#@#"; the first chunk is the row-table fragment we care about.
PAGINATION_AJAX_URL = "https://www.sebi.gov.in/sebiweb/ajax/home/getnewslistinfo.jsp"

_ID_FROM_URL = re.compile(r"_(\d+)\.html$")
_DATE_TEXT = re.compile(r"[A-Za-z]+ \d{1,2},\s*\d{4}")


def parse_sebi_date(text: str) -> date | None:
    match = _DATE_TEXT.search(text)
    if not match:
        return None
    candidate = re.sub(r"\s+", " ", match.group(0)).strip()
    try:
        return datetime.strptime(candidate, "%b %d, %Y").date()
    except ValueError:
        return None


def extract_id_from_url(url: str) -> int | None:
    match = _ID_FROM_URL.search(url)
    return int(match.group(1)) if match else None


def doc_id(source_name: str, natural_id: int) -> str:
    return f"{REGULATOR}:{source_name}:{natural_id}"


@dataclass(frozen=True)
class SectionSpec:
    source_name: str
    doc_type: str
    sid: int
    ssid: int
    smid: int
    licence: str


SECTIONS: dict[str, SectionSpec] = {
    "sebi_circulars": SectionSpec("sebi_circulars", "circular", 1, 7, 0, "gov_site_terms"),
    "sebi_master_circulars": SectionSpec("sebi_master_circulars", "master_circular", 1, 6, 0, "gov_site_terms"),
    "sebi_regulations": SectionSpec("sebi_regulations", "regulation", 1, 3, 0, "gov_site_terms"),
    "sebi_rules": SectionSpec("sebi_rules", "rule", 1, 2, 0, "gov_site_terms"),
    "sebi_guidelines": SectionSpec("sebi_guidelines", "guideline", 1, 5, 0, "gov_site_terms"),
    "sebi_gazette": SectionSpec("sebi_gazette", "notification", 1, 82, 0, "statutory_s52_1_q"),
}


def section_listing_url(section: SectionSpec, *, archive: bool = False,
                          from_date: str | None = None, to_date: str | None = None) -> str:
    """URL for page 1 only. Later pages require the stateful AJAX POST — see
    `fetch_listing_page` — there is no page-N query-string equivalent."""
    action = "doListingCirArchive" if archive else "doListing"
    url = f"{BASE}?{action}=yes&sid={section.sid}&ssid={section.ssid}&smid={section.smid}"
    if from_date:
        url += f"&fromDate={from_date}"
    if to_date:
        url += f"&toDate={to_date}"
    return url


def _pagination_post_data(section: SectionSpec, *, page_index_zero_based: int,
                            from_date: str = "", to_date: str = "") -> dict[str, str]:
    return {
        "nextValue": str(page_index_zero_based),
        "next": "n",
        "search": "",
        "fromDate": from_date,
        "toDate": to_date,
        "fromYear": "",
        "toYear": "",
        "deptId": "",
        "sid": str(section.sid),
        "ssid": str(section.ssid),
        "smid": str(section.smid),
        "ssidhidden": str(section.ssid),
        "intmid": "-1",
        "sText": "Legal",
        "ssText": "",
        "smText": "",
        "doDirect": str(page_index_zero_based),
    }


def fetch_listing_page(
    client: Client,
    policy: HostPolicy,
    section: SectionSpec,
    *,
    page: int,
    archive: bool = False,
    from_date: str = "",
    to_date: str = "",
    referer_url: str | None = None,
) -> bytes:
    """Fetch listing page N (1-based). Page 1 is a plain GET. Page 2+ requires
    the caller to have already GET'd page 1 on this same `client` (for the
    session cookie) and goes through the AJAX POST endpoint instead."""
    if page == 1:
        url = section_listing_url(section, archive=archive, from_date=from_date, to_date=to_date)
        result = client.get(url, host_policy=policy)
        return result.body

    referer = referer_url or section_listing_url(section, archive=archive)
    data = _pagination_post_data(section, page_index_zero_based=page - 1, from_date=from_date, to_date=to_date)
    result = client.post(
        PAGINATION_AJAX_URL,
        data=data,
        host_policy=policy,
        extra_headers={"X-Requested-With": "XMLHttpRequest", "Referer": referer},
    )
    return result.body.split(b"#@#")[0]


def parse_listing_page(html: bytes | str, base_url: str = ACTIVE_LISTING_URL) -> list[DocumentMeta]:
    tree = HTMLParser(html)
    results: list[DocumentMeta] = []

    for row in tree.css("tbody tr"):
        cells = row.css("td")
        if len(cells) < 2:
            continue
        date_text = cells[0].text(deep=True).strip()
        issue_date = parse_sebi_date(date_text)

        link = cells[1].css_first("a")
        if link is None:
            continue
        href = link.attributes.get("href")
        if not href:
            continue
        detail_url = urljoin(base_url, href)
        natural_id = extract_id_from_url(detail_url)
        if natural_id is None:
            continue
        title = link.text(deep=True).strip()

        results.append(
            DocumentMeta(
                doc_id=doc_id("sebi_circulars", natural_id),
                title=title,
                issue_date=issue_date,
                detail_url=detail_url,
                pdf_url=None,
            )
        )
    return results


def parse_record_count(html: bytes | str) -> int | None:
    tree = HTMLParser(html)
    for p in tree.css("p"):
        text = p.text(deep=True)
        match = re.search(r"of\s+(\d+)\s+records", text)
        if match:
            return int(match.group(1))
    return None


@dataclass(frozen=True)
class SebiDetailFields:
    title: str | None
    issue_date: date | None
    circular_number: str | None
    pdf_url: str | None
    metadata_gaps: list[str]


def _pdf_url_from_iframe(tree: HTMLParser, base_url: str) -> str | None:
    iframe = tree.css_first("iframe")
    if iframe is None:
        return None
    src = iframe.attributes.get("src")
    if not src:
        return None
    parsed = urlparse(urljoin(base_url, src))
    query = parse_qs(parsed.query)
    file_values = query.get("file")
    if file_values:
        return urljoin(base_url, file_values[0])
    return None


def parse_detail_page(html: bytes | str, base_url: str) -> SebiDetailFields:
    tree = HTMLParser(html)
    gaps: list[str] = []

    h1 = tree.css_first("h1")
    title = h1.text(deep=True).strip() if h1 is not None else None
    if not title:
        title = None
        gaps.append("title: no <h1> found on detail page")

    date_node = tree.css_first(".date_value h5")
    issue_date = parse_sebi_date(date_node.text(deep=True)) if date_node is not None else None
    if issue_date is None:
        gaps.append("issue_date: no parseable date in .date_value")

    circular_number = None
    id_area = tree.css_first(".id_area")
    if id_area is not None:
        spans = id_area.css("span")
        if len(spans) >= 2:
            candidate = spans[1].text(deep=True).strip()
            if candidate:
                circular_number = candidate
    if circular_number is None:
        gaps.append("circular_number: no .id_area value span found")

    pdf_url = _pdf_url_from_iframe(tree, base_url)
    if pdf_url is None:
        gaps.append("pdf_url: no iframe with a file= query parameter found")

    return SebiDetailFields(
        title=title,
        issue_date=issue_date,
        circular_number=circular_number,
        pdf_url=pdf_url,
        metadata_gaps=gaps,
    )


class SEBICircularsSource:
    name = "sebi_circulars"
    regulator = REGULATOR

    def verify(self, client: Client) -> VerifyReport:
        policy = HostPolicy(min_interval_seconds=2.0)
        checks: dict[str, bool] = {}
        section = SECTIONS["sebi_circulars"]

        try:
            page1_body = fetch_listing_page(client, policy, section, page=1)
            count = parse_record_count(page1_body)
            checks["record_count_parses"] = count is not None and count > 0
        except Exception as exc:  # noqa: BLE001
            return VerifyReport(
                source_name=self.name, ok=False, access_method="session_ajax_post",
                detail=f"listing fetch/parse failed: {exc}", checks=checks,
            )

        try:
            page2_body = fetch_listing_page(client, policy, section, page=2)
            docs1 = parse_listing_page(page1_body)
            docs2 = parse_listing_page(page2_body)
            ids1 = {d.doc_id for d in docs1}
            ids2 = {d.doc_id for d in docs2}
            checks["page2_disjoint_from_page1"] = len(ids2) > 0 and ids1.isdisjoint(ids2)
        except Exception as exc:  # noqa: BLE001
            return VerifyReport(
                source_name=self.name, ok=False, access_method="session_ajax_post",
                detail=f"pagination check failed: {exc}", checks=checks,
            )

        try:
            known = docs1[0]
            detail = client.get(known.detail_url, host_policy=policy)
            fields = parse_detail_page(detail.body, known.detail_url)
            checks["known_detail_resolves"] = fields.title is not None
        except Exception as exc:  # noqa: BLE001
            return VerifyReport(
                source_name=self.name, ok=False, access_method="session_ajax_post",
                detail=f"detail fetch/parse failed: {exc}", checks=checks,
            )

        ok = all(checks.values())
        return VerifyReport(
            source_name=self.name,
            ok=ok,
            access_method="session_ajax_post",
            detail="verified record count, page2 disjoint from page1, and one detail resolution" if ok else "one or more checks failed",
            checks=checks,
        )

    def discover(self, client: Client, window: DateWindow) -> Iterator[DocumentRef]:
        policy = HostPolicy(min_interval_seconds=2.0)
        section = SECTIONS["sebi_circulars"]
        body = fetch_listing_page(client, policy, section, page=1)
        for meta in parse_listing_page(body):
            yield DocumentRef(source_url=meta.detail_url, doc_meta=meta)

    def parse_listing_meta(self, raw: bytes) -> list[DocumentMeta]:
        return parse_listing_page(raw)


def crawl_section_page(
    client: Client,
    conn: sqlite3.Connection,
    policy: HostPolicy,
    section: SectionSpec,
    *,
    archive: bool,
    page: int = 1,
) -> list[DocumentMeta]:
    listing_url = section_listing_url(section, archive=archive)
    body = fetch_listing_page(client, policy, section, page=page, archive=archive)
    metas = parse_listing_page(body, listing_url)

    # Archive membership is genuine rank-1 evidence of supersession (matches
    # 06-TEMPORAL-VALIDITY-SPEC.md's evidence table). Active-listing
    # membership is NOT positive evidence of in_force, despite what an
    # earlier version of that doc assumed: verified 2026-08-04 by crawling
    # the Active endpoint to completion — it paginates through SEBI's
    # entire circular history back to 1991, not a curated "currently
    # active" set, so presence in it carries no temporal signal. Leave
    # Active-listing documents at their default 'unknown' status; only set
    # status for genuine Archive membership.
    status = "superseded" if archive else None

    for meta in metas:
        detail_result = client.get(meta.detail_url, host_policy=policy)
        fields = parse_detail_page(detail_result.body, meta.detail_url)

        pdf_sha256 = None
        if fields.pdf_url:
            try:
                pdf_result = client.get(fields.pdf_url, host_policy=policy)
                if pdf_result.status < 400:
                    pdf_sha256 = pdf_result.sha256 or None
            except RetriesExhausted:
                pass  # already recorded in fetch_failures by the client; keep pdf_sha256 NULL

        upsert_document(
            conn,
            NewDocument(
                doc_id=meta.doc_id,
                regulator=REGULATOR,
                source_name=section.source_name,
                doc_type=section.doc_type,
                title=fields.title or meta.title,
                source_url=meta.detail_url,
                licence=section.licence,
                doc_number=fields.circular_number,
                issue_date=fields.issue_date or meta.issue_date,
                pdf_url=fields.pdf_url,
                html_sha256=detail_result.sha256 or None,
                pdf_sha256=pdf_sha256,
                metadata_gaps=fields.metadata_gaps,
            ),
        )
        if status is not None:
            conn.execute(
                "UPDATE documents SET status = ? WHERE doc_id = ?",
                (status, meta.doc_id),
            )
        conn.commit()

    return metas


def crawl_section_all_pages(
    client: Client,
    conn: sqlite3.Connection,
    policy: HostPolicy,
    section: SectionSpec,
    *,
    archive: bool = False,
    max_pages: int | None = None,
) -> int:
    first_body = fetch_listing_page(client, policy, section, page=1, archive=archive)
    total_records = parse_record_count(first_body) or 0
    total_pages = (total_records + 24) // 25 if total_records else 1
    if max_pages is not None:
        total_pages = min(total_pages, max_pages)

    total_ingested = 0
    for page in range(1, total_pages + 1):
        metas = crawl_section_page(client, conn, policy, section, archive=archive, page=page)
        total_ingested += len(metas)
    return total_ingested


register(SEBICircularsSource())
