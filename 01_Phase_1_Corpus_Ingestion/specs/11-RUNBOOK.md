# 11 — Runbook

## First-time setup

```bash
git clone <repo> && cd finreg-slm
uv sync
sudo apt-get install -y poppler-utils tesseract-ocr ghostscript ocrmypdf
cp config/sources.example.yaml config/sources.yaml
# edit config/sources.yaml and set contact_email — the client refuses to start without it
finreg db init
finreg sources verify
```

`finreg sources verify` must pass before any crawl. It prints, per source, the access method it selected and every structural assumption it confirmed.

## Normal operations

```bash
finreg crawl --source rbi_notifications          # one source
finreg crawl --all                               # everything enabled, in priority order
finreg crawl --all --since 2026-07-01            # incremental
finreg extract --pending                         # extract anything without a texts row
finreg resolve                                   # temporal + citations, re-runnable
finreg dedup
finreg export
finreg report
finreg qa gate                                   # the nine acceptance criteria
```

Every command is resumable. Ctrl-C or `SIGKILL` is safe at any point; re-run the same command.

## Cold crawl

Expect ~72 hours at default politeness. Run it in `tmux` or as a systemd unit, not in a terminal you will close.

```bash
tmux new -s finreg
finreg crawl --all 2>&1 | tee reports/logs/cold-$(date +%F).log
```

Start it outside IST business hours where practical. Monitor with:

```bash
finreg status                                    # live per-source progress from the manifest
watch -n 300 'finreg status --brief'
```

## Refresh cadence

| Cadence | Command | Purpose |
|---|---|---|
| Weekly | `finreg crawl --all --since <last run date>` | New documents |
| Weekly | `finreg sources verify` | Catch site changes before they cause a silent zero-document crawl |
| Monthly | `finreg crawl --recheck-sample 0.02` | Re-fetch 2% of existing documents to detect silent revisions |
| Monthly | `finreg resolve && finreg export && finreg report` | Refresh temporal status and views |
| Before any Phase 2 training run | `finreg qa gate` | Never train on a corpus that has not passed the gate |

## Incident procedures

### A source returns zero documents

Almost always a site change, not an outage.

1. `finreg sources verify --source <name>` — read which assertion failed.
2. Fetch the listing page manually and compare with the committed fixture.
3. Fix the parser, **update doc 03 with the corrected pattern and today's date**, capture a new fixture, add a test.
4. Re-run the crawl for that source only.

Never work around a parse failure by loosening the parser until something matches. A parser that matches anything will silently produce garbage.

### Rate limiting / 429s

The client already halves the host rate on repeated 429s and logs it. If they persist:

1. Stop the crawl for that host.
2. Wait at least an hour.
3. Raise `min_interval_seconds` for that host to 5.0 in config.
4. Resume.

If a host blocks the crawler outright, **stop and report it** (invariant: no proxy rotation, no UA rotation). Email the site's listed contact — for RBI, the helpdesk address in the site footer — explain the academic purpose, and ask. Record the outcome in `reports/`.

**Current known exception:** `rbidocs.rbi.org.in` (RBI's PDF host) resets the connection for the honest UA; a scoped, logged override is configured in `config/sources.yaml`'s `identity_overrides` for that host only — see `07-LEGAL-AND-CRAWL-ETHICS.md` "Identification exceptions" for the full justification. Still email RBI's webmaster to request allowlisting; remove the override once that lands.

### Disk pressure

```bash
finreg status --storage
```

Blobs are never deleted by the pipeline. If storage is tight, move `data/raw/` to external storage and symlink; the manifest stores relative paths under `data/raw/` so the move is transparent. Do not prune blobs — provenance depends on them.

### Manifest corruption

WAL mode plus transactional writes make this unlikely, but:

```bash
sqlite3 data/manifest.db "PRAGMA integrity_check;"
```

If it fails, restore the most recent snapshot from `data/export/manifest-snapshots/` and re-run `finreg crawl --all`. Idempotency means re-crawling costs time, not correctness. Take a snapshot before every export:

```bash
finreg db snapshot
```

### Extraction regression

Symptom: mean chars/document for a source drops sharply between reports.

1. `finreg qa regress` — runs the frozen 100-document regression corpus and diffs.
2. Identify the change that caused it (extraction changes bump `extractor_version`, so `texts` rows carry the culprit).
3. Fix, increment `spec_revision`, re-extract the affected subset. Old `texts` rows are retained, so before/after is directly comparable.

## Handover state

At the end of Phase 1, the following must exist and be committed:

- `config/sources.yaml` with tuned thresholds and the evidence for each tuning recorded in `reports/phase1-summary.md`.
- `reports/phase1-summary.md` — generated numbers, not typed ones.
- `reports/audit-<date>.md` — the manual audit worksheet with its seed.
- `data/export/corpus_card.json` — with a populated `known_gaps`.
- A git tag `phase1-freeze` on the commit that produced the export.

Phase 2 starts from the tag and the corpus card, not from a conversation.

## A note for whoever runs this

The crawl is slow on purpose. The politeness settings in this project are not a technical constraint to be optimised away — they are the terms on which a student project gets to take data from public infrastructure. If you find yourself editing `min_interval_seconds` downward to make a deadline, the deadline is the thing that should move.
