from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterator
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from finreg.config import Config, DateWindow
from finreg.http.client import Client, HostPolicy, RetriesExhausted
from finreg.normalize.doc_number import (
    match_rbi_departmental_reference,
    match_rbi_master_direction_series,
    match_rbi_master_reference,
)
from finreg.sources.base import DocumentMeta, DocumentRef, Source, VerifyReport
from finreg.sources.registry import register
from finreg.store.documents import NewDocument, upsert_document
from finreg.store.withdrawals import WithdrawnEntry, insert_withdrawn_entry

REGULATOR = "rbi"
LISTING_URL = "https://www.rbi.org.in/Scripts/NotificationUser.aspx"
DETAIL_URL = "https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id={id}&Mode=0"
WITHDRAWN_URL = "https://www.rbi.org.in/Scripts/NotificationUserWithdrawnCircular.aspx"
MASTER_DIRECTIONS_URL = "https://www.rbi.org.in/Scripts/BS_ViewMasterDirections.aspx"
MASTER_CIRCULARS_URL = "https://www.rbi.org.in/Scripts/BS_ViewMasterCirculardetails.aspx"
AMENDMENT_DIRECTIONS_URL = "https://www.rbi.org.in/Scripts/Fs_AmendmentDirections.aspx"

RBI_CONTENT_SELECTOR = "tr.tablecontent2"

_ID_IN_HREF = re.compile(r"[Ii]d=(\d+)")
_DATE_TEXT = re.compile(r"[A-Za-z]+ \d{1,2},\s*\d{4}")
_DATE_FORMATS = ("%b %d, %Y", "%B %d, %Y")


def parse_rbi_date(text: str) -> date | None:
    match = _DATE_TEXT.search(text)
    if not match:
        return None
    candidate = re.sub(r"\s+", " ", match.group(0)).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(candidate, fmt).date()
        except ValueError:
            continue
    return None


def extract_id_from_href(href: str) -> int | None:
    match = _ID_IN_HREF.search(href)
    return int(match.group(1)) if match else None


def doc_id(source_name: str, natural_id: int) -> str:
    return f"{REGULATOR}:{source_name}:{natural_id}"


def parse_listing_page(html: bytes | str, base_url: str = LISTING_URL) -> list[DocumentMeta]:
    tree = HTMLParser(html)
    results: list[DocumentMeta] = []
    current_date: date | None = None

    for tr in tree.css("tr"):
        tds = tr.css("td")
        if len(tds) == 1 and "tableheader" in (tds[0].attributes.get("class") or ""):
            bold = tds[0].css_first("b")
            if bold is not None:
                current_date = parse_rbi_date(bold.text())
            continue

        link = tr.css_first("a.link2")
        if link is None:
            continue
        href = link.attributes.get("href")
        if not href:
            continue
        natural_id = extract_id_from_href(href)
        if natural_id is None:
            continue
        title = link.text(deep=True).strip()

        pdf_anchor = None
        for anchor in tr.css("a"):
            anchor_href = anchor.attributes.get("href") or ""
            if anchor_href.lower().endswith(".pdf"):
                pdf_anchor = anchor
                break
        pdf_url = urljoin(base_url, pdf_anchor.attributes["href"]) if pdf_anchor else None

        results.append(
            DocumentMeta(
                doc_id=doc_id("rbi_notifications", natural_id),
                title=title,
                issue_date=current_date,
                detail_url=urljoin(base_url, href),
                pdf_url=pdf_url,
            )
        )
    return results


@dataclass(frozen=True)
class DetailFields:
    title: str | None
    issue_date: date | None
    master_reference: str | None
    departmental_reference: str | None
    master_direction_series: str | None
    addressee: str | None
    pdf_url: str | None
    metadata_gaps: list[str]


