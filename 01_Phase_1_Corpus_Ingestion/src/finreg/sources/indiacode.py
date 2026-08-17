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

REGULATOR = "indiacode"
BASE = "https://www.indiacode.nic.in"
CENTRAL_ACTS_HANDLE = "123456789/1362"
BROWSE_YEAR_URL = f"{BASE}/handle/{CENTRAL_ACTS_HANDLE}/browse?type=actyear&order=ASC&rpp=100&value={{year}}"
OAI_PROBE_URL = f"{BASE}/oai/request?verb=Identify"
REST_PROBE_URL = f"{BASE}/rest/test"

_HANDLE_FROM_HREF = re.compile(r"/handle/123456789/(\d+)")

# The 15 statutes doc 03 requires, with the enactment year encoded in their
# name (used to target a browse-by-year query) and a short-title substring to
# match against. NOTE (verified 2026-08-03, see 03-DATA-SOURCES.md): this
# mirror's `actyear` and `ministry` browse facets are sparse/incomplete for
# several of these — e.g. the RBI Act 1934 does not appear in the year=1934
# bucket at all (2 unrelated acts only) — so this list is a target list to
# search for, not a guarantee every entry will resolve via browse alone.
STATUTE_TARGETS: list[tuple[str, int]] = [
    ("Reserve Bank of India Act", 1934),
    ("Banking Regulation Act", 1949),
    ("Foreign Exchange Management Act", 1999),
    ("Payment and Settlement Systems Act", 2007),
    ("Securities and Exchange Board of India Act", 1992),
    ("Securities Contracts (Regulation) Act", 1956),
    ("Depositories Act", 1996),
    ("Companies Act", 2013),
    ("Insolvency and Bankruptcy Code", 2016),
    ("Prevention of Money-Laundering Act", 2002),
    ("Income-tax Act", 1961),
    ("Income-tax Act", 2025),
    ("Central Goods and Services Tax Act", 2017),
    ("Integrated Goods and Services Tax Act", 2017),
    ("Digital Personal Data Protection Act", 2023),
]


def doc_id(natural_id: int) -> str:
    return f"{REGULATOR}:indiacode_statutes:{natural_id}"


def extract_handle_id(href: str) -> int | None:
    match = _HANDLE_FROM_HREF.search(href)
    return int(match.group(1)) if match else None


def item_url(handle_id: int) -> str:
    return f"{BASE}/handle/123456789/{handle_id}"


@dataclass(frozen=True)
class BrowseEntry:
    handle_id: int
    short_title: str
    act_number: str | None
    enactment_date: date | None
    detail_url: str


def parse_rest_probe(status: int) -> bool:
    return status == 200


def parse_browse_year_page(html: bytes | str, base_url: str = BASE) -> list[BrowseEntry]:
    tree = HTMLParser(html)
    entries: list[BrowseEntry] = []

    for row in tree.css("table.table tr"):
        cells = row.css("td")
        if len(cells) != 4:
            continue
        link = cells[3].css_first("a")
        if link is None:
            continue
        href = link.attributes.get("href")
        if not href:
            continue
        handle_id = extract_handle_id(href)
        if handle_id is None:
            continue

        date_text = cells[0].text(deep=True).strip()
        enactment_date = _parse_indiacode_date(date_text)
        act_number = cells[1].text(deep=True).strip() or None
        short_title = cells[2].text(deep=True).strip()

        entries.append(
            BrowseEntry(
                handle_id=handle_id,
                short_title=short_title,
                act_number=act_number,
                enactment_date=enactment_date,
                detail_url=urljoin(base_url, item_url(handle_id)),
            )
        )
    return entries


def _parse_indiacode_date(text: str) -> date | None:
    text = text.strip()
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


@dataclass(frozen=True)
class StatuteFields:
    short_title: str | None
    act_number: str | None
    enactment_date: date | None
    ministry: str | None
    department: str | None
    pdf_url: str | None
    metadata_gaps: list[str]


def parse_item_page(html: bytes | str, base_url: str) -> StatuteFields:
    tree = HTMLParser(html)
    gaps: list[str] = []
    field_values: dict[str, str] = {}

    for row in tree.css("table.itemDisplayTable tr"):
        cells = row.css("td")
        if len(cells) != 2:
            continue
        label = cells[0].text(deep=True).strip().rstrip(":").strip()
        value = cells[1].text(deep=True).strip()
        if label and value:
            field_values[label] = value

    short_title = field_values.get("Short Title")
    if not short_title:
        gaps.append("short_title: no Short Title row in itemDisplayTable")

    act_number = field_values.get("Act Number")
    if not act_number:
        gaps.append("act_number: no Act Number row in itemDisplayTable")

    enactment_date = None
    raw_date = field_values.get("Enactment Date")
    if raw_date:
        enactment_date = _parse_indiacode_date(raw_date)
    if enactment_date is None:
        gaps.append("enactment_date: missing or unparseable Enactment Date row")

    ministry = field_values.get("Ministry")
    department = field_values.get("Department")

    pdf_url = None
    for anchor in tree.css("a"):
        href = anchor.attributes.get("href") or ""
        if "/bitstream/" in href and href.lower().endswith(".pdf"):
            filename = href.rsplit("/", 1)[-1]
            if filename.startswith("H"):
                continue
            pdf_url = urljoin(base_url, href)
            break
    if pdf_url is None:
        gaps.append("pdf_url: no non-Hindi bitstream PDF link found")

    return StatuteFields(
        short_title=short_title,
        act_number=act_number,
        enactment_date=enactment_date,
        ministry=ministry,
        department=department,
        pdf_url=pdf_url,
        metadata_gaps=gaps,
    )


