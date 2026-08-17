from __future__ import annotations

from typing import Iterator

from finreg.config import DateWindow
from finreg.http.client import Client, HostPolicy
from finreg.sources.base import DocumentMeta, DocumentRef, VerifyReport
from finreg.sources.registry import register

REGULATOR = "meity"

# Verified 2026-08-03: www.meity.gov.in's DPDP-related pages (root,
# /data-protection-framework, /dpdpa2023) are all served by a Next.js SPA
# (digifootprint.gov.in build) that returns an essentially empty HTML shell
# with content populated client-side by JavaScript
# (/_next/static/chunks/...). A plain HTTP client — this crawler,
# deliberately, per 07-LEGAL-AND-CRAWL-ETHICS.md's "no browser automation by
# default" — sees none of the real content. This is architecturally
# different from the RBI/India Code/MeitY-root UA-based blocks: an
# identity_overrides UA swap does nothing here, because nothing is blocking
# the request — the server just doesn't render the content without a JS
# engine. egazette.gov.in (the other documented host for DPDP Rules gazette
# publication) times out entirely from this network. See 03-DATA-SOURCES.md
# §5. Per 08-IMPLEMENTATION-PLAN.md's explicit cut list ("Drop MeitY DPDP" is
# item 1 if a source is consuming disproportionate time), this source is
# disabled rather than pulled in via Playwright in this pass.
PROBE_URLS = (
    "https://www.meity.gov.in/",
    "https://www.meity.gov.in/data-protection-framework",
)


class MeitYUnavailable(Exception):
    pass


class MeitYDPDPSource:
    name = "meity_dpdp"
    regulator = REGULATOR

    def verify(self, client: Client) -> VerifyReport:
        policy = HostPolicy(min_interval_seconds=2.0)
        checks: dict[str, bool] = {}

        for url in PROBE_URLS:
            try:
                result = client.get(url, host_policy=policy)
                is_js_shell = b"__NEXT_DATA__" in result.body and len(result.body) < 10_000
                checks[url] = result.status == 200 and not is_js_shell
            except Exception:  # noqa: BLE001
                checks[url] = False

        ok = any(checks.values())
        return VerifyReport(
            source_name=self.name,
            ok=ok,
            access_method="none" if not ok else "unknown",
            detail=(
                "All probed MeitY pages are client-rendered Next.js SPA shells with no "
                "server-side content (verified 2026-08-03) — requires a JS-executing client, "
                "which this crawler deliberately does not use by default. See "
                "03-DATA-SOURCES.md §5 and 08-IMPLEMENTATION-PLAN.md's cut list."
                if not ok
                else "at least one probed page returned real server-rendered content"
            ),
            checks=checks,
        )

    def discover(self, client: Client, window: DateWindow) -> Iterator[DocumentRef]:
        raise MeitYUnavailable(
            "meity_dpdp has no working access method as of 2026-08-03 (client-rendered SPA) — "
            "see verify() and 03-DATA-SOURCES.md §5."
        )
        yield  # pragma: no cover - makes this a generator, matching the Source protocol

    def parse_listing_meta(self, raw: bytes) -> list[DocumentMeta]:
        raise MeitYUnavailable("meity_dpdp has no working access method as of 2026-08-03")


register(MeitYDPDPSource())
