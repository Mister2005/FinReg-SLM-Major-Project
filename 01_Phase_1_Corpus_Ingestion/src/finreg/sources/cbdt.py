from __future__ import annotations

from typing import Iterator

from finreg.config import DateWindow
from finreg.http.client import Client, HostPolicy
from finreg.sources.base import DocumentMeta, DocumentRef, VerifyReport
from finreg.sources.registry import register

REGULATOR = "cbdt"

# Verified 2026-08-03: every path on this host returns Akamai's 403 "Access
# Denied" (errors.edgesuite.net), for BOTH the project's identifying
# User-Agent and a spoofed browser User-Agent — unlike the RBI PDF host and
# India Code, where a UA swap alone got through. This means the block is not
# UA-string-based and the identity_overrides mechanism (07-LEGAL-AND-CRAWL-
# ETHICS.md "Identification exceptions") does not apply here: that mechanism
# is only justified when the diagnostic proves UA-based blocking, and here it
# proves the opposite. See 03-DATA-SOURCES.md §3 for the full record.
PROBE_URLS = (
    "https://www.incometaxindia.gov.in/pages/communications/circulars.aspx",
    "https://www.incometaxindia.gov.in/circulars",
    "https://www.incometaxindia.gov.in/Communications/Circular/910110000000000929.htm",
)


class CBDTUnavailable(Exception):
    pass


class CBDTCircularsSource:
    name = "cbdt_circulars"
    regulator = REGULATOR

    def verify(self, client: Client) -> VerifyReport:
        policy = HostPolicy(min_interval_seconds=2.0)
        results: dict[str, int] = {}

        for url in PROBE_URLS:
            try:
                result = client.get(url, host_policy=policy)
                results[url] = result.status
            except Exception as exc:  # noqa: BLE001
                results[url] = -1
                results[f"{url}__error"] = str(exc)

        all_blocked = all(status in (403, -1) for url, status in results.items() if not url.endswith("__error"))

        return VerifyReport(
            source_name=self.name,
            ok=not all_blocked,
            access_method="none" if all_blocked else "unknown",
            detail=(
                "All probed paths return Akamai 403 Access Denied for both the identifying "
                "and a browser User-Agent (verified 2026-08-03) — not a UA-based block, so "
                "no identity_overrides exception applies. Requires a full browser engine "
                "(Playwright) or the site allowlisting the crawler; neither is in place. "
                f"Probe results: {results}"
                if all_blocked
                else f"Probe results: {results}"
            ),
            checks={url: status == 200 for url, status in results.items() if not url.endswith("__error")},
        )

    def discover(self, client: Client, window: DateWindow) -> Iterator[DocumentRef]:
        raise CBDTUnavailable(
            "cbdt_circulars has no working access method as of 2026-08-03 — see verify() "
            "and 03-DATA-SOURCES.md §3. Do not call discover() until this is resolved."
        )
        yield  # pragma: no cover - makes this a generator, matching the Source protocol

    def parse_listing_meta(self, raw: bytes) -> list[DocumentMeta]:
        raise CBDTUnavailable("cbdt_circulars has no working access method as of 2026-08-03")


register(CBDTCircularsSource())