class IndiaCodeStatutesSource:
    name = "indiacode_statutes"
    regulator = REGULATOR

    def verify(self, client: Client) -> VerifyReport:
        policy = HostPolicy(min_interval_seconds=2.0)
        checks: dict[str, bool] = {}

        oai_result = client.get(OAI_PROBE_URL, host_policy=policy)
        checks["oai_unavailable_as_expected"] = oai_result.status == 404

        rest_result = client.get(REST_PROBE_URL, host_policy=policy)
        checks["rest_unavailable_as_expected"] = rest_result.status == 404

        try:
            browse_result = client.get(BROWSE_YEAR_URL.format(year=1961), host_policy=policy)
            entries = parse_browse_year_page(browse_result.body)
            checks["handle_browse_fallback_works"] = len(entries) > 0
        except Exception as exc:  # noqa: BLE001
            return VerifyReport(
                source_name=self.name, ok=False, access_method="handle_traversal",
                detail=f"browse fallback failed: {exc}", checks=checks,
            )

        ok = checks.get("handle_browse_fallback_works", False)
        return VerifyReport(
            source_name=self.name,
            ok=ok,
            access_method="handle_traversal",
            detail=(
                "OAI-PMH and REST both unavailable (confirmed); handle-traversal via "
                "year-browse works" if ok else "handle-traversal fallback did not yield entries"
            ),
            checks=checks,
        )

    def discover(self, client: Client, window: DateWindow) -> Iterator[DocumentRef]:
        policy = HostPolicy(min_interval_seconds=2.0)
        for keyword, year in STATUTE_TARGETS:
            body = client.get(BROWSE_YEAR_URL.format(year=year), host_policy=policy).body
            for entry in parse_browse_year_page(body):
                if keyword.lower() in entry.short_title.lower():
                    yield DocumentRef(
                        source_url=entry.detail_url,
                        doc_meta=DocumentMeta(
                            doc_id=doc_id(entry.handle_id),
                            title=entry.short_title,
                            issue_date=entry.enactment_date,
                            detail_url=entry.detail_url,
                            pdf_url=None,
                        ),
                    )

    def parse_listing_meta(self, raw: bytes) -> list[DocumentMeta]:
        return [
            DocumentMeta(
                doc_id=doc_id(e.handle_id),
                title=e.short_title,
                issue_date=e.enactment_date,
                detail_url=e.detail_url,
                pdf_url=None,
            )
            for e in parse_browse_year_page(raw)
        ]


def crawl_statutes(client: Client, conn: sqlite3.Connection, policy: HostPolicy) -> list[str]:
    """Search each STATUTE_TARGETS entry via year-browse and ingest matches.
    Returns the list of target names that were NOT found (an honest, expected
    outcome on this mirror — see STATUTE_TARGETS's docstring — never silently
    dropped)."""
    not_found: list[str] = []
    for keyword, year in STATUTE_TARGETS:
        body = client.get(BROWSE_YEAR_URL.format(year=year), host_policy=policy).body
        entries = parse_browse_year_page(body)
        match = next((e for e in entries if keyword.lower() in e.short_title.lower()), None)
        if match is None:
            not_found.append(f"{keyword} ({year})")
            continue

        detail_result = client.get(match.detail_url, host_policy=policy)
        fields = parse_item_page(detail_result.body, match.detail_url)

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
                doc_id=doc_id(match.handle_id),
                regulator=REGULATOR,
                source_name="indiacode_statutes",
                doc_type="act",
                title=fields.short_title or match.short_title,
                source_url=match.detail_url,
                licence="statutory_s52_1_q",
                doc_number=fields.act_number,
                issue_date=fields.enactment_date or match.enactment_date,
                department=fields.department,
                pdf_url=fields.pdf_url,
                html_sha256=detail_result.sha256 or None,
                pdf_sha256=pdf_sha256,
                metadata_gaps=fields.metadata_gaps,
            ),
        )
    return not_found


register(IndiaCodeStatutesSource())