def parse_detail_page(html: bytes | str, base_url: str) -> DetailFields:
    tree = HTMLParser(html)
    gaps: list[str] = []

    header_tds = tree.css("td.tableheader")
    title: str | None = None
    for td in header_tds:
        bold = td.css_first("b")
        if bold is not None and (td.attributes.get("align") == "center"):
            title = bold.text(deep=True).strip()
            break
    if title is None:
        gaps.append("title: no centered tableheader <b> found on detail page")

    pdf_url: str | None = None
    for td in header_tds:
        anchor = td.css_first("a")
        if anchor is not None:
            href = anchor.attributes.get("href")
            if href and href.lower().endswith(".pdf"):
                pdf_url = urljoin(base_url, href)
                break
    if pdf_url is None:
        gaps.append("pdf_url: no PDF anchor found in tableheader cells")

    body_cell = tree.css_first("tr.tablecontent2 td")
    paragraphs: list[str] = []
    if body_cell is not None:
        for p in body_cell.css("p"):
            text = p.text(deep=True, separator="\n").strip()
            if text:
                paragraphs.append(text)

    if not paragraphs:
        gaps.append("body: tablecontent2 cell has no <p> paragraphs")

    master_reference: str | None = None
    departmental_reference: str | None = None
    master_direction_series: str | None = None
    issue_date: date | None = None
    addressee: str | None = None

    if paragraphs:
        ref_block = paragraphs[0]
        master_reference = match_rbi_master_reference(ref_block)
        departmental_reference = match_rbi_departmental_reference(ref_block)
        # Optional: only Master Directions carry this second, self-identifying
        # series number (the one other documents cite them by) — absence is
        # normal for notifications/circulars, not a metadata gap.
        master_direction_series = match_rbi_master_direction_series(ref_block)
        if master_reference is None:
            gaps.append("master_reference: no RBI/<FY>/<seq> pattern found in first paragraph")
        if departmental_reference is None:
            gaps.append("departmental_reference: no departmental reference pattern found")

        for para in paragraphs[1:4]:
            candidate = parse_rbi_date(para)
            if candidate is not None:
                issue_date = candidate
                break
        if issue_date is None:
            gaps.append("issue_date: no parseable date found in early body paragraphs")

        salutation_idx = None
        for idx, para in enumerate(paragraphs):
            lowered = para.lower()
            if "dear sir" in lowered or "madam" in lowered:
                salutation_idx = idx
                break
        if salutation_idx is not None and salutation_idx > 0:
            candidate_addressee = paragraphs[salutation_idx - 1]
            if parse_rbi_date(candidate_addressee) is None and candidate_addressee != ref_block:
                addressee = candidate_addressee
        if addressee is None:
            gaps.append("addressee: no addressee paragraph found before salutation")

    return DetailFields(
        title=title,
        issue_date=issue_date,
        master_reference=master_reference,
        departmental_reference=departmental_reference,
        master_direction_series=master_direction_series,
        addressee=addressee,
        pdf_url=pdf_url,
        metadata_gaps=gaps,
    )


def parse_withdrawn_listing(html: bytes | str) -> list[WithdrawnEntry]:
    tree = HTMLParser(html)
    entries: list[WithdrawnEntry] = []
    for tr in tree.css("tr"):
        tds = tr.css("td")
        if len(tds) != 4:
            continue
        link = tds[1].css_first("a")
        if link is None:
            continue
        href = link.attributes.get("href") or ""
        natural_id = extract_id_from_href(href)
        raw_circular_no = link.text(deep=True).strip()
        raw_title = tds[2].text(deep=True).strip()
        raw_date = tds[3].text(deep=True).strip()
        parsed_date = parse_rbi_date(raw_date) if raw_date else None
        matched = doc_id("rbi_notifications", natural_id) if natural_id is not None else None
        entries.append(
            WithdrawnEntry(
                source_name="rbi_notifications",
                source_url=WITHDRAWN_URL,
                raw_circular_no=raw_circular_no,
                raw_title=raw_title,
                raw_date=raw_date or None,
                parsed_date=parsed_date,
                matched_doc_id=matched,
            )
        )
    return entries


