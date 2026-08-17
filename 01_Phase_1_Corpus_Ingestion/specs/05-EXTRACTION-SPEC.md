# 05 — Extraction Specification

## Routing

```
content_type / magic bytes
├── application/pdf      → PDF path
├── text/html            → HTML path
└── anything else        → fetch_failures(content_type_unexpected)
```

## PDF path

### Stage 1 — embedded text layer (`pypdfium2`)

Extract per page. Record `chars_per_page` for every page.

**Decision rule.**

| Condition | Action |
|---|---|
| median `chars_per_page` ≥ 250 | Accept. `text_source = pdf_layer`. |
| median `chars_per_page` < 250 and page has ≥ 1 large raster image covering > 60% of page area | Route to OCR. |
| median `chars_per_page` < 250, no dominant image | Retry with `pdftotext -layout`. If that clears 250, accept as `text_source = pdftotext`; otherwise route to OCR. |
| Any page raises on open | `fetch_failures(pdf_corrupt)` after trying both extractors. |

The 250 threshold is a starting value, not a law. It is in `config/sources.yaml` as `extraction.min_chars_per_page` and must be re-tuned once the first 500 real documents are in — record the tuned value and the evidence in the QA report.

### Stage 2 — OCR fallback

`ocrmypdf --skip-text --rotate-pages --deskew -l eng --output-type pdf <in> <out>`, then extract text from the output.

- Store the OCR'd PDF as a new blob linked to the original.
- Record mean per-word confidence. Documents below `extraction.min_ocr_confidence` (start at 0.70) get `quality_flags: low_ocr_confidence` and are excluded from `corpus_clean`.
- `text_source = ocr`. Phase 2 must be able to exclude all OCR text with one filter, because OCR errors in numeric tax rates are a specific and serious hazard for this domain.

### Stage 3 — tables

`pdfplumber` table extraction per page, both `lattice` and `stream` settings; keep whichever yields more well-formed rows. Store cell matrices in `tables_extracted`.

**Tables matter disproportionately here.** TDS rate schedules, capital-adequacy tables, GST rate notifications and penalty schedules are tables. A flattened text rendering of a rate table is the single most likely source of a wrong answer in the finished model. Where a table is detected, the linear text must also include a readable serialisation of it — pipe-delimited rows with the header repeated — rather than the raw column-shuffled text pdfium produces.

## HTML path

Parse with `selectolax`.

1. Isolate the content region. For RBI, this is the main notification body within the page's content container; for SEBI, the article body on the detail page. Each source module supplies its own content selector — this is source-specific and belongs in `sources/`, not in `extract/`.
2. Strip: navigation, breadcrumb, font-size and theme controls, "More Links", social-follow blocks, footer disclaimers, print widgets.
3. Preserve: heading hierarchy, ordered and unordered lists with their numbering, table structure, `<pre>` blocks, and paragraph boundaries.
4. Convert tables to the same pipe-delimited serialisation used on the PDF path.

**Do not use a generic boilerplate remover.** Trafilatura, readability and similar tools are tuned for news articles and reliably delete numbered clause lists and short paragraph fragments — which in a circular are the operative provisions. This has to be source-specific selector work.

## Normalisation

Applied to text from every path, in this order:

1. Unicode NFKC.
2. Ligature repair: `ﬁ ﬂ ﬀ ﬃ ﬄ` → ASCII equivalents.
3. Quote and dash normalisation: curly quotes → straight; en/em dash preserved (they carry meaning in section ranges).
4. **Character-spacing repair.** Observed on legacy `incometaxindia.gov.in` HTML: text rendered as `C i r c u l a r   N o .`. Detect when > 40% of a line's characters are single characters separated by single spaces, and collapse. Log every repair to `quality_flags: charspace_repaired` so the transformation is auditable.
5. De-hyphenate line-broken words: `regula-\ntion` → `regulation`, but only when the fragment before the hyphen is not itself a known word and the join produces a dictionary or corpus-frequent word. Conservative: when in doubt, leave it.
6. Repeated header/footer removal: a line appearing at the same relative page position on ≥ 60% of pages is a running header/footer and is removed. Page numbers matching `^\s*\d+\s*$` at page boundaries are removed.
7. Collapse runs of ≥ 3 blank lines to 2. Never collapse to 1 — paragraph structure is signal.
8. Strip trailing site disclaimers matched against a per-source list of known boilerplate strings.

