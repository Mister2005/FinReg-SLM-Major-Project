from __future__ import annotations

import statistics
import subprocess
from dataclasses import dataclass
from importlib.metadata import version as _pkg_version
from pathlib import Path

import pypdfium2 as pdfium

MIN_CHARS_PER_PAGE_DEFAULT = 250
DOMINANT_IMAGE_AREA_RATIO = 0.60

PYPDFIUM2_VERSION = _pkg_version("pypdfium2")
EXTRACTOR_VERSION_PDF_LAYER = f"pypdfium2-{PYPDFIUM2_VERSION}-r1"
EXTRACTOR_VERSION_PDFTOTEXT = "pdftotext-poppler-r1"


class PdfCorrupt(Exception):
    pass


class OCRRequired(Exception):
    def __init__(self, blob_path: Path, reason: str) -> None:
        self.blob_path = blob_path
        self.reason = reason
        super().__init__(f"OCR required for {blob_path}: {reason}")


@dataclass(frozen=True)
class PdfExtractionResult:
    text: str
    page_count: int
    chars_per_page: list[int]
    text_source: str
    extractor: str
    extractor_version: str


def _extract_pdf_layer(blob_path: Path) -> tuple[str, list[int]]:
    try:
        doc = pdfium.PdfDocument(str(blob_path))
    except Exception as exc:  # noqa: BLE001
        raise PdfCorrupt(f"pypdfium2 could not open {blob_path}: {exc}") from exc

    chars_per_page: list[int] = []
    page_texts: list[str] = []
    try:
        for page in doc:
            textpage = page.get_textpage()
            text = textpage.get_text_range()
            page_texts.append(text)
            chars_per_page.append(len(text))
    except Exception as exc:  # noqa: BLE001
        raise PdfCorrupt(f"pypdfium2 failed reading pages of {blob_path}: {exc}") from exc

    return "\n\n".join(page_texts), chars_per_page


def _has_dominant_raster_image(blob_path: Path) -> bool:
    try:
        doc = pdfium.PdfDocument(str(blob_path))
    except Exception:  # noqa: BLE001
        return False

    for page in doc:
        width, height = page.get_size()
        page_area = width * height
        if page_area <= 0:
            continue
        for obj in page.get_objects():
            if obj.type != pdfium.raw.FPDF_PAGEOBJ_IMAGE:
                continue
            left, bottom, right, top = obj.get_bounds()
            image_area = max(0.0, right - left) * max(0.0, top - bottom)
            if image_area / page_area > DOMINANT_IMAGE_AREA_RATIO:
                return True
    return False


def _extract_via_pdftotext(blob_path: Path, page_count: int) -> list[str]:
    page_texts: list[str] = []
    for page_number in range(1, page_count + 1):
        try:
            result = subprocess.run(
                ["pdftotext", "-layout", "-f", str(page_number), "-l", str(page_number), str(blob_path), "-"],
                capture_output=True,
                timeout=60,
            )
        except (subprocess.SubprocessError, FileNotFoundError) as exc:
            raise PdfCorrupt(f"pdftotext failed on {blob_path}: {exc}") from exc
        if result.returncode != 0:
            raise PdfCorrupt(f"pdftotext exited {result.returncode} on {blob_path}")
        page_texts.append(result.stdout.decode("utf-8", errors="replace"))
    return page_texts


def extract_pdf(blob_path: Path, min_chars_per_page: int = MIN_CHARS_PER_PAGE_DEFAULT) -> PdfExtractionResult:
    text, chars_per_page = _extract_pdf_layer(blob_path)
    page_count = len(chars_per_page)
    median_chars = statistics.median(chars_per_page) if chars_per_page else 0

    if median_chars >= min_chars_per_page:
        return PdfExtractionResult(
            text=text,
            page_count=page_count,
            chars_per_page=chars_per_page,
            text_source="pdf_layer",
            extractor="pypdfium2",
            extractor_version=EXTRACTOR_VERSION_PDF_LAYER,
        )

    if _has_dominant_raster_image(blob_path):
        raise OCRRequired(blob_path, "median chars_per_page below threshold with a dominant raster image")

    fallback_pages = _extract_via_pdftotext(blob_path, page_count)
    fallback_chars_per_page = [len(p) for p in fallback_pages]
    fallback_median = statistics.median(fallback_chars_per_page) if fallback_chars_per_page else 0

    if fallback_median >= min_chars_per_page:
        return PdfExtractionResult(
            text="\n\n".join(fallback_pages),
            page_count=page_count,
            chars_per_page=fallback_chars_per_page,
            text_source="pdftotext",
            extractor="pdftotext",
            extractor_version=EXTRACTOR_VERSION_PDFTOTEXT,
        )

    raise OCRRequired(blob_path, "below threshold after pdftotext fallback, no dominant image detected")