def _bisect_boundary(id_max: int, id_min: int, date_of: "callable[[int], date | None]", window_start: date) -> int:
    lo, hi = id_min, id_max
    while lo < hi:
        mid = (lo + hi) // 2
        found_date = date_of(mid)
        step = 0
        probe = mid
        while found_date is None and step < 5:
            probe -= 1
            if probe < lo:
                break
            found_date = date_of(probe)
            step += 1
        if found_date is None or found_date < window_start:
            lo = mid + 1
        else:
            hi = mid
    return lo


class RBINotificationsSource:
    name = "rbi_notifications"
    regulator = REGULATOR

    def verify(self, client: Client) -> VerifyReport:
        policy = HostPolicy(min_interval_seconds=2.0)
        checks: dict[str, bool] = {}
        try:
            listing_result = client.get(LISTING_URL, host_policy=policy)
            docs = parse_listing_page(listing_result.body, LISTING_URL)
            checks["listing_returns_documents"] = len(docs) > 0
        except Exception as exc:  # noqa: BLE001
            return VerifyReport(
                source_name=self.name,
                ok=False,
                access_method="id_enumeration",
                detail=f"listing fetch/parse failed: {exc}",
                checks=checks,
            )

        try:
            known_id = docs[0].doc_id.rsplit(":", 1)[-1]
            detail_result = client.get(
                DETAIL_URL.format(id=known_id), host_policy=policy
            )
            fields = parse_detail_page(detail_result.body, DETAIL_URL.format(id=known_id))
            checks["known_id_resolves"] = fields.title is not None or fields.master_reference is not None
        except Exception as exc:  # noqa: BLE001
            return VerifyReport(
                source_name=self.name,
                ok=False,
                access_method="id_enumeration",
                detail=f"detail fetch/parse failed: {exc}",
                checks=checks,
            )

        ok = all(checks.values())
        return VerifyReport(
            source_name=self.name,
            ok=ok,
            access_method="id_enumeration",
            detail="verified listing parse and one detail-page resolution" if ok else "one or more checks failed",
            checks=checks,
        )

    def discover(self, client: Client, window: DateWindow) -> Iterator[DocumentRef]:
        policy = HostPolicy(min_interval_seconds=2.0)
        listing_result = client.get(LISTING_URL, host_policy=policy)
        for meta in parse_listing_page(listing_result.body, LISTING_URL):
            yield DocumentRef(source_url=meta.detail_url, doc_meta=meta)

    def parse_listing_meta(self, raw: bytes) -> list[DocumentMeta]:
        return parse_listing_page(raw, LISTING_URL)


def find_id_max(client: Client, policy: HostPolicy) -> int:
    listing_result = client.get(LISTING_URL, host_policy=policy)
    docs = parse_listing_page(listing_result.body, LISTING_URL)
    ids = [int(meta.doc_id.rsplit(":", 1)[-1]) for meta in docs]
    if not ids:
        raise ValueError("listing page yielded no documents; cannot determine id_max")
    return max(ids)


def bisect_window_boundary(
    client: Client, policy: HostPolicy, id_min: int, id_max: int, window_start: date
) -> int:
    def date_of(candidate_id: int) -> date | None:
        result = client.get(DETAIL_URL.format(id=candidate_id), host_policy=policy)
        fields = parse_detail_page(result.body, DETAIL_URL.format(id=candidate_id))
        return fields.issue_date

    return _bisect_boundary(id_max, id_min, date_of, window_start)


def _load_cursor(conn: sqlite3.Connection, source_name: str) -> dict:
    row = conn.execute(
        "SELECT cursor_json FROM source_state WHERE source_name = ?", (source_name,)
    ).fetchone()
    return json.loads(row["cursor_json"]) if row else {}


