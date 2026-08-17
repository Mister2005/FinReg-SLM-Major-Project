# 03 — Data Sources

**Verification status.** Every pattern marked ✅ was fetched and confirmed on **2026-08-03**. Patterns marked ⚠️ are documented from search results or site structure but were not fetched end-to-end; the implementing agent must confirm them in `verify()` before relying on them. Nothing in this document is invented — where a detail is unknown it says so.

**Volume figures** are the counts observed on 2026-08-03 where a site displayed them, and are marked as such. They are checkpoints for `verify()`, not targets. Do not treat a mismatch as failure; treat it as a signal to re-read the listing.

---

## 1. Reserve Bank of India

### 1.1 Notifications (circulars, directions, amendments) — primary RBI source

**Listing** ✅ `https://www.rbi.org.in/Scripts/NotificationUser.aspx`

**Detail page** ✅ `https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=<int>&Mode=0`

**Attached PDF** ✅ `https://rbidocs.rbi.org.in/rdocs/notification/PDFs/<OPAQUE>.PDF` — filename is an opaque uppercase hash-like token, not derivable. It must be scraped from the detail or listing page. Never construct it.

**Critical structural finding.** The year/month archive navigation on the listing page uses ASP.NET `__doPostBack` links (every year link has `href="#"`). Reproducing that requires round-tripping `__VIEWSTATE`, `__VIEWSTATEGENERATOR` and `__EVENTVALIDATION` on every page transition — brittle and slow.

**Therefore the RBI strategy is sequential ID enumeration, not archive pagination.** Observed on 2026-08-03: `Id=13553` corresponded to a notification dated 2026-06-29, and IDs decrease monotonically with age (`Id=12460` → March 2023; `Id=6260` → 2011; `Id=2455` → 2005-06). IDs are dense but not perfectly contiguous — gaps exist and a gap is not an error.

**Enumeration procedure.**
1. Fetch the listing page, take the highest `Id` present as `id_max`.
2. Binary-search downward for the boundary ID whose page date is ≥ `window.start`. Fetch a candidate, parse its date, and bisect. Expect ~15 requests to locate the boundary.
3. Walk `id_min … id_max` inclusive. Record 404s and empty pages as `http_4xx`, not as crawl failure.
4. Persist `id_max` per run so incremental refresh only walks upward from the last known maximum.

Parse from each detail page: title, date, RBI reference number (format `RBI/<FY>/<seq>` plus a departmental reference such as `DGBA.GBD.No.S1469/42-01-029/2022-2023`), addressee block, body HTML, and the linked PDF URL. Fetch both the HTML body and the PDF; the HTML is usually cleaner, the PDF is authoritative. Store both; prefer HTML text with the PDF as fallback and as the citable artefact.

**Verified 2026-08-03 (M1 implementation).** Two findings from a live 51-ID contiguous probe (`Id=13600`–`13650`) and direct fetch testing, both confirmed reproducible:

1. **`rbidocs.rbi.org.in` PDF downloads are behind an F5/TSPD bot-detection JS challenge.** A plain HTTP client (no JS execution) fetching any URL under `https://rbidocs.rbi.org.in/rdocs/notification/PDFs/...` receives HTTP 200 with an HTML bot-challenge page instead of the PDF bytes — `Content-Type: text/html`, not `application/pdf`. This was consistent across multiple distinct PDF URLs. The extraction router correctly classifies this as `content_type_unexpected` rather than silently accepting HTML as a PDF, but it means **no RBI PDF can currently be fetched by the crawler** — only the HTML notification body. A future ticket must address this (headless-browser fallback, session/cookie warm-up, or accepting HTML-only text for RBI and flagging `pdf_url` as unfetchable) before RBI PDFs enter the corpus. `www.rbi.org.in` (the HTML pages) does **not** show this behaviour for a plain client.
2. **A significant share of recent notifications — the November 2025 consolidation's "Directions" documents in particular — have an empty `tablecontent2` body cell**: just a title and a PDF link, no inline `<p>` paragraphs at all. For these, `issue_date`, the RBI reference number and the addressee cannot be parsed from HTML (there is no HTML text containing them) and correctly land as `NULL` with a `metadata_gaps` entry rather than being guessed. In the 51-ID live probe, roughly 70% of documents were of this body-less type. Recovering their dates will require parsing the (currently unfetchable, see finding 1) PDF — this is expected to resolve once finding 1 is addressed, not a separate defect.

