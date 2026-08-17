from __future__ import annotations

import random
import sqlite3
from datetime import date
from pathlib import Path

TARGET_SAMPLE_SIZE = 200
MIN_PER_REGULATOR = 15
FORCE_OCR_COUNT = 20
FORCE_FLAGGED_COUNT = 20
FORCE_LOW_CHAR_COUNT = 10
FORCE_TABLES_COUNT = 10


def _all_doc_ids(conn: sqlite3.Connection) -> list[str]:
    return [r["doc_id"] for r in conn.execute("SELECT doc_id FROM documents").fetchall()]


def _proportional_stratified_sample(conn: sqlite3.Connection, rng: random.Random, target_size: int) -> list[str]:
    regulators = [r["regulator"] for r in conn.execute("SELECT DISTINCT regulator FROM documents").fetchall()]
    total = len(_all_doc_ids(conn))
    if total == 0:
        return []

    selected: list[str] = []
    for regulator in regulators:
        doc_ids = [
            r["doc_id"]
            for r in conn.execute("SELECT doc_id FROM documents WHERE regulator = ?", (regulator,)).fetchall()
        ]
        share = len(doc_ids) / total
        quota = max(MIN_PER_REGULATOR, round(share * target_size))
        quota = min(quota, len(doc_ids))
        selected.extend(rng.sample(doc_ids, quota))
    return selected


def _force_include(conn: sqlite3.Connection) -> dict[str, list[str]]:
    ocr_docs = [
        r["doc_id"]
        for r in conn.execute(
            "SELECT doc_id FROM texts WHERE text_source = 'ocr' LIMIT ?", (FORCE_OCR_COUNT,)
        ).fetchall()
    ]
    flagged_docs = [
        r["doc_id"]
        for r in conn.execute(
            "SELECT DISTINCT doc_id FROM quality_flags LIMIT ?", (FORCE_FLAGGED_COUNT,)
        ).fetchall()
    ]
    low_char_docs = [
        r["doc_id"]
        for r in conn.execute(
            "SELECT doc_id FROM texts ORDER BY char_count ASC LIMIT ?", (FORCE_LOW_CHAR_COUNT,)
        ).fetchall()
    ]
    table_docs = [
        r["doc_id"]
        for r in conn.execute(
            "SELECT DISTINCT doc_id FROM tables_extracted LIMIT ?", (FORCE_TABLES_COUNT,)
        ).fetchall()
    ]
    return {
        "ocr": ocr_docs,
        "flagged": flagged_docs,
        "low_char_count": low_char_docs,
        "tables": table_docs,
    }


def generate_sample(conn: sqlite3.Connection, seed: int, target_size: int = TARGET_SAMPLE_SIZE) -> list[str]:
    """Deterministic given the seed. Combines a proportional-by-regulator
    stratified sample with the doc-10 force-include categories, deduplicated,
    capped at target_size (or fewer if the corpus doesn't have that many
    documents yet — an honest, smaller worksheet, not padded)."""
    rng = random.Random(seed)
    stratified = _proportional_stratified_sample(conn, rng, target_size)
    forced = _force_include(conn)

    combined: list[str] = []
    seen: set[str] = set()
    for doc_id in [*stratified, *forced["ocr"], *forced["flagged"], *forced["low_char_count"], *forced["tables"]]:
        if doc_id not in seen:
            seen.add(doc_id)
            combined.append(doc_id)

    return combined[:target_size] if len(combined) > target_size else combined


def write_audit_worksheet(conn: sqlite3.Connection, seed: int, out_path: Path) -> int:
    doc_ids = generate_sample(conn, seed)

    lines = [
        "# Manual Audit Worksheet",
        f"\nSeed: {seed}",
        f"Generated: {date.today().isoformat()}",
        f"Sample size: {len(doc_ids)}",
        "\nPer doc 10-TESTING-AND-QA.md's protocol, fill in each row after opening the source_url:",
        "resolves (yes/no/redirected), complete (yes/partial/no), ordered (yes/no), "
        "numbers_intact (yes/no+detail), metadata_correct (yes/no+field), boilerplate_removed (yes/no).",
        "\n| doc_id | source_url | resolves | complete | ordered | numbers_intact | metadata_correct | boilerplate_removed |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for doc_id in doc_ids:
        row = conn.execute("SELECT source_url FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
        source_url = row["source_url"] if row else ""
        lines.append(f"| {doc_id} | {source_url} | | | | | | |")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return len(doc_ids)