def _save_cursor(conn: sqlite3.Connection, source_name: str, cursor: dict) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO source_state (source_name, cursor_json, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(source_name) DO UPDATE SET cursor_json = excluded.cursor_json, updated_at = excluded.updated_at
        """,
        (source_name, json.dumps(cursor), now),
    )
    conn.commit()


def enumerate_ids(
    client: Client,
    conn: sqlite3.Connection,
    policy: HostPolicy,
    id_min: int,
    id_max: int,
    source_name: str = "rbi_notifications",
) -> Iterator[DetailFields]:
    cursor = _load_cursor(conn, source_name)
    start = max(id_min, cursor.get("last_completed_id", id_min - 1) + 1)

    for current_id in range(start, id_max + 1):
        url = DETAIL_URL.format(id=current_id)
        try:
            result = client.get(url, host_policy=policy)
        except Exception:  # noqa: BLE001
            _save_cursor(conn, source_name, {"last_completed_id": current_id})
            continue

        if result.status >= 400:
            # The HTTP client already records fetch_failures for 4xx/5xx responses.
            _save_cursor(conn, source_name, {"last_completed_id": current_id})
            continue

        fields = parse_detail_page(result.body, url)
        this_doc_id = doc_id(source_name, current_id)
        upsert_document(
            conn,
            NewDocument(
                doc_id=this_doc_id,
                regulator=REGULATOR,
                source_name=source_name,
                doc_type="notification",
                title=fields.title or "",
                source_url=url,
                licence="godl_india",
                doc_number=fields.master_reference,
                departmental_ref=fields.departmental_reference,
                alias_doc_number=fields.master_direction_series,
                issue_date=fields.issue_date,
                addressee=fields.addressee,
                pdf_url=fields.pdf_url,
                html_sha256=result.sha256 or None,
                metadata_gaps=fields.metadata_gaps,
            ),
        )
        _save_cursor(conn, source_name, {"last_completed_id": current_id})
        yield fields


def ingest_withdrawn_circulars(client: Client, conn: sqlite3.Connection, policy: HostPolicy) -> int:
    result = client.get(WITHDRAWN_URL, host_policy=policy)
    entries = parse_withdrawn_listing(result.body)
    for entry in entries:
        insert_withdrawn_entry(conn, entry)
    return len(entries)


@dataclass(frozen=True)
class SupplementalListing:
    doc_type: str
    source_name: str
    listing_url: str


SUPPLEMENTAL_LISTINGS = (
    SupplementalListing("master_direction", "rbi_master_directions", MASTER_DIRECTIONS_URL),
    SupplementalListing("master_circular", "rbi_master_circulars", MASTER_CIRCULARS_URL),
    SupplementalListing("amendment_direction", "rbi_amendment_directions", AMENDMENT_DIRECTIONS_URL),
)


def parse_supplemental_listing(html: bytes | str, base_url: str, source_name: str) -> list[DocumentMeta]:
    tree = HTMLParser(html)
    results: list[DocumentMeta] = []
    current_date: date | None = None

    for tr in tree.css("tr"):
        tds = tr.css("td")
        header_td = None
        for td in tds:
            if "tableheader" in (td.attributes.get("class") or ""):
                header_td = td
                break
        if header_td is not None and len(tds) <= 1:
            bold = header_td.css_first("b")
            if bold is not None:
                parsed = parse_rbi_date(bold.text())
                if parsed is not None:
                    current_date = parsed
            continue

        link = None
        for anchor in tr.css("a"):
            href = anchor.attributes.get("href") or ""
            if href.lower().endswith(".pdf"):
                continue
            if "id=" in href.lower() or "Id=" in href:
                link = anchor
                break
        if link is None:
            continue
        href = link.attributes["href"]
        natural_id = extract_id_from_href(href)
        if natural_id is None:
            continue
        title = link.text(deep=True).strip()

        pdf_anchor = None
        for anchor in tr.css("a"):
            anchor_href = anchor.attributes.get("href") or ""
            if anchor_href.lower().endswith(".pdf"):
                pdf_anchor = anchor
                break
        pdf_url = urljoin(base_url, pdf_anchor.attributes["href"]) if pdf_anchor else None

        results.append(
            DocumentMeta(
                doc_id=doc_id(source_name, natural_id),
                title=title,
                issue_date=current_date,
                detail_url=urljoin(base_url, href),
                pdf_url=pdf_url,
            )
        )
    return results


def ingest_supplemental_listing(
    client: Client,
    conn: sqlite3.Connection,
    policy: HostPolicy,
    listing: SupplementalListing,
    limit: int | None = None,
) -> int:
    listing_result = client.get(listing.listing_url, host_policy=policy)
    metas = parse_supplemental_listing(listing_result.body, listing.listing_url, listing.source_name)
    if limit is not None:
        metas = metas[:limit]

    count = 0
    for meta in metas:
        detail_result = client.get(meta.detail_url, host_policy=policy)
        fields = parse_detail_page(detail_result.body, meta.detail_url)

        pdf_url = fields.pdf_url or meta.pdf_url
        pdf_sha256 = None
        if pdf_url:
            try:
                pdf_result = client.get(pdf_url, host_policy=policy)
                if pdf_result.status < 400:
                    pdf_sha256 = pdf_result.sha256 or None
            except RetriesExhausted:
                pass  # already recorded in fetch_failures by the client; keep pdf_sha256 NULL

        upsert_document(
            conn,
            NewDocument(
                doc_id=meta.doc_id,
                regulator=REGULATOR,
                source_name=listing.source_name,
                doc_type=listing.doc_type,
                title=fields.title or meta.title,
                source_url=meta.detail_url,
                licence="godl_india",
                doc_number=fields.master_reference,
                departmental_ref=fields.departmental_reference,
                alias_doc_number=fields.master_direction_series,
                issue_date=fields.issue_date or meta.issue_date,
                addressee=fields.addressee,
                pdf_url=pdf_url,
                html_sha256=detail_result.sha256 or None,
                pdf_sha256=pdf_sha256,
                metadata_gaps=fields.metadata_gaps,
            ),
        )
        count += 1
    return count


class RBIMasterDirectionsSource:
    name = "rbi_master_directions"
    regulator = REGULATOR

    def verify(self, client: Client) -> VerifyReport:
        policy = HostPolicy(min_interval_seconds=2.0)
        checks: dict[str, bool] = {}
        try:
            listing_result = client.get(MASTER_DIRECTIONS_URL, host_policy=policy)
            metas = parse_supplemental_listing(listing_result.body, MASTER_DIRECTIONS_URL, self.name)
            checks["listing_returns_documents"] = len(metas) > 0
        except Exception as exc:  # noqa: BLE001
            return VerifyReport(
                source_name=self.name,
                ok=False,
                access_method="supplemental_listing",
                detail=f"listing fetch/parse failed: {exc}",
                checks=checks,
            )

        try:
            detail_result = client.get(metas[0].detail_url, host_policy=policy)
            fields = parse_detail_page(detail_result.body, metas[0].detail_url)
            checks["known_entry_resolves"] = fields.title is not None or fields.master_reference is not None
        except Exception as exc:  # noqa: BLE001
            return VerifyReport(
                source_name=self.name,
                ok=False,
                access_method="supplemental_listing",
                detail=f"detail fetch/parse failed: {exc}",
                checks=checks,
            )

        ok = all(checks.values())
        return VerifyReport(
            source_name=self.name,
            ok=ok,
            access_method="supplemental_listing",
            detail="verified listing parse and one detail-page resolution" if ok else "one or more checks failed",
            checks=checks,
        )

    def discover(self, client: Client, window: DateWindow) -> Iterator[DocumentRef]:
        policy = HostPolicy(min_interval_seconds=2.0)
        listing_result = client.get(MASTER_DIRECTIONS_URL, host_policy=policy)
        for meta in parse_supplemental_listing(listing_result.body, MASTER_DIRECTIONS_URL, self.name):
            yield DocumentRef(source_url=meta.detail_url, doc_meta=meta)

    def parse_listing_meta(self, raw: bytes) -> list[DocumentMeta]:
        return parse_supplemental_listing(raw, MASTER_DIRECTIONS_URL, self.name)


register(RBINotificationsSource())
register(RBIMasterDirectionsSource())
