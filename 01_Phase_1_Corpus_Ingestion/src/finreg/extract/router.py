from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from finreg.extract.html import extract_html
from finreg.extract.ocr import OcrFailed, ocr_pdf
from finreg.extract.pdf import OCRRequired, PdfCorrupt, extract_pdf

_PDF_MAGIC = b"%PDF-"
MIN_OCR_CONFIDENCE_DEFAULT = 0.70


class ContentTypeUnexpected(Exception):
    def __init__(self, content_type: str) -> None:
        self.content_type = content_type
        super().__init__(f"unhandled content type: {content_type}")


@dataclass(frozen=True)
class ExtractionResult:
    text: str
    page_count: int | None
    chars_per_page: list[int]
    text_source: str
    extractor: str
    extractor_version: str
    tables: list[list[list[str]]] = field(default_factory=list)
    quality_flags: list[str] = field(default_factory=list)


def _looks_like_pdf(blob_path: Path, content_type: str) -> bool:
    if content_type and "pdf" in content_type.lower():
        return True
    with open(blob_path, "rb") as f:
        return f.read(len(_PDF_MAGIC)) == _PDF_MAGIC


def _looks_like_html(content_type: str) -> bool:
    return bool(content_type) and "html" in content_type.lower()


def extract(
    blob_path: Path,
    content_type: str,
    *,
    content_selector: str | None = None,
    ocr_work_dir: Path | None = None,
    min_ocr_confidence: float = MIN_OCR_CONFIDENCE_DEFAULT,
) -> ExtractionResult:
    if _looks_like_pdf(blob_path, content_type):
        try:
            result = extract_pdf(blob_path)
        except PdfCorrupt:
            raise
        except OCRRequired:
            return _extract_via_ocr(blob_path, ocr_work_dir, min_ocr_confidence)
        return ExtractionResult(
            text=result.text,
            page_count=result.page_count,
            chars_per_page=result.chars_per_page,
            text_source=result.text_source,
            extractor=result.extractor,
            extractor_version=result.extractor_version,
        )

    if _looks_like_html(content_type):
        if content_selector is None:
            raise ValueError("content_selector is required to extract HTML content")
        result = extract_html(blob_path.read_bytes(), content_selector)
        return ExtractionResult(
            text=result.text,
            page_count=None,
            chars_per_page=[],
            text_source="html",
            extractor=result.extractor,
            extractor_version=result.extractor_version,
        )

    raise ContentTypeUnexpected(content_type)


def _extract_via_ocr(
    blob_path: Path, ocr_work_dir: Path | None, min_ocr_confidence: float
) -> ExtractionResult:
    with tempfile.TemporaryDirectory() as tmp:
        work_dir = ocr_work_dir if ocr_work_dir is not None else Path(tmp)
        try:
            result = ocr_pdf(blob_path, work_dir)
        except OcrFailed:
            raise

    quality_flags = []
    if result.mean_confidence < min_ocr_confidence:
        quality_flags.append("low_ocr_confidence")

    return ExtractionResult(
        text=result.text,
        page_count=None,
        chars_per_page=[],
        text_source=result.text_source,
        extractor=result.extractor,
        extractor_version=result.extractor_version,
        quality_flags=quality_flags,
    )
