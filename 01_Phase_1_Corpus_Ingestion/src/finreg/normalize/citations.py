from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from finreg.normalize.doc_number import (
    _RBI_DEPARTMENTAL_REF,
    _RBI_MASTER_REF,
    _RBI_MASTER_DIRECTION_SERIES_REF,
)

_DATE_TEXT = re.compile(r"[A-Za-z]+ \d{1,2},\s*\d{4}")
_DATE_NUMERIC = re.compile(r"\d{2}\.\d{2}\.\d{4}")


def _parse_any_date(text: str) -> date | None:
    match = _DATE_TEXT.search(text)
    if match:
        candidate = re.sub(r"\s+", " ", match.group(0)).strip()
        for fmt in ("%b %d, %Y", "%B %d, %Y"):
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
    match = _DATE_NUMERIC.search(text)
    if match:
        try:
            return datetime.strptime(match.group(0), "%d.%m.%Y").date()
        except ValueError:
            return None
    return None


@dataclass(frozen=True)
class CitationCandidate:
    raw_span: str
    char_start: int
    char_end: int
    citation_type: str
    target_act: str | None
    target_section: str | None
    relation: str | None
    confidence: float
    circular_number: str | None = None
    circular_date: date | None = None


# Real 2026-08-04 finding, from a full unbounded crawl of real RBI text:
# "in supersession of" phrases very commonly cite a Notification (FEMA-style,
# e.g. "Notification No. FEMA 120/RB-2004 dated July 07, 2004") or an A.P.
# (DIR Series) Circular (e.g. "A.P. (DIR Series) Circular No.115 dated March
# 28, 2014"), neither of which the departmental/master-reference patterns
# match. Added for T-035 raw_span/relation capture even where the cited
# document predates the crawl window and so can't resolve to a target_doc_id
# — that outcome is doc06's own accepted 'unknown' terminal state, not a bug.
_NOTIFICATION_NO_REF = re.compile(
    r"Notification\s+No\.?\s*[A-Za-z]*[.\s]*\d+[\w\-/]*(?:\s+(?!dated\b)[\w\-/]+)?",
    re.IGNORECASE,
)
_AP_DIR_CIRCULAR_REF = re.compile(
    r"A\.P\.\s*\(DIR\s+Series\)\s*Circular\s+No\.?\s*\d+", re.IGNORECASE
)

# Reference + "dated <date>" — the real pattern observed in RBI Master
# Circulars ("Master Circular DoR.CRE.REC.71/07.10.002/2023-24 dated January
# 16, 2024") and applicable to the master-reference form too.
_REF_DATED_PATTERNS = (
    _RBI_DEPARTMENTAL_REF,
    _RBI_MASTER_REF,
    _NOTIFICATION_NO_REF,
    _AP_DIR_CIRCULAR_REF,
)
_DATED_SUFFIX = re.compile(
    r"\s+dated\s+(" + _DATE_TEXT.pattern + r"|" + _DATE_NUMERIC.pattern + r")"
)

# doc-05's own quoted generic form: "Circular No. 3 of 2023 dated 28.03.2023"
_GENERIC_CIRCULAR_DATED = re.compile(
    r"Circular\s+No\.?\s*(\d+)\s+of\s+(\d{4})\s+dated\s+(\d{2}\.\d{2}\.\d{4})",
    re.IGNORECASE,
)

# Master Directions carry a second, department-prefix-free series number
# (e.g. "Master Direction No. 2/2016-17") that OTHER documents cite them by,
# distinct from their RBI/<dept>/<FY>/<seq> doc_number. Normalized to match
# how normalize.doc_number.match_rbi_master_direction_series stores it on
# the target document's own alias_doc_number, so resolve_circular_target can
# match by equality regardless of the citing document's exact punctuation/
# department-prefix variant (e.g. "FMRD.Master Direction No.2/2016-17" vs
# "FMRD Master Direction No. 2/2016-17" both normalize the same way).
_MASTER_DIRECTION_SERIES_DATED = re.compile(
    _RBI_MASTER_DIRECTION_SERIES_REF.pattern
    + r"\s+dated\s+("
    + _DATE_TEXT.pattern
    + r"|"
    + _DATE_NUMERIC.pattern
    + r")",
    re.IGNORECASE,
)

_STATUTE_SECTION = re.compile(
    r"[Ss]ection\s+\d+[A-Za-z]*(?:\(\w+\))*"
)
_STATUTE_RULE = re.compile(
    r"Rule\s+\w+\s+of\s+the\s+([A-Za-z\- ,]+?(?:Rules|Regulations),?\s*\d{4})",
)

_SUPERSESSION_PHRASES: tuple[tuple[str, str], ...] = (
    ("in supersession of", "supersedes"),
    ("stands withdrawn", "withdraws"),
    ("is hereby repealed", "withdraws"),
    ("shall cease to have effect", "withdraws"),
    ("subsumed in", "supersedes"),
    ("partial modification of", "amends"),
)


