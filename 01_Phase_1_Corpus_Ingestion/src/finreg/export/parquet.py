from __future__ import annotations

import json
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

EXPORT_SCHEMA = pa.schema(
    [
        ("doc_id", pa.string()),
        ("regulator", pa.string()),
        ("doc_type", pa.string()),
        ("doc_number", pa.string()),
        ("title", pa.string()),
        ("issue_date", pa.date32()),
        ("year", pa.int16()),
        ("department", pa.string()),
        ("text", pa.string()),
        ("text_source", pa.string()),
        ("char_count", pa.int32()),
        ("status", pa.string()),
        ("in_force_from", pa.date32()),
        ("in_force_to", pa.date32()),
        ("superseded_by", pa.string()),
        ("statutory_regime", pa.string()),
        ("source_url", pa.string()),
        ("pdf_url", pa.string()),
        ("sha256", pa.string()),
        ("retrieved_at", pa.timestamp("us", tz="UTC")),
        ("licence", pa.string()),
        ("attribution", pa.string()),
        ("quality_flags", pa.list_(pa.string())),
        ("is_duplicate", pa.bool_()),
    ]
)


def _row_year(issue_date: str | None) -> int:
    if issue_date is None:
        return 0
    return int(issue_date[:4])


def _fetch_export_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    orig_factory = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT d.doc_id, d.regulator, d.doc_type, d.doc_number, d.title, d.issue_date,
                   d.department, d.status, d.in_force_from, d.in_force_to, d.superseded_by,
                   d.statutory_regime, d.source_url, d.pdf_url, d.retrieved_at, d.licence,
                   d.attribution, t.body AS text, t.text_source, t.char_count,
                   COALESCE(t.blob_sha256, d.html_sha256, d.pdf_sha256) AS sha256
            FROM documents d
            JOIN texts t ON t.doc_id = d.doc_id
            ORDER BY d.doc_id
            """
        ).fetchall()

        result = []
        for row in rows:
            flags = [
                r["flag"]
                for r in conn.execute(
                    "SELECT flag FROM quality_flags WHERE doc_id = ? ORDER BY flag", (row["doc_id"],)
                ).fetchall()
            ]
            dup_row = conn.execute(
                "SELECT is_canonical FROM duplicates WHERE doc_id = ?", (row["doc_id"],)
            ).fetchone()
            is_duplicate = bool(dup_row) and dup_row["is_canonical"] == 0

            result.append(
                {
                    "doc_id": row["doc_id"],
                    "regulator": row["regulator"],
                    "doc_type": row["doc_type"],
                    "doc_number": row["doc_number"],
                    "title": row["title"],
                    "issue_date": date.fromisoformat(row["issue_date"]) if row["issue_date"] else None,
                    "year": _row_year(row["issue_date"]),
                    "department": row["department"],
                    "text": row["text"],
                    "text_source": row["text_source"],
                    "char_count": row["char_count"],
                    "status": row["status"],
                    "in_force_from": date.fromisoformat(row["in_force_from"]) if row["in_force_from"] else None,
                    "in_force_to": date.fromisoformat(row["in_force_to"]) if row["in_force_to"] else None,
                    "superseded_by": row["superseded_by"],
                    "statutory_regime": row["statutory_regime"],
                    "source_url": row["source_url"],
                    "pdf_url": row["pdf_url"],
                    "sha256": row["sha256"],
                    "retrieved_at": datetime.fromisoformat(row["retrieved_at"]),
                    "licence": row["licence"],
                    "attribution": row["attribution"],
                    "quality_flags": flags,
                    "is_duplicate": is_duplicate,
                }
            )
        return result
    finally:
        conn.row_factory = orig_factory


def _is_clean(row: dict) -> bool:
    return not row["is_duplicate"] and not row["quality_flags"] and row["licence"] != "unverified"


def _write_partitioned(rows: list[dict], out_dir: Path) -> None:
    if out_dir.exists():
        for f in out_dir.rglob("*.parquet"):
            f.unlink()

    by_partition: dict[tuple[str, int], list[dict]] = {}
    for row in rows:
        key = (row["regulator"], row["year"])
        by_partition.setdefault(key, []).append(row)

    for (regulator, year), partition_rows in sorted(by_partition.items()):
        columns = {field.name: [r[field.name] for r in partition_rows] for field in EXPORT_SCHEMA}
        table = pa.table(columns, schema=EXPORT_SCHEMA)
        partition_dir = out_dir / f"regulator={regulator}" / f"year={year:04d}"
        partition_dir.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, partition_dir / "part-0000.parquet", compression="zstd")


def _git_commit(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


@dataclass(frozen=True)
class ExportResult:
    corpus_count: int
    corpus_clean_count: int
    corpus_in_force_count: int
    corpus_card_path: Path


def export(conn: sqlite3.Connection, export_dir: Path, repo_root: Path, config_sha256: str, window_start: str) -> ExportResult:
    from finreg.temporal.query import in_force_as_of

    all_rows = _fetch_export_rows(conn)
    clean_rows = [r for r in all_rows if _is_clean(r)]
    in_force_ids, _ = in_force_as_of(conn, date.today())
    in_force_row_ids = set(in_force_ids)
    in_force_rows = [r for r in clean_rows if r["doc_id"] in in_force_row_ids]

    _write_partitioned(all_rows, export_dir / "corpus")
    _write_partitioned(clean_rows, export_dir / "corpus_clean")
    _write_partitioned(in_force_rows, export_dir / "corpus_in_force")

    counts_by_regulator: dict[str, int] = {}
    counts_by_doc_type: dict[str, int] = {}
    counts_by_status: dict[str, int] = {}
    counts_by_text_source: dict[str, int] = {}
    counts_by_licence: dict[str, int] = {}
    for row in all_rows:
        counts_by_regulator[row["regulator"]] = counts_by_regulator.get(row["regulator"], 0) + 1
        counts_by_doc_type[row["doc_type"]] = counts_by_doc_type.get(row["doc_type"], 0) + 1
        counts_by_status[row["status"]] = counts_by_status.get(row["status"], 0) + 1
        if row["text_source"]:
            counts_by_text_source[row["text_source"]] = counts_by_text_source.get(row["text_source"], 0) + 1
        counts_by_licence[row["licence"]] = counts_by_licence.get(row["licence"], 0) + 1

    known_gaps: list[str] = []
    gap_rows = conn.execute(
        "SELECT DISTINCT metadata_gaps FROM documents WHERE metadata_gaps IS NOT NULL"
    ).fetchall()
    seen_gaps: set[str] = set()
    for gr in gap_rows:
        for gap in json.loads(gr["metadata_gaps"]):
            if gap not in seen_gaps:
                seen_gaps.add(gap)
                known_gaps.append(gap)

    ocr_count = sum(1 for r in all_rows if r["text_source"] == "ocr")
    flagged_count = sum(1 for r in all_rows if r["quality_flags"])
    duplicate_clusters = conn.execute("SELECT COUNT(DISTINCT cluster_id) FROM duplicates").fetchone()[0]
    failure_count = conn.execute("SELECT COUNT(*) FROM fetch_failures WHERE resolved = 0").fetchone()[0]

    corpus_card = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(repo_root),
        "config_sha256": config_sha256,
        "window": {"start": window_start, "end": date.today().isoformat()},
        "counts": {
            "by_regulator": counts_by_regulator,
            "by_doc_type": counts_by_doc_type,
            "by_status": counts_by_status,
            "by_text_source": counts_by_text_source,
            "by_licence": counts_by_licence,
        },
        "coverage": {"missing_quarters": []},
        "quality": {
            "ocr_share": ocr_count / len(all_rows) if all_rows else 0.0,
            "flagged_share": flagged_count / len(all_rows) if all_rows else 0.0,
            "duplicate_clusters": duplicate_clusters,
            "extraction_failure_count": failure_count,
        },
        "known_gaps": known_gaps,
        "source_access_methods": {},
    }

    card_path = export_dir / "corpus_card.json"
    export_dir.mkdir(parents=True, exist_ok=True)
    card_path.write_text(json.dumps(corpus_card, indent=2, sort_keys=True), encoding="utf-8")

    return ExportResult(
        corpus_count=len(all_rows),
        corpus_clean_count=len(clean_rows),
        corpus_in_force_count=len(in_force_rows),
        corpus_card_path=card_path,
    )