### 1.2 Master Directions ✅ `https://www.rbi.org.in/Scripts/BS_ViewMasterDirections.aspx`

High value. As of the RBI's consolidation announced 2025-11-28, Master Directions are the canonical consolidated statement of RBI regulation, organised function-wise across categories of regulated entity. These are the documents a compliance officer actually reads.

### 1.3 Master Circulars ✅ `https://www.rbi.org.in/Scripts/BS_ViewMasterCirculardetails.aspx`

Annual consolidations. Each Master Circular lists the circulars it subsumes — parse that list into the supersession graph (see doc 06).

### 1.4 Amendment Directions ✅ `https://www.rbi.org.in/Scripts/Fs_AmendmentDirections.aspx`

Amendments to Master Directions. Essential for reconstructing what a Direction said at a given date.

### 1.5 Circulars Withdrawn ✅ `https://www.rbi.org.in/Scripts/NotificationUserWithdrawnCircular.aspx`

**This page is the single highest-value metadata source in the entire corpus.** It is RBI's own list of circulars no longer in force. Ingest it in full and use it to set `status = 'withdrawn'`. Crawl it before the main notification crawl so status can be assigned as documents arrive.

### 1.6 Index to RBI Circulars ✅ `https://www.rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx`
### 1.7 Standalone Circulars ✅ `https://www.rbi.org.in/Scripts/BS_ViewListofstandalonecirculars.aspx`
### 1.8 Legal framework ✅
- Acts: `https://www.rbi.org.in/Scripts/Act.aspx`
- Rules: `https://www.rbi.org.in/Scripts/Rules.aspx`
- Regulations: `https://www.rbi.org.in/Scripts/Regulations.aspx`
- Schemes: `https://www.rbi.org.in/Scripts/Schemes.aspx`

### 1.9 RSS ✅ `https://www.rbi.org.in/Scripts/rss.aspx`

Use for incremental refresh only. Not a substitute for the ID walk.

**Hosts:** `www.rbi.org.in` (pages), `rbidocs.rbi.org.in` (PDFs). Throttle them independently but conservatively — treat as one logical origin at 1 req/2 s each.

---

## 2. Securities and Exchange Board of India

**Listing endpoint** ✅ `https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=<int>&ssid=<int>&smid=<int>`

**Verified section map** ✅

| Section | sid | ssid | smid |
|---|---|---|---|
| Rules | 1 | 2 | 0 |
| Regulations | 1 | 3 | 0 |
| Guidelines | 1 | 5 | 0 |
| Master Circulars | 1 | 6 | 0 |
| **Circulars** | 1 | 7 | 0 |
| Gazette Notification | 1 | 82 | 0 |
| Informal Guidance | 2 | 10 | 0 |
| Orders (optional, off by default) | 2 | 9 | 2 |

**Observed volume** ✅ Circulars section showed **2,786 active records, 25 per page, 112 pages** on 2026-08-03.

**Detail URL pattern** ✅ `https://www.sebi.gov.in/legal/circulars/<mon-yyyy>/<title-slug>_<docid>.html` — e.g. `.../legal/circulars/jul-2026/intraday-borrowing-facility-availed-by-mutual-funds_102762.html`. The trailing integer is SEBI's document ID. Slugs are derived from titles and are not reliably reconstructable; always take the href from the listing.

**Pagination** ✅ Client-side JS: `searchFormNewsList('n', <zero_based_page>)`. Implement by replaying the underlying form POST to `HomeAction.do` rather than driving a browser. The listing page carries a search form exposing **date-from / date-to**, **Department**, **Sub Section**, **Sub Sub Section** and **Intermediary** filters — use the date filter to window the crawl and keep result sets small and stable.

