"""Extractive Substring Citation Guardrail Verifier for Phase 4."""

import re
from typing import List, Dict, Any, Tuple

class ExtractiveVerifier:
    def __init__(self):
        self.citation_pattern = re.compile(r"\[([a-zA-Z0-9_\-:]+)\s*/\s*([^\]]+)\]")

    def extract_citations(self, text: str) -> List[Tuple[str, str]]:
        matches = self.citation_pattern.findall(text)
        return [(m[0].strip(), m[1].strip()) for m in matches]

    def verify_response(self, generation: str, retrieved_chunks: List[Any]) -> Dict[str, Any]:
        citations = self.extract_citations(generation)
        if not citations:
            return {
                "is_verified": False,
                "reason": "NO_CITATIONS_FOUND",
                "valid_citations": [],
                "unverified_citations": [],
                "grounding_ratio": 0.0,
            }

        retrieved_set = set()
        for chunk in retrieved_chunks:
            if hasattr(chunk, "doc_id"):
                retrieved_set.add((chunk.doc_id, chunk.provision_path))
            elif isinstance(chunk, dict):
                retrieved_set.add((chunk.get("doc_id", ""), chunk.get("provision_path", "")))

        valid_cits = []
        unverified_cits = []

        for doc_id, loc in citations:
            # Check exact or partial locator match within retrieved docs
            matched = any(doc_id == r_doc and (loc in r_loc or r_loc in loc) for r_doc, r_loc in retrieved_set)
            if matched:
                valid_cits.append((doc_id, loc))
            else:
                unverified_cits.append((doc_id, loc))

        grounding_ratio = len(valid_cits) / len(citations) if citations else 0.0
        return {
            "is_verified": len(unverified_cits) == 0,
            "total_citations": len(citations),
            "valid_citations": valid_cits,
            "unverified_citations": unverified_cits,
            "grounding_ratio": round(grounding_ratio, 4),
        }