Normalisation never deletes numerals, currency symbols, percentages, or section references. Any normalisation rule that could is out of bounds.

## Structural parsing

### Document number patterns

These are the observed real formats. Store the raw match, not a canonicalised rewrite.

| Regulator | Pattern | Example (observed) |
|---|---|---|
| RBI master reference | `RBI/<FY>/<seq>` | `RBI/2022-23/184` |
| RBI departmental ref | `<DEPT>.<...>/<...>/<FY>` | `DGBA.GBD.No.S1469/42-01-029/2022-2023` |
| CBDT circular | `Circular No. <n>/<YYYY>` | `CIRCULAR NO. 09/2025` |
| CBDT notification | `S.O. <n>(E)` / `G.S.R. <n>(E)` | |
| GST circular | `Circular No. <n>/<n>/<YYYY>-GST` | `Circular No. 192/04/2023-GST` |
| SEBI circular | SEBI's own reference string in the document header | varies by department |

SEBI circular reference formats vary by issuing department and are **not** reliably regular. Parse what matches; leave `doc_number` NULL and record a `metadata_gaps` entry otherwise. Do not force a match.

### Citation extraction

Patterns to detect, each writing a `citations` row with the exact span:

- References to other circulars by number (`Circular No. 3 of 2023 dated 28.03.2023`) — resolve to `target_doc_id` by matching `doc_number` + date.
- Statutory section references (`section 201(1A)(ii)`, `Rule 114AAA of the Income-tax Rules, 1962`) — populate `target_act` and `target_section`.
- Supersession language: `in supersession of`, `stands withdrawn`, `is hereby repealed`, `shall cease to have effect`, `subsumed in`, `partial modification of`. These set `relation`.
- Master Circular / Master Direction consolidation lists — usually an appendix table of subsumed circulars. Parse the table, not the prose.

A citation that cannot be resolved to a `target_doc_id` stays `citation_type = 'unresolved'` with its raw span intact. That is useful data, not a failure.

## Deduplication

MinHash over 5-gram shingles of normalised text, 128 permutations, LSH threshold 0.85.

Clusters are formed, one member is marked canonical by this precedence: (1) has a `pdf_layer` or `html` text source over `ocr`; (2) higher `char_count`; (3) earlier `issue_date`; (4) lexicographically smaller `doc_id`. Non-canonical members keep their rows and are excluded from `corpus_clean`.

Expected legitimate duplicate sources: circular text reproduced verbatim inside a Master Circular; the same document published on two regulator pages; a document re-issued with a corrigendum.

## Quality flags

| Flag | Trigger | Effect |
|---|---|---|
| `low_ocr_confidence` | mean OCR conf < threshold | excluded from `corpus_clean` |
| `short_document` | `char_count` < 200 and `doc_type` not in {`notification`} | flagged, retained |
| `high_nonascii_ratio` | > 15% non-ASCII outside a known-Devanagari document | flagged |
| `charspace_repaired` | normalisation step 4 fired | flagged, retained |
| `no_date` | `issue_date` is NULL | flagged, routed to `year=0000` |
| `table_heavy_low_text` | ≥ 3 tables and < 500 chars of prose | flagged — likely a rate schedule needing manual review |
| `extraction_partial` | page count from PDF metadata exceeds pages with extracted text | flagged |
| `duplicate_non_canonical` | set by dedup | excluded from `corpus_clean` |

## Extractor versioning

`extractor_version` is `<library>-<library_version>-<spec_revision>`, e.g. `pypdfium2-4.30.0-r1`. When any extraction rule in this document changes, `spec_revision` increments and affected documents are re-extracted into **new** `texts` rows. Old rows are retained. This lets the QA report answer "did the extraction change improve things?" with evidence rather than assertion.
