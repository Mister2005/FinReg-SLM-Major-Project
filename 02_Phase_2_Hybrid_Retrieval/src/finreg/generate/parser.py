"""Output extraction parser for inline citations and parseable abstentions (T-113)."""

import re
from dataclasses import dataclass, field
from typing import List, Tuple, Optional


@dataclass
class ParsedGeneration:
    raw_response: str
    abstained: bool
    abstention_reason: Optional[str] = None
    citations: List[Tuple[str, str]] = field(default_factory=list)


CITATION_PATTERN = re.compile(r'[\[\(]\s*([a-zA-Z0-9_\-\.:]+)\s*/\s*([^\]\)]+)[\]\)]')


def parse_model_response(response_text: str) -> ParsedGeneration:
    """Parses model response into structured citation tuples and abstention status."""
    text = response_text.strip()
    abstained = False
    abstention_reason = None

    if text.startswith("INSUFFICIENT_CORPUS_EVIDENCE:"):
        abstained = True
        parts = text.split("INSUFFICIENT_CORPUS_EVIDENCE:", 1)
        abstention_reason = parts[1].strip() if len(parts) > 1 else ""

    # Extract all inline citations [doc_id / provision_path]
    raw_citations = CITATION_PATTERN.findall(text)
    citations = [(doc_id.strip(), path.strip()) for doc_id, path in raw_citations]

    return ParsedGeneration(
        raw_response=text,
        abstained=abstained,
        abstention_reason=abstention_reason,
        citations=citations
    )
