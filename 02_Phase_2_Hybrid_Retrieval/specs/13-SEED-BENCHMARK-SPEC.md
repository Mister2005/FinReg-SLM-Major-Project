# 13 — Seed Benchmark Specification

300 questions, hand-authored from the Phase 1 corpus, human-verified, frozen before any model runs. This is the measuring instrument for the entire phase; if it is bad, nothing downstream means anything.

## Why 300

Enough to detect a difference of roughly 8–10 percentage points between two arms with reasonable confidence, and small enough that one person can author and verify it in a week. It is explicitly a *seed* benchmark: if Phase 3 proceeds, it grows.

Be honest in the write-up about what 300 cannot do. It cannot support fine-grained per-regulator claims (roughly 50 questions each), and it cannot detect a 3-point difference. `docs/16` sets out exactly which claims the sample size supports.

## Category taxonomy

| # | Category | n | What it tests |
|---|---|---|---|
| C1 | Direct lookup | 60 | Single provision, single document. "What is the threshold under X?" |
| C2 | Multi-document synthesis | 50 | Answer requires combining a Master Direction with an amending circular, or a statute with a clarifying circular |
| C3 | **As-of-date reasoning** | 60 | Same question, different dates, different correct answers |
| C4 | Computation | 40 | TDS/GST/threshold arithmetic grounded in a cited provision |
| C5 | **False premise** | 40 | Question presupposes a provision, section number or rule that does not exist |
| C6 | **Unanswerable from corpus** | 50 | Genuinely outside the corpus; correct behaviour is abstention with an explanation |

C3, C5 and C6 are weighted heavily on purpose. C3 is our novelty axis. C5 targets the documented failure where models accept false legal premises (Dahl et al. 2024). C6 makes abstention measurable, which per invariant E10 is a first-class behaviour in this domain, not a cop-out.

## Regulator distribution

Roughly proportional to corpus size with a floor, so no regulator is unmeasurable: RBI 90, SEBI 70, Income-tax 70, GST 50, DPDP 20. Every regulator appears in every category where it makes sense.

## The as-of-date design (C3)

C3 questions come in **paired or tripled variants** sharing a stem and differing only in the as-of date:

```
stem:  "What is the applicable provision governing <X>?"
v1:    as_of = 2024-06-01   → gold cites the pre-consolidation circular
v2:    as_of = 2026-06-01   → gold cites the current Master Direction
```

Score variants independently, and additionally report a **consistency metric**: the fraction of stems where the system got *all* variants right. A system that answers one variant correctly by luck and contradicts itself across dates is not usable, and only the paired metric reveals that.

Three date anchors give natural material:
- **1 April 2026** — Income-tax Act 2025 in force, 1961 Act repealed, sections renumbered
- **November 2025** — RBI consolidation into Master Directions
- **13 Nov 2025 / 13 Nov 2026 / 13 May 2027** — DPDP phased commencement, where "is this rule in force?" changes answer by date

## Question record schema

```json
{
  "qid": "C3-RBI-014",
  "category": "C3",
  "regulator": "RBI",
  "question": "...",
  "as_of_date": "2026-06-01",
  "stem_id": "C3-RBI-014-stem",
  "gold_answer": "...",
  "gold_citations": [{"doc_id": "...", "locator": "para 4.2"}],
  "answerable": true,
  "false_premise": false,
  "computation": {"expected_value": null, "tolerance": null},
  "difficulty": "medium",
  "author": "...",
  "verified_by": "...",
  "verification_date": "2026-08-20",
  "notes": "..."
}
```

`gold_citations` uses Phase 1 `doc_id`s, so citation scoring joins directly against the manifest. A question whose gold citation does not resolve to a corpus document is invalid and cannot be frozen.

## Authoring protocol

1. **Source-first, never model-first.** Open a corpus document, read a provision, write a question it answers. Never ask a model to generate questions from a document — that biases the benchmark toward what models find easy and risks importing model errors into the gold answers.
2. **Gold answer written from the source text**, with the citation recorded at authoring time, not reconstructed later.
3. **C5 false premises must be plausible.** A section number adjacent to real ones, a rule that sounds like it should exist. An obviously absurd premise tests nothing.
4. **C6 questions must be genuinely unanswerable from the corpus**, not merely hard. State-level rules, a regulator we did not ingest, or a question requiring facts about a specific company are good C6 material.
5. Record every question's authoring date and source document.

## Verification and agreement

Every question is checked by a **second person** against the cited source. Where a second annotator is unavailable, the author re-verifies after a minimum 48-hour gap, and this weaker protocol is disclosed in the write-up rather than hidden.

Verification checks: is the gold answer correct and complete; does the citation resolve and support it; is the question unambiguous; is `answerable` correctly labelled; for C3, is the as-of date genuinely decisive.

**Report Cohen's κ** on a 60-question overlap subsample for the binary judgements (`answerable`, `false_premise`) and on a 3-point correctness scale for gold-answer agreement. Target κ ≥ 0.7. Below 0.6 means the questions are ambiguous — revise the ambiguous ones and re-verify before freezing, and report that this happened.

## Where domain expertise is needed

Some questions — especially C4 computation and C2 synthesis — need someone who actually knows Indian tax or banking regulation. Options in order of preference: a faculty member with commerce/law background; a chartered accountant contact; a final-year commerce student. If no expert is available, **restrict C4 to computations that are fully determined by an explicitly cited rate table** so correctness is checkable from the text alone, and state this limitation in the write-up.

Do not fabricate expertise. A benchmark with 40 shallow-but-correct computation questions is worth more than 40 deep ones with wrong gold answers.

## Freeze procedure

1. All 300 questions authored and verified.
2. Validator passes: schema valid, all `doc_id`s resolve, no duplicate stems, category counts match, all citations support their gold answers.
3. Compute and record the SHA-256 of the file.
4. Commit and tag `bench-v1`.
5. **Record the set of `doc_id`s used in any gold citation.** This set is excluded from SFT generation (invariant E7) and the exclusion is asserted in a test.

After this point, `docs/AGENTS-PHASE2.md` invariant E1 applies absolutely.