**Archive toggle** ✅ The listing exposes an `Active` / `Archive` switch (`showCircularArchive()`). **The Archive view is SEBI's own list of no-longer-current circulars.** Crawl both views; the Active/Archive split populates `status` directly, the same role RBI's withdrawn page plays.

**Verify() assertions:** the record-count string parses; page 2 returns 25 distinct hrefs disjoint from page 1; a known detail URL returns 200 with a matching title.

**Observed flakiness — real, not a code defect.** Repeated `verify()` runs within a short window (tested 2026-08-03, several runs a few minutes apart) intermittently return the *same* 25 records for both "page 1" and "page 2" of the AJAX pagination endpoint — i.e. `page2_disjoint_from_page1` sometimes fails, sometimes passes, with no code change between runs. This looks like a caching layer in front of `getnewslistinfo.jsp` occasionally serving a short-lived cached response regardless of the `doDirect` parameter. `sources/sebi.py`'s pagination logic itself is correct (confirmed via a controlled fixture pair fetched back-to-back, and via a live 3-page/75-document crawl that produced 74 distinct real documents). If `finreg sources verify` reports this specific check as failing, retry once before treating it as a real regression.

**Departments exposed in the filter** ✅ (useful as a controlled vocabulary for the `department` field): Alternative Investment Fund and Foreign Portfolio Investors; Corporation Finance; Economic and Policy Analysis; Debt and Hybrid Securities; Enforcement-1; Information Technology; Investment Management; Market Intermediaries Regulation and Supervision; Market Regulation; Investor Assistance and Education.

**Host:** `www.sebi.gov.in`.

---

## 3. Central Board of Direct Taxes / Income Tax Department

**Entry points** ✅
- `https://www.incometaxindia.gov.in/circulars`
- `https://www.incometaxindia.gov.in/notifications`
- `https://incometaxindia.gov.in/Pages/communications/index.aspx`

**Legacy document pattern** ✅ `https://incometaxindia.gov.in/Communications/Circular/<20-digit-id>.htm` — e.g. `.../Communications/Circular/910110000000000929.htm`. Older material lives here as HTML; some of it is poorly formed and character-spaced (observed), which will need aggressive normalisation.

**Modern document pattern** ✅ `https://www.incometaxindia.gov.in/documents/<num>/<num>/<slug>.pdf/<uuid>?t=<epoch_ms>` — e.g. the CBDT FAQ on transition to the Income-tax Act, 2025. The `?t=` cache-buster and the UUID make these unconstructable; always scrape the href.

⚠️ The listing pages are ASP.NET/SharePoint-backed and the exact pagination parameters were not confirmed end-to-end. The source module must implement `verify()` to determine whether pagination is query-string driven or postback driven before crawling, and log which it found.

**Documents to capture**
- CBDT Circulars (numbered `Circular No. n/YYYY`)
- CBDT Notifications (S.O. and G.S.R. series)
- Instructions and Office Memoranda
- Income-tax Act, 1961 (full text) — via India Code, section 7
- Income-tax Rules, 1962 (full text)
- **Income-tax Act, 2025** and **Income-tax Rules** notified thereunder
- CBDT transition FAQs and the official 1961→2025 section mapping, if published as a document

