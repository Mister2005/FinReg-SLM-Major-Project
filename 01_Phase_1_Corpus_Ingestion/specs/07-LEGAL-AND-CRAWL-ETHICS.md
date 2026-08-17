# 07 — Legal Position and Crawl Ethics

**This is a student research project, not legal advice, and nothing here is a legal opinion.** It records the basis on which the corpus is assembled so the position is documented, reviewable and correctable. If the college or a reviewer raises a concern, the answer is in this file.

## Copyright position on Indian government regulatory text

Two independent grounds support use of this material.

### 1. Copyright Act, 1957 — section 52(1)(q)

Section 52 of the Copyright Act, 1957 lists acts that do not constitute infringement. Clause (q) covers the reproduction or publication of any Act of a legislature and any rules or orders made thereunder. Clause (iv) of the same section covers judgments and orders of courts and tribunals, unless reproduction is expressly prohibited.

This ground covers: statutes (Income-tax Act, CGST Act, SEBI Act, RBI Act, DPDP Act), rules made under them, and gazette notifications and orders.

### 2. Government Open Data License — India (GODL-India)

The GODL-India, issued under the National Data Sharing and Accessibility Policy, grants a worldwide, royalty-free, non-exclusive licence to use, adapt, publish, translate and create derivative works, for lawful commercial and non-commercial purposes, **subject to attribution**.

This ground covers material published on Government of India open-data portals.

### The gap between the two

**The GODL applies to data published on `data.gov.in` and associated portals. It does not automatically extend to every document on every regulator's own website.** RBI and SEBI each carry their own site terms of use and copyright notice (the RBI site footer asserts "© Reserve Bank of India. All Rights Reserved."). Circulars and Master Directions are not obviously "Acts, rules or orders" in the narrow §52(1)(q) sense, and are not obviously GODL-licensed data either.

This is the honest position: **for regulator-issued circulars and directions, the licensing basis is site terms of use plus the academic and non-commercial nature of the work, and is not as clean as for statutes.**

### How this is operationalised

Every record carries a `licence` tag:

| Tag | Applies to | Export treatment |
|---|---|---|
| `statutory_s52_1_q` | Acts, rules, gazette notifications, orders | Included everywhere |
| `godl_india` | Material sourced from a portal explicitly carrying GODL | Included everywhere |
| `gov_site_terms` | Regulator circulars, directions, guidelines from official regulator sites | Included in `corpus`, `corpus_clean`; retained for training and retrieval; attribution mandatory |
| `unverified` | Anything whose licensing basis could not be established | **Excluded from any training export.** Available for retrieval-only use. Count reported in the corpus card. |

Before Phase 2 training begins, the `gov_site_terms` tier should be reviewed with the project guide, and — if the college has a legal or library contact — with them. The tiering exists so that decision is a one-line config change, not a re-crawl.

### Attribution

Every export carries per-record attribution, and the corpus card carries a global attribution block:

> Contains public regulatory documents published by the Reserve Bank of India, the Securities and Exchange Board of India, the Central Board of Direct Taxes, the Central Board of Indirect Taxes and Customs, and the Ministry of Electronics and Information Technology, Government of India. Reproduced for academic research. Rights in the underlying documents remain with the respective publishers.

Any paper, poster or demo built on this corpus repeats that attribution.

## What must never enter the corpus

| Excluded | Why |
|---|---|
| TaxGuru, CAclubindia, ClearTax, Taxmann, CCH, TaxTMI, Taxscan and similar | Copyrighted editorial commentary and curated compilations. Reading them to orient yourself is fine; ingesting them is not. |
| Law-firm client alerts and Big Four briefings | Copyrighted. |
| Third-party mirrors and scraper aggregators | Unclear rights, unverifiable provenance, and they defeat the point of a primary-source corpus. |
| Section-mapping tables published by commercial tax portals | Copyrighted compilations. Use the official CBDT mapping if it exists; otherwise record the gap. |
| Anything behind authentication or a paywall | Both licensing and NFR-5. |

If a needed fact exists only in a commercial compilation, that is a `known_gaps` entry, not a licence to copy.

## Crawl ethics

These are not optional and are enforced in code (invariant I4).

### Rate limiting
1 request per 2 seconds per host, concurrency 1 per host, as the default and the ceiling for a first run. These are public-service websites operated on public money; a research project has no claim on their capacity.

### Identification
Every request sends `User-Agent: FinReg-SLM-Research/1.0 (academic corpus construction; <contact-email>)`. The contact email is a required config value and the client refuses to start without it. If a site operator wants to reach you, they can.

### robots.txt
Fetched and honoured per host. A disallowed path is skipped and recorded as skipped, never fetched via a workaround. If robots.txt disallows a path this project needs, the correct response is to email the regulator's webmaster and ask, not to ignore the file.

### Backoff
On 429 or 503, honour `Retry-After` if present, otherwise exponential backoff base 2 s with full jitter, capped at 120 s, 5 attempts. On repeated 429s from a host, halve that host's rate for the remainder of the run and log it.

### Caching
Conditional requests using stored `ETag` / `Last-Modified`. A refresh crawl should mostly produce 304s. If a refresh is re-downloading everything, that is a bug to fix, not a cost to absorb.

