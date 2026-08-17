from __future__ import annotations

import re

_RBI_MASTER_REF = re.compile(r"RBI/(?:[A-Za-z]+/)?\d{4}-\d{2,4}/\d+")
_RBI_DEPARTMENTAL_REF = re.compile(
    r"\b[A-Z]{2,}(?:\.[A-Za-z0-9]+)+/[\w.\-]+/\d{4}-\d{2,4}"
)
_CBDT_CIRCULAR = re.compile(r"CIRCULAR\s+NO\.?\s*(\d+)\s*/\s*(\d{4})", re.IGNORECASE)
_CBDT_NOTIFICATION = re.compile(
    r"\b(S\.?O\.?|G\.?S\.?R\.?)\s*(\d+)\s*\(E\)", re.IGNORECASE
)
_GST_CIRCULAR = re.compile(r"Circular\s+No\.?\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d{4})-GST", re.IGNORECASE)

# Real 2026-08-04 finding: a Master Direction carries two independent
# reference numbers on its own detail page — its RBI/<dept>/<FY>/<seq>
# doc_number (matched above) AND a separate self-identifying series number
# like "FMRD.Master Direction No.2/2016-17" that OTHER documents cite it by
# (e.g. "in supersession of ... Master Direction No. 2/2016-17 dated..."),
# not the RBI/... form. Department prefix and spacing vary by document, so
# this matches and normalizes just the "Master Direction No. <n>/<FY>" core.
_RBI_MASTER_DIRECTION_SERIES_REF = re.compile(
    r"Master\s+Direction\s+No\.?\s*(\d+)\s*/\s*(\d{4}-\d{2,4})", re.IGNORECASE
)


def match_rbi_master_reference(text: str) -> str | None:
    match = _RBI_MASTER_REF.search(text)
    return match.group(0) if match else None


def match_rbi_master_direction_series(text: str) -> str | None:
    match = _RBI_MASTER_DIRECTION_SERIES_REF.search(text)
    if not match:
        return None
    return f"MASTER DIRECTION NO. {match.group(1)}/{match.group(2)}"


def match_rbi_departmental_reference(text: str) -> str | None:
    match = _RBI_DEPARTMENTAL_REF.search(text)
    return match.group(0) if match else None


def match_cbdt_circular(text: str) -> str | None:
    match = _CBDT_CIRCULAR.search(text)
    return match.group(0) if match else None


def match_cbdt_notification(text: str) -> str | None:
    match = _CBDT_NOTIFICATION.search(text)
    return match.group(0) if match else None


def match_gst_circular(text: str) -> str | None:
    match = _GST_CIRCULAR.search(text)
    return match.group(0) if match else None
