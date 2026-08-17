# 06 — Temporal Validity Specification

This is the document that distinguishes FinReg-SLM's corpus from a pile of scraped PDFs. Read it before implementing `temporal/`.

## The problem

Regulatory correctness is time-indexed. "What is the applicable rate?" has no answer without "as of when?". A ten-year corpus contains, for many questions, several mutually contradictory correct answers — each correct for its own period. Three failure modes follow if this is ignored:

1. The model states a withdrawn rule as current.
2. The retrieval layer surfaces a superseded circular above its replacement because the superseded one is longer or better-matched lexically.
3. The benchmark cannot be scored, because the grader cannot say what the right answer *was* supposed to be.

## Evidence sources for validity

Ranked by reliability. Always prefer a higher-ranked source.

| Rank | Evidence | Sets |
|---|---|---|
| 1 | RBI "Circulars Withdrawn" listing | `status = withdrawn`, `in_force_to` |
| 1 | SEBI Archive listing (Active-listing membership is NOT evidence — see correction below) | `status = superseded` or `withdrawn`, `in_force_to` |
| 2 | Explicit supersession language in a later document, with the superseded document named | `superseded_by`, `in_force_to` |
| 2 | Master Circular / Master Direction appendix of subsumed circulars | `superseded_by`, `status = superseded` |
| 3 | Statutory repeal provision (e.g. ITA 2025 repealing ITA 1961) | `status = repealed`, `in_force_to` |
| 4 | Commencement notification specifying dates for provisions | `in_force_from` at provision granularity |
| 5 | Nothing found | `status = unknown` |

**`unknown` is a legitimate terminal state.** Roughly a fifth of RBI/SEBI records and a larger share elsewhere will land there. Reporting that honestly is a research result. Guessing `in_force` to make a number look better corrupts every downstream measurement.

## Resolution algorithm

Run as a distinct stage, after extraction and citation parsing, re-runnable at any time.

```
1. Load withdrawal and archive listings. For every matched doc_id:
     status ← withdrawn | superseded
     in_force_to ← listing date if given, else NULL with metadata_gaps note
2. Load citations where relation ∈ {supersedes, withdraws}.
   For each (source S, target T) with a resolved target_doc_id:
     T.superseded_by ← S.doc_id
     T.status ← superseded  (unless already withdrawn — withdrawn wins)
     T.in_force_to ← S.issue_date
3. Load Master Circular / Master Direction subsumption tables.
   For each subsumed circular C under master M:
     C.superseded_by ← M.doc_id
     C.status ← superseded
     C.in_force_to ← M.issue_date
4. For every document with no in_force_from:
     in_force_from ← explicit effective date from document text if parsed,
                     else issue_date,
                     else NULL
     If issue_date was used as a proxy, add metadata_gaps note.
5. For every document still status = 'unknown' whose doc_id appears as a
   target of no supersession and whose issue_date is within the window:
     leave as 'unknown'. Do NOT promote to 'in_force'.
6. Detect cycles in the supersession graph. A cycle is a data error:
   log it, set both nodes to 'unknown', and add to the QA report.
```

**Step 5 is the one an implementer will be tempted to change. Do not.** A document being un-superseded is not evidence that it is in force; it is the absence of evidence.

**Correction (2026-08-04, verified against a full unbounded crawl):** this section previously claimed SEBI's Active listing is positive evidence of `in_force`. It is not. Crawled to completion, SEBI's Active endpoint (`doListing=yes`, non-archive) paginates through the entire circular history back to 1991 — it is not a curated "currently active" set, so membership in it carries no temporal signal and must not set `status`. Only genuine Archive-listing membership (rank 1 in the table above) is real evidence. A regulator publishing something *labeled* "Active" is not sufficient grounds to treat membership as positive evidence — that requires confirming the listing is actually filtered to current documents, not just named as if it were.

## The Income-tax Act regime break

**Facts.** The Income-tax Act, 2025 came into force on **2026-04-01**, replacing the Income-tax Act, 1961, which stands repealed from that date. The new Act reduces the statute from 819 sections across 23 chapters to 536 sections across 23 chapters, renumbering comprehensively while largely preserving the substantive scheme. The concept of "previous year" and "assessment year" is replaced by a single "Tax Year", applicable from 2026-27 onward. Income earned up to 2026-03-31 continues to be governed by the 1961 Act, and transitional provisions continue pending proceedings under the old Act.

**Consequences for the corpus.**