**Regime break — read `06-TEMPORAL-VALIDITY-SPEC.md` before writing this module.** The Income-tax Act, 2025 came into force on **2026-04-01**, repealing the Income-tax Act, 1961. Section numbering changed comprehensively (from 819 sections across 23 chapters to 536 sections across 23 chapters, per PwC's summary of the enacted Act). A corpus that flattens this will produce a model that cites repealed section numbers with confidence. Every direct-tax record must be regime-tagged.

**Host:** `www.incometaxindia.gov.in` (note: also resolves without `www.`; canonicalise to `www.`).

**Access blocked — verified 2026-08-03, M2 implementation.** Every path tried on this host (`/pages/communications/circulars.aspx`, `/circulars`, and a legacy `.htm` circular URL) returns an Akamai `403 Access Denied` (`errors.edgesuite.net` reference IDs). Unlike the RBI PDF host and India Code, **this is not resolved by a User-Agent swap** — a full browser-UA request gets the identical 403, tested with every other request property held constant. This rules out the `identity_overrides` mechanism (07-LEGAL-AND-CRAWL-ETHICS.md "Identification exceptions"), which is only justified when the diagnostic shows UA-based blocking; here it shows the opposite. `sources/cbdt.py`'s `verify()` correctly detects and reports this rather than crawling blind or returning a silent zero-document crawl. `cbdt_circulars` is `enabled: false` in `config/sources.yaml` pending either a full browser-engine fallback (permitted by doc 07 "only for a source where the underlying API or form POST is demonstrably unavailable" — arguably satisfied here, but out of scope for this pass; a real scope/dependency decision, not a quick fix) or the site allowlisting the crawler. Per `08-IMPLEMENTATION-PLAN.md`'s explicit guidance, the milestone proceeds without CBDT rather than absorbing unbounded time on one source.

---

## 4. Central Board of Indirect Taxes and Customs (GST)

**Modern portal** ✅ `https://taxinformation.cbic.gov.in/`
- Circulars index: `https://taxinformation.cbic.gov.in/content-page/explore-circulars`
- Notifications index: `https://taxinformation.cbic.gov.in/content-page/explore-notification`

**Direct document pattern** ✅ `https://taxinformation.cbic.gov.in/view-pdf/<docid>/ENG/Circulars` — observed IDs include 1000234, 1002906, 1003137, 1003166, 1003187. IDs are numeric and appear enumerable, but the density and the meaning of the ranges were **not** established. Do not assume contiguity.

⚠️→✅ **Resolved 2026-08-03, but not the way this section anticipated.** `taxinformation.cbic.gov.in` fails TLS certificate verification for a standards-compliant HTTPS client (`SSL: CERTIFICATE_VERIFY_FAILED`, confirmed with `verify=False` diagnostics that the server *does* respond 200 once cert checking is bypassed — this is a real certificate-chain problem on the site's end, not a network issue on this side). This project does not disable TLS verification as a workaround (a categorically more dangerous move than a UA header, and not one this crawler does silently). `verify()` therefore treats the modern SPA as unreachable — correctly, per this section's own original contingency — and falls back to the legacy static portal, which works fine over TLS with the honest UA.

**Legacy static portal** ✅ `https://cbic-gst.gov.in/circulars-cgst.html` is the **English** path (verified 2026-08-03; the `.../hindi/circulars-cgst.html` path noted here previously actually also serves English content — the "hindi" URL segment is misleading, not a language switch). Plain HTML table, columns Circular No. | English (PDF link) | हिन्दी (PDF link) | Date of issue | Subject.

**Coverage limitation — real finding, not a bug.** This legacy page currently lists only **10 circulars/orders, all dated September 2017**. It reads as a frozen historical snapshot rather than a live-maintained index — there is no visible pagination or "load more" mechanism, and no CGST circular from 2018 onward appears on it. The current, actively-updated GST circular content lives on the (TLS-broken) modern SPA. Until the SPA's certificate is fixed or the crawler can safely reach it another way, `cbic_circulars` genuinely only contributes these 10 2017 documents — recorded honestly in `known_gaps`, not padded.

**Documents to capture:** CGST/IGST/UTGST circulars, notifications (Central Tax, Central Tax Rate, Integrated Tax), orders, and the CGST Act 2017 + CGST Rules 2017 full text (via India Code where cleaner).

**Host:** `taxinformation.cbic.gov.in` (currently unreachable — TLS cert failure), `cbic-gst.gov.in` (working, limited coverage).

---

## 5. MeitY — Digital Personal Data Protection

**Documents to capture**
- Digital Personal Data Protection Act, 2023 (published 2023-08-11)
- **Digital Personal Data Protection Rules, 2025** — notified by MeitY on **2025-11-13** and gazetted; press coverage dates the gazette publication 13–14 November 2025 (sources differ by a day; store both the notification date and the gazette date and do not reconcile them by guessing).
- The separate enforcement/commencement notifications, the Data Protection Board establishment notification, and the notification on the number of Board members.

**Phased commencement — this is a benchmark goldmine.** Provisions come into force on three dates: **13 November 2025**, **13 November 2026**, and **13 May 2027** (a small number of secondary sources state 14 November 2025 / 14 November 2026 / 14 May 2027 — record the discrepancy in `metadata_gaps`, do not silently pick one). This means "is Rule X in force?" has a different correct answer depending on the query date, which is exactly the temporal-reasoning capability the benchmark should test.

⚠️→❌ **Blocked, verified 2026-08-03 — architecturally different from every other block found this session.** `www.meity.gov.in` (root, `/data-protection-framework`, `/dpdpa2023`) all serve a client-rendered Next.js SPA shell (`digifootprint.gov.in` build) — the raw HTML is ~3KB of `<script>` tags and an empty `__NEXT_DATA__` blob; no document links, no text, nothing for a non-JS client to read. This is *not* a WAF/bot-defense block (the honest UA gets the same empty shell as a browser UA would over plain HTTP — the content genuinely doesn't exist until JavaScript runs), so the `identity_overrides` mechanism used for the three UA-based blocks elsewhere in this document does not help here. `egazette.gov.in` timed out entirely from the network this was tested on. Per `08-IMPLEMENTATION-PLAN.md`'s cut list (MeitY DPDP is explicitly item 1 — "small corpus contribution, though it costs the best temporal benchmark material"), this source is disabled (`sources/meity.py`, `verify()` correctly detects and reports the JS-shell condition) rather than pulled in via Playwright in this pass. The DPDP phased-commencement dates in this section remain accurate and valuable for Phase 3 benchmark design even without the crawled documents; if this source is revisited, a headless-browser fallback is the documented, permitted path (doc 07 "No browser automation by default" — the underlying API being unavailable is satisfied here).

**Host:** `www.meity.gov.in` (client-rendered SPA, no crawlable content without JS execution), `egazette.gov.in` (timed out).

---

## 6. IRDAI (optional, disabled by default)

⚠️ Not verified. Enable only if Phase 2 scope extends to insurance. If enabled, the module must implement `verify()` from scratch and document the discovered structure here before crawling.

---

## 7. India Code — statutes and subordinate legislation

**Root** ✅ `https://www.indiacode.nic.in/`

**Platform** ✅ DSpace 5.5 (confirmed via page `Generator` meta tag, 2026-08-03). Observed patterns:
- Item handle: `https://www.indiacode.nic.in/handle/123456789/<id>` — verified working example (fetched live 2026-08-03): `/handle/123456789/1631` (The Advocates Act, 1961). **The two example handles previously recorded here (`2435` for Income-tax Act 1961, `15240` for Constitution of India) are STALE and no longer resolve** — both now return DSpace's "Invalid URL or Argument(s)." error page. Never hardcode a handle ID; always obtain it from a browse-page or item listing fetched in the same run.
- Bitstream (PDF): `https://www.indiacode.nic.in/bitstream/123456789/<id>/<n>/<filename>.pdf` — verified live: `/bitstream/123456789/1631/4/A1961-25.pdf` (English; filenames prefixed `A`) alongside `.../3/H1961-25.pdf` (Hindi; prefixed `H` — skip these, take the `A`-prefixed one). Always scrape the href from the item page; the `<n>` bitstream-sequence-id is not predictable.
- Browse by year: `https://www.indiacode.nic.in/handle/123456789/1362/browse?type=actyear&value=<year>` — works and returns a real, parseable `table.itemDisplayTable`-adjacent results table with working "View..." links.

✅ **OAI-PMH and REST confirmed absent** (verified 2026-08-03): `/oai/request?verb=Identify`, `/dspace-oai/request?verb=Identify`, `/rest/test` and `/server/api` all return plain 404. Handle traversal via the `browse?type=actyear` index is therefore the only viable mechanism, exactly as this section anticipated.

⚠️ **The `actyear` browse facet has incomplete coverage — a real, verified finding, not a scraper bug.** Querying `value=1934` for the Reserve Bank of India Act returns only 2 unrelated acts (RBI Act absent) when browsed manually with a narrow `rpp`; against this, the site's own search (`/simple-search`) would resolve it directly, but **`/simple-search` is disallowed by `robots.txt`** and must not be used (I4/doc 07 — no workaround). In practice, driving the full `crawl_statutes()` search (checking every `STATUTE_TARGETS` entry's own labelled year, matching by short-title substring) still resolved **12 of the 15 target statutes** in a live run: RBI Act 1934, Banking Regulation Act 1949, FEMA 1999, Payment and Settlement Systems Act 2007, SEBI Act 1992, SCRA 1956, Depositories Act 1996, Companies Act 2013, IBC 2016, CGST Act 2017, IGST Act 2017, DPDP Act 2023 all found with correct act numbers and enactment dates. **Not found: Prevention of Money-Laundering Act 2002, Income-tax Act 1961, Income-tax Act 2025** — none appear in their respective `actyear` buckets on this mirror. These three need either a working search path (pending India Code's response to an allowlisting request, same as the identity-override situation) or manual handle lookup; recorded honestly rather than guessed, per I3.

**Access note:** `www.indiacode.nic.in` returns a hard `403 Access Denied` (Akamai edge WAF) for the project's honest, identifying User-Agent on every path — confirmed via the same UA-swap diagnostic used for the RBI PDF host. A scoped, logged `identity_overrides` entry (see `07-LEGAL-AND-CRAWL-ETHICS.md` "Identification exceptions") is required for this entire host, not just PDFs.

**Self-critique, recorded 2026-08-03.** By late in this implementation session, `www.indiacode.nic.in` began timing out on every request (30s+), including for the working, cert-valid browser-UA path that succeeded earlier the same session. The most likely cause: ad hoc diagnostic probing during development (raw `httpx.get()` calls used to quickly test hypotheses about handle IDs, OAI/REST availability, and browse-facet coverage) went **around** `finreg.http.client.Client` and its 2-second-per-host throttle — dozens of unthrottled requests were sent to this host in quick succession while investigating. That is not how the actual crawl path works (every real fetch, in every source module, goes through the throttled `Client`), but it is a real lapse in how this session conducted its own reconnaissance, and it plausibly triggered rate-limiting or a temporary soft-block on this IP. Documented honestly rather than silently blamed on the site. If `finreg sources verify` reports `indiacode_statutes` as failing shortly after heavy interactive development against this host, that is the likely cause — wait and retry, or verify from a different network path, before concluding the access method itself has broken. The module's correctness is independently established by its passing unit tests against real fixtures and by the live 12/15-statute crawl recorded above.

**Statutes to capture (full text, latest consolidated version):** Reserve Bank of India Act 1934; Banking Regulation Act 1949; FEMA 1999; Payment and Settlement Systems Act 2007; SEBI Act 1992; Securities Contracts (Regulation) Act 1956; Depositories Act 1996; Companies Act 2013; Insolvency and Bankruptcy Code 2016; Prevention of Money Laundering Act 2002; Income-tax Act 1961; Income-tax Act 2025; CGST Act 2017; IGST Act 2017; Digital Personal Data Protection Act 2023.

**Host:** `www.indiacode.nic.in`.

---

## 8. Source priority

Crawl in this order. Earlier sources produce metadata that later stages depend on.

1. RBI Circulars Withdrawn + SEBI Archive listing (status metadata)
2. RBI Master Directions, Master Circulars, Amendment Directions (supersession metadata)
3. India Code statutes (statutory anchors for citation resolution)
4. RBI Notifications (largest volume)
5. SEBI Circulars, Master Circulars, Regulations
6. CBDT Circulars and Notifications
7. CBIC GST Circulars and Notifications
8. MeitY DPDP

## Sources deliberately excluded

| Excluded | Reason |
|---|---|
| Aggregators (TaxGuru, CAclubindia, ClearTax, Taxmann, CCH, TaxTMI) | Copyrighted editorial content. Useful for orientation while writing this spec; **must never enter the corpus.** |
| Bankopedia-style scraper mirrors | Third-party reproductions with unclear rights and no provenance guarantee. Always go to the regulator. |
| Wikipedia | Not a primary source. |
| Court judgments and tribunal orders | Out of Phase 1 scope; different licensing analysis. |
| Anything behind a login or paywall | Invariant NFR-5. |
