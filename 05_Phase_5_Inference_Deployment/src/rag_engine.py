"""Temporal & Lexical RAG Engine for Indian Regulatory Compliance.

Connects to SQLite manifest.db, pre-filters circulars by temporal validity as-of date,
retrieves relevant provisions, and constructs strictly grounded prompt contexts.
"""

import sqlite3
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("rag_engine")

ROOT_DIR = Path(r"c:\Users\Varun\Desktop\Main\Sem 7\Major Project")
MANIFEST_DB = ROOT_DIR / "Phase 1" / "data" / "manifest.db"

class RegulatoryRAGEngine:
    def __init__(self, db_path: Path = MANIFEST_DB):
        self.db_path = db_path
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found at {self.db_path}")
        self._warmup_cache()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _warmup_cache(self):
        logger.info(f"Connecting to regulatory manifest at {self.db_path}...")
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM documents")
            doc_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM texts")
            text_count = cur.fetchone()[0]
        logger.info(f"RAG Engine Initialized: {doc_count} documents, {text_count} text bodies loaded in SQLite.")

    def get_document_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Fetch complete document metadata and text body with flexible matching."""
        doc_id_clean = doc_id.strip()
        with self._get_connection() as conn:
            cur = conn.cursor()
            # 1. Exact match (case-insensitive)
            cur.execute(
                """
                SELECT d.doc_id, d.title, d.regulator, d.in_force_from, d.in_force_to, 
                       d.status, d.source_url, d.pdf_url, t.body
                FROM documents d
                LEFT JOIN texts t ON d.doc_id = t.doc_id
                WHERE LOWER(d.doc_id) = LOWER(?)
                """,
                (doc_id_clean,)
            )
            row = cur.fetchone()
            if row:
                return dict(row)

            # 2. Substring / LIKE match
            cur.execute(
                """
                SELECT d.doc_id, d.title, d.regulator, d.in_force_from, d.in_force_to, 
                       d.status, d.source_url, d.pdf_url, t.body
                FROM documents d
                LEFT JOIN texts t ON d.doc_id = t.doc_id
                WHERE d.doc_id LIKE ? OR d.title LIKE ?
                LIMIT 1
                """,
                (f"%{doc_id_clean}%", f"%{doc_id_clean}%")
            )
            row = cur.fetchone()
            if row:
                return dict(row)

            # 3. Numeric ID match if digits present (e.g. 10321)
            digits = re.findall(r'\d+', doc_id_clean)
            if digits:
                cur.execute(
                    """
                    SELECT d.doc_id, d.title, d.regulator, d.in_force_from, d.in_force_to, 
                           d.status, d.source_url, d.pdf_url, t.body
                    FROM documents d
                    LEFT JOIN texts t ON d.doc_id = t.doc_id
                    WHERE d.doc_id LIKE ?
                    LIMIT 1
                    """,
                    (f"%:{digits[-1]}",)
                )
                row = cur.fetchone()
                if row:
                    return dict(row)

        return None

    def search_regulatory_context(
        self,
        query: str,
        as_of_date: str = "2026-06-01",
        regulator_filter: Optional[str] = None,
        max_chunks: int = 4,
        min_relevance_score: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant circulars respecting temporal validity as of `as_of_date`.
        Applies SQL filtering for in_force_from <= as_of_date and in_force_to >= as_of_date.
        """
        # Generic stop words that shouldn't inflate document match scores
        stopwords = {
            "what", "which", "does", "under", "apply", "regulation", "circular", "requirement", 
            "please", "state", "with", "from", "have", "rbi", "sebi", "cbic", "mca", "notification", 
            "dated", "reserve", "bank", "india", "the", "for", "are", "and", "about", "this", "that",
            "section", "clause", "rules", "act", "para", "order", "guidelines", "master", "direction"
        }

        # Extract topical content keywords
        all_words = re.findall(r'\b[A-Za-z0-9_:-]{3,}\b', query)
        topical_words = [w for w in all_words if w.lower() not in stopwords]

        # Check for specific doc_ids or numbers (e.g., 10321, 10531)
        specific_ids = [w for w in topical_words if any(c.isdigit() for c in w)]

        if not topical_words:
            return []

        with self._get_connection() as conn:
            cur = conn.cursor()

            # Base query with temporal constraint
            sql = """
                SELECT d.doc_id, d.title, d.regulator, d.in_force_from, d.in_force_to, 
                       d.status, d.source_url, t.body
                FROM documents d
                JOIN texts t ON d.doc_id = t.doc_id
                WHERE (d.in_force_from <= ? OR d.in_force_from IS NULL)
                  AND (d.in_force_to >= ? OR d.in_force_to = 'PRESENT' OR d.in_force_to IS NULL)
            """
            params = [as_of_date, as_of_date]

            if regulator_filter and regulator_filter.upper() != "ALL":
                sql += " AND UPPER(d.regulator) = ?"
                params.append(regulator_filter.upper())

            # Specific ID search has highest priority
            if specific_ids:
                id_clauses = ["d.doc_id LIKE ?" for _ in specific_ids]
                sql += " AND (" + " OR ".join(id_clauses) + ")"
                for sid in specific_ids:
                    params.append(f"%{sid}%")
            else:
                like_clauses = []
                for w in topical_words[:5]:
                    like_clauses.append("(d.title LIKE ? OR t.body LIKE ?)")
                    params.extend([f"%{w}%", f"%{w}%"])
                sql += " AND (" + " OR ".join(like_clauses) + ")"

            # Order by title keyword matches first to guarantee high-relevance candidates
            title_score_clauses = []
            for w in topical_words[:4]:
                title_score_clauses.append(f"CASE WHEN d.title LIKE ? THEN 15 ELSE 0 END")
                params.append(f"%{w}%")

            if title_score_clauses:
                sql += " ORDER BY (" + " + ".join(title_score_clauses) + ") DESC"

            sql += " LIMIT 150"
            cur.execute(sql, params)
            rows = cur.fetchall()

        results = []
        for r in rows:
            doc_id = r["doc_id"]
            body = r["body"] or ""
            title = r["title"] or ""
            reg = r["regulator"] or "RBI"
            status = r["status"] or "active"
            in_force_from = r["in_force_from"] or "2020-01-01"
            in_force_to = r["in_force_to"] or "PRESENT"

            # Compute relevance score based strictly on topical content words
            distinct_word_hits = set()
            score = 0
            for w in topical_words:
                w_lower = w.lower()
                hit = False
                if w_lower in doc_id.lower():
                    score += 30
                    hit = True
                if w_lower in title.lower():
                    score += 20
                    hit = True
                if w_lower in body[:1200].lower():
                    score += 5
                    hit = True
                if hit:
                    distinct_word_hits.add(w_lower)

            # Compound relevance requirement:
            # If query has 2 or more topical words, require at least 2 distinct word matches
            # to avoid false-positive single-word matches (e.g., just matching "norms" or "accounts")
            if len(topical_words) >= 2 and len(distinct_word_hits) < 2:
                continue

            if score < min_relevance_score or not distinct_word_hits:
                continue

            # Chunk document body to ~1000 characters
            chunk_body = body[:1000] if body else f"Regulatory provision text for {doc_id}."
            results.append({
                "doc_id": doc_id,
                "title": title,
                "regulator": reg,
                "status": status,
                "in_force_from": in_force_from,
                "in_force_to": in_force_to,
                "body": chunk_body,
                "locator": "para 1",
                "relevance_score": score,
            })

        # Sort by relevance
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results[:max_chunks]

    def build_inference_messages(
        self,
        question: str,
        retrieved_chunks: List[Dict[str, Any]],
        as_of_date: str = "2026-06-01"
    ) -> List[Dict[str, str]]:
        """Constructs system and user chat template prompt matching Stage 1 & 2 fine-tuning distribution."""
        chunks_text = []
        for i, c in enumerate(retrieved_chunks):
            doc_id = c["doc_id"]
            loc = c.get("locator", "para 1")
            reg = c.get("regulator", "RBI")
            title = c.get("title", "")
            status = c.get("status", "active")
            in_force_from = c.get("in_force_from", "2020-01-01")
            in_force_to = c.get("in_force_to", "PRESENT")
            content = c.get("body", "")

            header = f"HEADER: [REGULATOR: {reg} | DOC: {doc_id} | TITLE: {title} | STATUS: {status} | IN-FORCE: FROM {in_force_from} TO {in_force_to} | PROVISION: {loc}]"
            chunks_text.append(f"--- CHUNK {i+1} [{doc_id} / {loc}] ---\n{header}\nCONTENT:\n{content}")

        if not chunks_text:
            chunks_formatted = "NO APPLICABLE REGULATORY PROVISIONS FOUND IN RETRIEVAL."
        else:
            chunks_formatted = "\n\n".join(chunks_text)

        system_prompt = (
            "You are an expert Indian regulatory compliance assistant. Your task is to answer legal, banking, tax, and securities compliance questions directly and concisely using ONLY the provided regulatory context provisions.\n\n"
            "RULES:\n"
            "1. Ground every statement strictly in the retrieved context chunks. Do NOT introduce external legal facts.\n"
            "2. Provide an inline citation for EVERY factual claim using the exact format: [doc_id / provision_path] (e.g. [RBI_MD_KYC / para 38]).\n"
            "3. Answer directly in 2-4 sentences without repeating the question or restating prompt headers.\n"
            "4. If the retrieved context is insufficient or unhelpful to answer the question, you MUST begin your response with:\n"
            "   INSUFFICIENT_CORPUS_EVIDENCE: <explanation>\n"
            "5. If relying on a chunk marked with UNCERTAIN_VALIDITY, explicitly flag it in your explanation."
        )

        user_prompt = f"AS-OF DATE CONTEXT: {as_of_date}\n\nRETRIEVED REGULATORY PROVISIONS:\n{chunks_formatted}\n\nQUESTION: {question}\n\nRESPONSE:"

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Return corpus breakdown by regulator."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM documents")
            total_docs = cur.fetchone()[0]
            cur.execute("SELECT regulator, COUNT(*) FROM documents GROUP BY regulator ORDER BY COUNT(*) DESC")
            by_regulator = dict(cur.fetchall())
        return {
            "total_documents": total_docs,
            "by_regulator": by_regulator
        }

if __name__ == "__main__":
    engine = RegulatoryRAGEngine()
    print("Database Stats:", engine.get_stats())
    sample = engine.search_regulatory_context("Priority Sector Lending MFIs", as_of_date="2026-06-01")
    print(f"Sample retrieval returned {len(sample)} chunks.")
    if sample:
        print("Top match:", sample[0]["doc_id"], "|", sample[0]["title"])