1. A ten-year corpus is roughly 96% ITA-1961 material by document count. An unweighted fine-tune will overwhelmingly learn 1961 section numbers and will confidently cite repealed provisions for present-day questions. This is the most likely single cause of a bad result in Phase 3, and it is knowable now.

2. Every direct-tax document therefore carries `statutory_regime`:

```
issue_date < 2026-04-01 and no ITA-2025 reference   → ITA_1961
issue_date >= 2026-04-01 and no ITA-1961 reference  → ITA_2025
document references both statutes                   → both
non-direct-tax document                             → NULL
```

Detection of "references ITA 2025" is by citation extraction (`target_act`), not by date alone — CBDT published transition material referencing both before the commencement date.

3. **Do not delete or downweight 1961-Act material.** It is the correct authority for any question about a period up to FY 2025-26, it governs pending proceedings, and the 1961→2025 mapping is itself a high-value reasoning task. The corpus keeps everything; Phase 2 decides sampling.

4. If CBDT has published an official 1961→2025 section correspondence table, capture it as a first-class document and parse it into a mapping table. `verify()` for the CBDT source must check for it. If no official mapping exists, record that in `known_gaps` — **do not substitute a third-party mapping table from a tax portal**, which would be both copyrighted and unverifiable.

Analogous handling applies to the Income-tax Rules: the 1962 Rules are superseded by the Rules notified under the 2025 Act with effect from 2026-04-01. Sources differ on whether the replacement instrument is styled "Income-tax Rules, 2025" or "Income-tax Rules, 2026" — capture the gazette title exactly as published and record the discrepancy in `metadata_gaps` rather than normalising it.

## DPDP phased commencement

The DPDP Act 2023 and DPDP Rules 2025 commence **provision by provision** across three dates: 2025-11-13, 2026-11-13 and 2027-05-13, per the enforcement notifications. (Some secondary sources state the 14th rather than the 13th for each; store both and flag the discrepancy.)

This means a single document has **different provisions in force on different dates**. The document-level `in_force_from` field cannot express this. Handle it as follows:

- Set the document-level `in_force_from` to the earliest commencement date.
- Add `quality_flags: phased_commencement`.
- Store the provision-level schedule as a parsed table in `tables_extracted` linked to the commencement notification.
- Record in `known_gaps` that provision-level temporal resolution is not modelled in Phase 1.

Do not fake provision-level granularity in the document schema. Phase 3 can use the parsed schedule table directly, and "as of date D, is Rule N in force?" becomes an excellent benchmark question precisely because the answer is in a table the model has to read rather than a fact it can memorise.

## RBI's November 2025 consolidation

On 2025-11-28 the RBI announced it had reorganised **9,446 circulars into 244 function-wise Master Directions across 11 categories of regulated entity**, of which 3,809 were subsumed into master circulars and 5,673 were repealed as obsolete. After the exercise, commercial banks need consult roughly 32 Master Directions.

This is the largest single supersession event in the corpus window and must be handled explicitly:

- Crawl the post-consolidation Master Directions first (source priority 2).
- Parse each Direction's statement of what it subsumes.
- Cross-check the resulting subsumption count against the withdrawn-circulars listing. A large discrepancy means the parse is wrong, not that RBI's numbers are wrong.
- Record the consolidation as a named event in the corpus card so the paper can describe it accurately.

**Caution on the 9,446 / 244 / 5,673 figures.** These come from the RBI's own announcement as reported on 2025-11-28. Do not present them in the paper as counts *you measured*. If your own subsumption parse produces different numbers, report both and explain the difference — that discrepancy is itself an interesting finding about machine-readability of regulatory consolidation.

## Query interface Phase 2 will need

Provide this as a manifest view so Phase 2 does not reimplement the logic:

```sql
CREATE VIEW v_in_force_as_of AS
SELECT doc_id, regulator, doc_type, title, issue_date,
       in_force_from, in_force_to, status, statutory_regime
FROM documents;
```

with a helper in `finreg.temporal.query`:

```python
def in_force_as_of(conn, as_of: date, regulator: str | None = None) -> list[str]
```

returning `doc_id`s where `in_force_from <= as_of` and (`in_force_to IS NULL` or `in_force_to > as_of`) and `status != 'withdrawn'`. Documents with `status = 'unknown'` are returned in a **separate list**, never silently merged into the in-force set. The caller decides what to do with uncertainty; the corpus never decides on the caller's behalf.
