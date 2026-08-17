from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pdfplumber

_LATTICE_SETTINGS = {"vertical_strategy": "lines", "horizontal_strategy": "lines"}
_STREAM_SETTINGS = {"vertical_strategy": "text", "horizontal_strategy": "text"}
_MIN_ROWS = 2
_MIN_COLS = 2
# Lattice tables have structural evidence (ruling lines) behind them, so a
# moderate fill-density is enough to trust them. Stream tables are inferred
# purely from text alignment and routinely misfire on justified prose
# (observed: a real RBI circular's body text scored 0.60 density as a fake
# 45-row "table"), so they need a much higher bar before being accepted.
_MIN_DENSITY_LATTICE = 0.5
_MIN_DENSITY_STREAM = 0.75


@dataclass(frozen=True)
class ExtractedTable:
    page_number: int
    rows: list[list[str]]
    n_rows: int
    n_cols: int
    strategy: str


def _cell_text(cell: str | None) -> str:
    return (cell or "").strip()


def _non_empty_density(rows: list[list[str | None]]) -> float:
    total = sum(len(row) for row in rows)
    if total == 0:
        return 0.0
    non_empty = sum(1 for row in rows for cell in row if cell and cell.strip())
    return non_empty / total


def _is_well_formed(rows: list[list[str | None]]) -> bool:
    if len(rows) < _MIN_ROWS:
        return False
    if not rows[0] or len(rows[0]) < _MIN_COLS:
        return False
    return True


def _min_density_for(strategy: str) -> float:
    return _MIN_DENSITY_LATTICE if strategy == "lattice" else _MIN_DENSITY_STREAM


def _best_table(candidates: list[tuple[str, list[list[str | None]]]]) -> tuple[str, list[list[str | None]]] | None:
    acceptable = [
        (strategy, rows)
        for strategy, rows in candidates
        if _is_well_formed(rows) and _non_empty_density(rows) >= _min_density_for(strategy)
    ]
    if not acceptable:
        return None
    return max(acceptable, key=lambda item: _non_empty_density(item[1]))


def extract_tables(pdf_path: Path) -> list[ExtractedTable]:
    results: list[ExtractedTable] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages):
            candidates: list[tuple[str, list[list[str | None]]]] = []
            for strategy, settings in (("lattice", _LATTICE_SETTINGS), ("stream", _STREAM_SETTINGS)):
                try:
                    tables = page.extract_tables(table_settings=settings)
                except Exception:  # noqa: BLE001
                    tables = []
                for table in tables:
                    candidates.append((strategy, table))

            best = _best_table(candidates)
            if best is None:
                continue
            strategy, rows = best
            cleaned_rows = [[_cell_text(cell) for cell in row] for row in rows]
            results.append(
                ExtractedTable(
                    page_number=page_index + 1,
                    rows=cleaned_rows,
                    n_rows=len(cleaned_rows),
                    n_cols=len(cleaned_rows[0]) if cleaned_rows else 0,
                    strategy=strategy,
                )
            )
    return results


def serialize_table(table: ExtractedTable) -> str:
    """Pipe-delimited serialisation with the header repeated into every data
    row (`Header: value | Header: value`), so each line is self-describing
    when it lands in the middle of a document's linear text — a reader (or
    a retrieval chunk) never has to scroll back up to the header row to know
    what a cell means."""
    if not table.rows:
        return ""
    header = [h or f"col_{i}" for i, h in enumerate(table.rows[0])]
    lines = [" | ".join(header)]
    for row in table.rows[1:]:
        cells = [f"{header[i]}: {cell}" for i, cell in enumerate(row) if i < len(header)]
        lines.append(" | ".join(cells))
    return "\n".join(lines)
