"""Temporal filtering engine for version-aware regulatory retrieval (T-112)."""

from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional
from finreg.retrieve.chunker import RegulatoryChunk


def parse_date(d_str: Optional[str]) -> Optional[datetime]:
    if not d_str:
        return None
    try:
        return datetime.strptime(d_str[:10], "%Y-%m-%d")
    except ValueError:
        return None


class TemporalFilter:
    """Filters retrieved chunks based on query as_of date and document in_force validity."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def filter_chunks(
        self,
        chunks: List[Tuple[RegulatoryChunk, float]],
        as_of_date_str: str
    ) -> Dict[str, List[Tuple[RegulatoryChunk, float]]]:
        """
        Filters chunks into eligible, unknown_status, and excluded buckets.
        Per spec 14: candidate is eligible if in_force_from <= as_of AND (in_force_to IS NULL OR in_force_to > as_of) AND status != 'withdrawn'.
        """
        if not self.enabled:
            return {
                "eligible": chunks,
                "unknown_status": [],
                "excluded": []
            }

        query_date = parse_date(as_of_date_str)
        if query_date is None:
            query_date = datetime.now()

        eligible = []
        unknown_status = []
        excluded = []

        for chunk, score in chunks:
            # 1. Exclude withdrawn provisions
            if chunk.status == "withdrawn":
                excluded.append((chunk, score))
                continue

            # 2. Check in_force date validity
            from_date = parse_date(chunk.in_force_from)
            to_date = parse_date(chunk.in_force_to)

            is_from_ok = (from_date is None) or (from_date <= query_date)
            is_to_ok = (to_date is None) or (to_date > query_date)

            if is_from_ok and is_to_ok:
                eligible.append((chunk, score))
                if chunk.status == "unknown":
                    unknown_status.append((chunk, score))
            else:
                excluded.append((chunk, score))

        return {
            "eligible": eligible,
            "unknown_status": unknown_status,
            "excluded": excluded
        }