### Off-hours
Schedule long cold crawls outside Indian business hours (IST 09:00–18:00) where practical. Not enforced in code; stated as operating practice in the runbook.

### No browser automation by default
Playwright or Selenium may only be used for a source where the underlying API or form POST is demonstrably unavailable. Headless browsers are heavier on the origin and harder to rate-limit correctly. Any use must be recorded in the corpus card's `source_access_methods`.

### No parallel identity
No proxy rotation, no user-agent rotation, no IP cycling. If a site blocks this crawler, the crawl stops and the block is investigated and reported — it is not routed around.

### Identification exceptions

One narrow, deliberate exception exists, added 2026-08-03 during M1 (RBI) implementation.

**Finding.** `rbidocs.rbi.org.in` (the RBI PDF host, distinct from `www.rbi.org.in`) actively resets the connection for the project's identifying User-Agent — `httpx.RemoteProtocolError: Server disconnected without sending a response` on every attempt, including after a session warmup on the main site and with cookies/Referer carried over. This is not a missing-header problem; it reproduces consistently and looks like WAF fingerprinting of the client itself. `www.rbi.org.in` (all HTML pages, including the notification bodies) does not exhibit this behaviour. See `03-DATA-SOURCES.md` §1.1 for the verification detail.

**Decision.** Rather than leave RBI PDFs permanently unreachable, the project owner explicitly authorised a scoped, config-driven, logged exception: `config/sources.yaml`'s `identity_overrides` section maps specific hosts to an alternate `User-Agent`, used only for that host, only when explicitly configured. Every use is logged (`identity_override_used`, with the host and the documented reason) so it is auditable in every run's JSONL log, not silent. This does not touch rate limiting, robots.txt handling, retry/backoff, or any other politeness mechanism — those remain unconditional and unaffected (I4's single choke point still applies; the override changes one header on one host).

**Why this is recorded as an exception rather than a policy change.** The default remains "no parallel identity" for every other host. This override exists for exactly one host, is visible in a version-controlled config file with its justification inline, is logged on every use, and should be removed if RBI allowlists the crawler's real identity (the honest path recommended below remains open in parallel). A future auditor reading this file sees the exception, its justification, its scope, and the date it was made — nothing here is hidden by the code.

**Also still true:** the runbook should record that emailing RBI's webmaster to request allowlisting of the `FinReg-SLM-Research/1.0` UA for `rbidocs.rbi.org.in` is the preferred long-term fix, per the same logic doc 07 already applies to robots.txt blocks ("the correct response is to email... and ask, not to ignore the file"). The override is a pragmatic interim measure for a student project's PDF coverage, not a replacement for that request.

**Second instance, added 2026-08-03 during M2 (India Code) implementation.** `www.indiacode.nic.in` — the entire site, not one sub-host — returns a hard `403 Access Denied` from an Akamai edge WAF for the identifying UA, on every path including the root. The same diagnostic used for the RBI PDF case was repeated here first (holding every other request property constant and swapping only the UA) before reaching for the override, confirming this is UA-based blocking and not a missing header, malformed request, or something the honest client could fix by behaving more politely. The same mechanism was applied — a scoped `identity_overrides` entry for `www.indiacode.nic.in`, nothing else changed. This establishes the pattern as repeatable: when a site's WAF is confirmed (not assumed) to block the honest UA specifically, and the diagnostic showing that is recorded here and in doc 03, the same scoped/logged/documented override applies without re-litigating the decision each time — the standard, not the specific host, is what was authorised. Emailing India Code's listed contact to request allowlisting is, as with RBI, the preferred long-term fix; this override is the interim measure.

**Third instance, added 2026-08-03 during M2 (MeitY) implementation.** `www.meity.gov.in` shows the identical signature: honest UA → 403, browser UA → 200, everything else held constant. Same override, same scope, same standing justification — see doc 03 §5. Not every site that returns a 403 gets this treatment automatically: CBDT (`www.incometaxindia.gov.in`) was tested the same way during this same milestone and its 403 persisted even with a browser UA, so *no* override was applied there — see doc 03 §3 and `sources/cbdt.py`. The override is earned by the diagnostic, not assumed from the error code.

## Personal data

Regulatory circulars are institutional documents, but adjudication orders, penalty notices and informal guidance letters **do name individuals and firms**. Since DPDP compliance is part of this project's own subject matter, the project holds itself to it:

- SEBI Orders and Informal Guidance are **disabled by default** in `config/sources.yaml`.
- If enabled later, records must be flagged `contains_personal_data` and excluded from any public release of the corpus.
- No public release of the corpus includes any document tagged `contains_personal_data`, regardless of its licence tag.

## Publication of the corpus

If the corpus is released alongside the paper, release **the acquisition code, the manifest schema, and the corpus card** rather than a bulk dump of regulator PDFs. This gives full reproducibility, keeps the authoritative copy with the regulator where it belongs, and avoids the redistribution question entirely. Anyone can rebuild the corpus from the code in 72 hours.

State this explicitly in the paper's data-availability statement.
