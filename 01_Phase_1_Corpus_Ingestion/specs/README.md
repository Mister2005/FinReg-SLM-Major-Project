# FinReg-SLM — Phase 1 Documentation Set

Phase 1 is **corpus acquisition, extraction and temporal indexing**. No model training happens in this phase. The deliverable of Phase 1 is a reproducible, licensed, version-aware corpus of Indian financial and regulatory primary sources spanning **2016-04-01 to the present**, plus the tooling to refresh it.

This set is written to be handed to an autonomous coding agent (Claude Code) with no further clarification required.

## Read order

| # | Document | Purpose |
|---|---|---|
| — | [`AGENTS.md`](AGENTS.md) | Non-negotiable engineering invariants. Read first, obey always. |
| 00 | [`docs/00-PROJECT-BRIEF.md`](docs/00-PROJECT-BRIEF.md) | What FinReg-SLM is, why Phase 1 exists, what is out of scope. |
| 01 | [`docs/01-PRD-PHASE1.md`](docs/01-PRD-PHASE1.md) | Requirements, acceptance criteria, exit gate. |
| 02 | [`docs/02-TRD-PHASE1.md`](docs/02-TRD-PHASE1.md) | Architecture, module layout, technology decisions. |
| 03 | [`docs/03-DATA-SOURCES.md`](docs/03-DATA-SOURCES.md) | Every source, verified URL pattern, access mechanism, expected volume. |
| 04 | [`docs/04-DATA-MODEL.md`](docs/04-DATA-MODEL.md) | SQLite DDL, blob store layout, Parquet export schema. |
| 05 | [`docs/05-EXTRACTION-SPEC.md`](docs/05-EXTRACTION-SPEC.md) | PDF/HTML → text, OCR fallback, tables, quality gates, dedup. |
| 06 | [`docs/06-TEMPORAL-VALIDITY-SPEC.md`](docs/06-TEMPORAL-VALIDITY-SPEC.md) | Supersession, withdrawal, the ITA-1961 → ITA-2025 regime break. |
| 07 | [`docs/07-LEGAL-AND-CRAWL-ETHICS.md`](docs/07-LEGAL-AND-CRAWL-ETHICS.md) | Copyright position, GODL attribution, rate limits, robots.txt. |
| 08 | [`docs/08-IMPLEMENTATION-PLAN.md`](docs/08-IMPLEMENTATION-PLAN.md) | Five milestones with hard go/no-go gates. |
| 09 | [`docs/09-TICKETS.md`](docs/09-TICKETS.md) | 42 dependency-ordered tickets with assertion-style acceptance criteria. |
| 10 | [`docs/10-TESTING-AND-QA.md`](docs/10-TESTING-AND-QA.md) | Test taxonomy, corpus quality metrics, manual audit protocol. |
| 11 | [`docs/11-RUNBOOK.md`](docs/11-RUNBOOK.md) | Commands, resume, incident procedures, refresh cadence. |

## Repository layout the agent must create

```
finreg-slm/
├── AGENTS.md
├── docs/
├── pyproject.toml
├── config/
│   ├── sources.yaml
│   └── logging.yaml
├── src/finreg/
│   ├── __init__.py
│   ├── cli.py
│   ├── http/          fetch, throttle, robots, cache
│   ├── sources/       one module per regulator
│   ├── extract/       pdf, html, ocr, tables
│   ├── normalize/     text cleanup, citation parsing
│   ├── temporal/      supersession graph, regime tagging
│   ├── store/         sqlite manifest, blob store, parquet export
│   └── qa/            quality gates, reports
├── tests/
├── data/              gitignored
│   ├── raw/           content-addressed blobs
│   ├── work/          intermediate
│   └── export/        parquet + manifest snapshots
└── reports/
```

## Phase 1 exit gate (one sentence)

Phase 1 is complete when `finreg export` produces a Parquet corpus in which **every record carries a resolvable source URL, a retrieval timestamp, a content hash, an in-force date range, and a licence tag**, and a 200-document stratified manual audit shows **≥ 95% extraction fidelity** and **zero records whose source URL does not resolve to the claimed document**.
