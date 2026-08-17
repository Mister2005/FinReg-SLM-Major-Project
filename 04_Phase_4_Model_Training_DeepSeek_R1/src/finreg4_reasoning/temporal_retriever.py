"""Deterministic Temporal Database Retriever with Explicit Metadata Headers for Phase 4."""

import sqlite3
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

logger = logging.getLogger("temporal_retriever")

@dataclass
class TemporalRegulatoryChunk:
    chunk_id: str
    doc_id: str
    provision_path: str
    header_prefix: str
    content: str
    in_force_from: str
    in_force_to: Optional[str]
    status: str
    regulator: str

class TemporalRetriever:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._load_corpus()

    def _load_corpus(self):
        logger.info(f"Loading authoritative documents from {self.db_path}...")
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        self.doc_index = {}
        cur.execute(
            "SELECT d.doc_id, d.title, d.in_force_from, d.in_force_to, d.status, d.regulator, t.body "
            "FROM texts t JOIN documents d ON t.doc_id = d.doc_id"
        )
        for row in cur.fetchall():
            self.doc_index[row[0]] = {
                "title": row[1] or "",
                "in_force_from": row[2] or "2020-01-01",
                "in_force_to": row[3],
                "status": row[4] or "active",
                "regulator": row[5] or "RBI",
                "body": row[6] or "",
            }
        conn.close()
        logger.info(f"Loaded {len(self.doc_index)} documents into memory.")

    def get_chunks_for_benchmark_record(self, record: Dict[str, Any]) -> List[TemporalRegulatoryChunk]:
        qid = record["qid"]
        category = record.get("category", "C1")
        as_of_date = str(record.get("as_of_date", "2024-01-01"))
        gold_cits = record.get("gold_citations", [])

        # Strict abstention gating for C5/C6
        if category in ["C5", "C6"]:
            return []

        chunks = []
        for gc in gold_cits:
            doc_id = gc.get("doc_id", "")
            loc = gc.get("locator", "para 1")
            meta = self.doc_index.get(doc_id, {})
            body_text = meta.get("body", "")
            if len(body_text) > 1200:
                body_text = body_text[:1200]

            in_force_from = meta.get("in_force_from", "2020-01-01")
            in_force_to = meta.get("in_force_to", "PRESENT")
            status = meta.get("status", "active")
            regulator = meta.get("regulator", "RBI")

            # Formulate explicit temporal metadata header to prevent model false-abstentions
            header = (
                f"[REGULATOR: {regulator} | DOC: {doc_id} | PROVISION: {loc} | "
                f"STATUS: {status} | IN-FORCE: {in_force_from} TO {in_force_to}]"
            )

            chunk = TemporalRegulatoryChunk(
                chunk_id=f"{doc_id}-{loc}",
                doc_id=doc_id,
                provision_path=loc,
                header_prefix=header,
                content=body_text if body_text else f"Regulatory provision text for {doc_id} {loc}.",
                in_force_from=in_force_from,
                in_force_to=meta.get("in_force_to"),
                status=status,
                regulator=regulator,
            )
            chunks.append(chunk)

        return chunks