def extract_citations(text: str) -> list[CitationCandidate]:
    candidates: list[CitationCandidate] = []

    for pattern in _REF_DATED_PATTERNS:
        for match in pattern.finditer(text):
            suffix_match = _DATED_SUFFIX.match(text, match.end())
            if not suffix_match:
                continue
            full_start, full_end = match.start(), suffix_match.end()
            raw_span = text[full_start:full_end]
            circular_date = _parse_any_date(suffix_match.group(1))
            candidates.append(
                CitationCandidate(
                    raw_span=raw_span,
                    char_start=full_start,
                    char_end=full_end,
                    citation_type="circular",
                    target_act=None,
                    target_section=None,
                    relation=None,
                    confidence=1.0 if circular_date else 0.6,
                    circular_number=match.group(0),
                    circular_date=circular_date,
                )
            )

    for match in _GENERIC_CIRCULAR_DATED.finditer(text):
        circular_date = _parse_any_date(match.group(3))
        candidates.append(
            CitationCandidate(
                raw_span=match.group(0),
                char_start=match.start(),
                char_end=match.end(),
                citation_type="circular",
                target_act=None,
                target_section=None,
                relation=None,
                confidence=1.0 if circular_date else 0.6,
                circular_number=f"{match.group(1)}/{match.group(2)}",
                circular_date=circular_date,
            )
        )

    for match in _MASTER_DIRECTION_SERIES_DATED.finditer(text):
        circular_date = _parse_any_date(match.group(3))
        candidates.append(
            CitationCandidate(
                raw_span=match.group(0),
                char_start=match.start(),
                char_end=match.end(),
                citation_type="circular",
                target_act=None,
                target_section=None,
                relation=None,
                confidence=1.0 if circular_date else 0.6,
                circular_number=f"MASTER DIRECTION NO. {match.group(1)}/{match.group(2)}",
                circular_date=circular_date,
            )
        )

    for match in _STATUTE_RULE.finditer(text):
        candidates.append(
            CitationCandidate(
                raw_span=match.group(0),
                char_start=match.start(),
                char_end=match.end(),
                citation_type="statute_section",
                target_act=match.group(1).strip(),
                target_section=None,
                relation=None,
                confidence=0.9,
            )
        )

    for match in _STATUTE_SECTION.finditer(text):
        candidates.append(
            CitationCandidate(
                raw_span=match.group(0),
                char_start=match.start(),
                char_end=match.end(),
                citation_type="statute_section",
                target_act=None,
                target_section=match.group(0),
                relation=None,
                confidence=0.7,
            )
        )

    for phrase, relation in _SUPERSESSION_PHRASES:
        start = 0
        while True:
            idx = text.lower().find(phrase, start)
            if idx == -1:
                break
            candidates.append(
                CitationCandidate(
                    raw_span=text[idx : idx + len(phrase)],
                    char_start=idx,
                    char_end=idx + len(phrase),
                    citation_type="unresolved",
                    target_act=None,
                    target_section=None,
                    relation=relation,
                    confidence=0.5,
                )
            )
            start = idx + len(phrase)

    candidates = _merge_supersession_phrases_with_nearby_references(text, candidates)

    for c in candidates:
        assert text[c.char_start : c.char_end] == c.raw_span

    return candidates


# A supersession phrase's target is usually the nearest circular reference
# following it in the same sentence, e.g. "in supersession of RBI/2020-21/1
# dated ...". Merging them means the resulting citation row carries both the
# relation and the resolvable target, which is what the supersession graph
# (temporal/graph.py) actually needs — a bare phrase with no target and a
# bare reference with no relation are each individually useless for the
# graph, even though both are still retained on their own if no merge fits.
_MERGE_PROXIMITY_CHARS = 120


def _merge_supersession_phrases_with_nearby_references(
    text: str, candidates: list[CitationCandidate]
) -> list[CitationCandidate]:
    phrase_candidates = [c for c in candidates if c.relation is not None and c.citation_type == "unresolved"]
    reference_candidates = [c for c in candidates if c.citation_type == "circular" and c.relation is None]

    merged_reference_ids = set()
    result: list[CitationCandidate] = []

    for phrase in phrase_candidates:
        best_ref = None
        best_distance = _MERGE_PROXIMITY_CHARS + 1
        for ref in reference_candidates:
            if id(ref) in merged_reference_ids:
                continue
            if ref.char_start < phrase.char_end:
                continue
            distance = ref.char_start - phrase.char_end
            if 0 <= distance < best_distance:
                best_distance = distance
                best_ref = ref
        if best_ref is not None:
            merged_reference_ids.add(id(best_ref))
            result.append(
                CitationCandidate(
                    raw_span=text[phrase.char_start : best_ref.char_end],
                    char_start=phrase.char_start,
                    char_end=best_ref.char_end,
                    citation_type="circular",
                    target_act=None,
                    target_section=None,
                    relation=phrase.relation,
                    confidence=best_ref.confidence,
                    circular_number=best_ref.circular_number,
                    circular_date=best_ref.circular_date,
                )
            )
        else:
            result.append(phrase)

    for c in candidates:
        if c in phrase_candidates:
            continue
        if c in reference_candidates and id(c) in merged_reference_ids:
            continue
        result.append(c)

    return result
