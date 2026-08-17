from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def _per_source_counts(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT source_name, COUNT(*) AS n FROM documents GROUP BY source_name ORDER BY source_name"
    ).fetchall()


def _coverage_histogram(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT regulator,
               CAST(strftime('%Y', issue_date) AS INTEGER) AS year,
               ((CAST(strftime('%m', issue_date) AS INTEGER) - 1) / 3) + 1 AS quarter,
               COUNT(*) AS n
        FROM documents
        WHERE issue_date IS NOT NULL
        GROUP BY regulator, year, quarter
        ORDER BY regulator, year, quarter
        """
    ).fetchall()


def _failure_breakdown(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT reason_code, COUNT(*) AS n FROM fetch_failures GROUP BY reason_code ORDER BY n DESC"
    ).fetchall()


def _ocr_share(conn: sqlite3.Connection) -> tuple[int, int]:
    ocr = conn.execute("SELECT COUNT(*) FROM texts WHERE text_source = 'ocr'").fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM texts").fetchone()[0]
    return ocr, total


def _status_distribution(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT status, COUNT(*) AS n FROM documents GROUP BY status ORDER BY n DESC"
    ).fetchall()


def _duplicate_clusters(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(DISTINCT cluster_id) FROM duplicates").fetchone()[0]


def _top_unresolved_failures(conn: sqlite3.Connection, limit: int = 50) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT source_url, reason_code, detail, attempts, last_seen
        FROM fetch_failures WHERE resolved = 0
        ORDER BY attempts DESC, last_seen DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()


def generate_markdown(conn: sqlite3.Connection) -> str:
    lines: list[str] = []
    lines.append("# FinReg-SLM Corpus QA Report")
    lines.append(f"\nGenerated: {datetime.now(timezone.utc).isoformat()}")
    lines.append("\nEvery number below is produced by a live manifest query in `qa/report.py`; "
                  "none are hardcoded.")

    lines.append("\n## Per-source counts")
    lines.append("\n| Source | Documents |\n|---|---|")
    for row in _per_source_counts(conn):
        lines.append(f"| {row['source_name']} | {row['n']} |")

    lines.append("\n## Coverage by regulator/quarter")
    lines.append("\n| Regulator | Year | Quarter | Documents |\n|---|---|---|---|")
    for row in _coverage_histogram(conn):
        lines.append(f"| {row['regulator']} | {row['year']} | Q{row['quarter']} | {row['n']} |")

    lines.append("\n## Fetch failure breakdown")
    lines.append("\n| Reason code | Count |\n|---|---|")
    for row in _failure_breakdown(conn):
        lines.append(f"| {row['reason_code']} | {row['n']} |")

    ocr, total = _ocr_share(conn)
    ocr_pct = (ocr / total * 100) if total else 0.0
    lines.append(f"\n## OCR share\n\n{ocr} of {total} extracted documents ({ocr_pct:.1f}%) used OCR.")

    lines.append("\n## Status distribution")
    lines.append("\n| Status | Count |\n|---|---|")
    for row in _status_distribution(conn):
        lines.append(f"| {row['status']} | {row['n']} |")

    lines.append(f"\n## Duplicate clusters\n\n{_duplicate_clusters(conn)} clusters found.")

    lines.append("\n## Top unresolved failures (up to 50)")
    lines.append("\n| URL | Reason | Attempts | Last seen |\n|---|---|---|---|")
    for row in _top_unresolved_failures(conn):
        lines.append(f"| {row['source_url']} | {row['reason_code']} | {row['attempts']} | {row['last_seen']} |")

    return "\n".join(lines)


def generate_html(markdown_text: str) -> str:
    escaped = markdown_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"<!DOCTYPE html>\n<html><head><meta charset='utf-8'><title>FinReg-SLM QA Report</title></head>\n<body><pre>{escaped}</pre></body></html>\n"
