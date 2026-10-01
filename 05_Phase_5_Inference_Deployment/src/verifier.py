"""
Test-Time Verifier & Citation Grounding Checker for FinReg-SLM.

Scores multiple candidate reasoning traces using rule-based statutory validation,
active circular index checks, and epistemic consistency checks.
"""

import re
import logging
from typing import List, Dict, Any, Tuple, Optional
from rag_engine import RegulatoryRAGEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("verifier")

class ComplianceVerifier:
    def __init__(self, rag_engine: RegulatoryRAGEngine):
        self.rag = rag_engine

    def verify_citation(self, citation_str: str, as_of_date: str = "2026-06-01") -> Tuple[bool, str]:
        """
        Verify if a cited circular identifier exists in the SQLite manifest
        and is temporally active as of the given date.
        """
        clean_cite = citation_str.strip()
        if not clean_cite:
            return False, "EMPTY_CITATION"

        # Check in RAG engine
        doc_match = self.rag.get_document_by_id(clean_cite)
        
        # If not found directly, check database for circular number substring
        if not doc_match:
            with self.rag._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT d.doc_id, d.title, d.in_force_from, d.in_force_to, d.status
                    FROM documents d
                    WHERE d.doc_id LIKE ? OR d.title LIKE ?
                    LIMIT 1
                    """,
                    (f"%{clean_cite}%", f"%{clean_cite}%")
                )
                row = cur.fetchone()
                if row:
                    doc_match = dict(row)

        if not doc_match:
            return False, "NON_EXISTENT_CITATION"

        # Check temporal validity
        in_force_from = doc_match.get("in_force_from") or "2000-01-01"
        in_force_to = doc_match.get("in_force_to") or "PRESENT"

        if in_force_from > as_of_date:
            return False, "PREMATURE_CITATION_NOT_YET_IN_FORCE"

        if in_force_to != "PRESENT" and in_force_to < as_of_date:
            return False, f"SUPERSEDED_CITATION_LAPSED_ON_{in_force_to}"

        return True, "ACTIVE_AND_VALID"

    def score_candidate(self, candidate: Dict[str, Any], as_of_date: str = "2026-06-01") -> float:
        """
        Score a single candidate response (0.0 to 100.0) based on statutory validity,
        structural completeness, and citation precision.
        """
        score = 0.0
        raw_output = candidate.get("raw_output", "")
        answer = candidate.get("answer", "")
        citations = candidate.get("citations", [])
        is_abstained = candidate.get("is_abstained", False)

        # 1. Structural reasoning integrity (up to 20 pts)
        if "<think>" in raw_output and "</think>" in raw_output:
            score += 20.0
        elif "</think>" in raw_output or "<think>" in raw_output:
            score += 10.0

        # 2. Calibrated refusal / Abstention check (up to 25 pts)
        if is_abstained:
            if "INSUFFICIENT_CORPUS_EVIDENCE" in raw_output:
                score += 25.0
            return score + 50.0  # Safe abstentions get high score if well-formatted

        # 3. Citation grounding & temporal validity (up to 40 pts)
        if citations:
            valid_count = 0
            for cite in citations:
                is_valid, _ = self.verify_citation(cite, as_of_date)
                if is_valid:
                    valid_count += 1
            citation_ratio = valid_count / len(citations)
            score += 40.0 * citation_ratio
        else:
            # Penalize ungrounded affirmative assertions
            score -= 10.0

        # 4. Length and conciseness sanity (up to 15 pts)
        word_count = len(answer.split())
        if 20 <= word_count <= 200:
            score += 15.0
        elif 10 <= word_count < 20 or 200 < word_count <= 350:
            score += 8.0

        return max(0.0, min(100.0, score))

    def select_best_candidate(
        self,
        candidates: List[Dict[str, Any]],
        as_of_date: str = "2026-06-01"
    ) -> Dict[str, Any]:
        """
        Evaluate N candidate generations and return the candidate with the highest verification score.
        """
        if not candidates:
            raise ValueError("No candidates provided for verification.")

        scored_candidates = []
        for cand in candidates:
            s = self.score_candidate(cand, as_of_date)
            scored_candidates.append((s, cand))

        # Sort descending by score
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_cand = scored_candidates[0]

        best_cand_copy = dict(best_cand)
        best_cand_copy["verification_score"] = round(best_score, 2)
        best_cand_copy["candidate_pool_size"] = len(candidates)
        return best_cand_copy

if __name__ == "__main__":
    engine = RegulatoryRAGEngine()
    verifier = ComplianceVerifier(engine)
    
    # Test citation check on a known circular in the DB
    ok, reason = verifier.verify_citation("FIDD.CO.Plan.BC.No.8", as_of_date="2026-06-01")
    print(f"Citation Verification for 'FIDD.CO.Plan.BC.No.8': {ok} ({reason})")
    
    # Mock candidate pool
    cands = [
        {
            "raw_output": "<think>Checking Master Direction...</think> The bank is compliant [FIDD.CO.Plan.BC.No.8 / para 1].",
            "answer": "The bank is compliant [FIDD.CO.Plan.BC.No.8 / para 1].",
            "citations": ["FIDD.CO.Plan.BC.No.8"],
            "is_abstained": False
        },
        {
            "raw_output": "The bank is compliant under fake law [FAKE/CIRCULAR/999].",
            "answer": "The bank is compliant under fake law [FAKE/CIRCULAR/999].",
            "citations": ["FAKE/CIRCULAR/999"],
            "is_abstained": False
        }
    ]
    best = verifier.select_best_candidate(cands, as_of_date="2026-06-01")
    print(f"Best Candidate Selected (Score: {best['verification_score']}): {best['answer']}")
