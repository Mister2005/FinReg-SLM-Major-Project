from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterator, Protocol

from finreg.config import DateWindow
from finreg.http.client import Client


@dataclass(frozen=True)
class DocumentMeta:
    doc_id: str
    title: str
    issue_date: date | None
    detail_url: str
    pdf_url: str | None


@dataclass(frozen=True)
class DocumentRef:
    source_url: str
    doc_meta: DocumentMeta


@dataclass(frozen=True)
class VerifyReport:
    source_name: str
    ok: bool
    access_method: str
    detail: str
    checks: dict[str, bool] = field(default_factory=dict)


class Source(Protocol):
    name: str
    regulator: str

    def verify(self, client: Client) -> VerifyReport: ...

    def discover(self, client: Client, window: DateWindow) -> Iterator[DocumentRef]: ...

    def parse_listing_meta(self, raw: bytes) -> list[DocumentMeta]: ...
