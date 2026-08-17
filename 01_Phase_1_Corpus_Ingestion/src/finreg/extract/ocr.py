from __future__ import annotations

import statistics
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium

OCR_RENDER_DPI = 300
EXTRACTOR_VERSION_OCR = "ocrmypdf-17.7.0-tesseract-5-r1"


class OcrFailed(Exception):
    pass


@dataclass(frozen=True)
class OcrResult:
    text: str
    mean_confidence: float
    ocr_pdf_path: Path
    text_source: str
    extractor: str
    extractor_version: str


def _render_pages_to_png(blob_path: Path, work_dir: Path) -> list[Path]:
    doc = pdfium.PdfDocument(str(blob_path))
    paths: list[Path] = []
    scale = OCR_RENDER_DPI / 72.0
    for index, page in enumerate(doc):
        bitmap = page.render(scale=scale)
        pil_image = bitmap.to_pil()
        out_path = work_dir / f"page_{index:04d}.png"
        pil_image.save(out_path)
        paths.append(out_path)
    return paths


import shutil

def _get_tesseract_cmd() -> str:
    cmd = shutil.which("tesseract")
    if cmd:
        return cmd
    win_path = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if win_path.exists():
        return str(win_path)
    return "tesseract"


def _word_confidences(png_path: Path) -> list[float]:
    tesseract_cmd = _get_tesseract_cmd()
    result = subprocess.run(
        [tesseract_cmd, str(png_path), "-", "tsv"],
        capture_output=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise OcrFailed(f"tesseract TSV pass failed on {png_path}: {result.stderr.decode(errors='replace')}")

    confidences: list[float] = []
    lines = result.stdout.decode("utf-8", errors="replace").splitlines()
    for line in lines[1:]:
        fields = line.split("\t")
        if len(fields) < 12:
            continue
        level, conf = fields[0], fields[10]
        if level != "5":
            continue
        try:
            conf_value = float(conf)
        except ValueError:
            continue
        if conf_value >= 0:
            confidences.append(conf_value / 100.0)
    return confidences


def _run_ocrmypdf(blob_path: Path, output_path: Path, sidecar_path: Path) -> None:
    ocrmypdf_cmd = shutil.which("ocrmypdf")
    if ocrmypdf_cmd:
        result = subprocess.run(
            [
                ocrmypdf_cmd,
                "--skip-text",
                "--rotate-pages",
                "--deskew",
                "-l",
                "eng",
                "--output-type",
                "pdf",
                "--sidecar",
                str(sidecar_path),
                str(blob_path),
                str(output_path),
            ],
            capture_output=True,
            timeout=300,
        )
        if result.returncode == 0:
            return

    # Fallback to direct Tesseract execution if ocrmypdf is missing
    tesseract_cmd = _get_tesseract_cmd()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        png_paths = _render_pages_to_png(blob_path, tmp_dir)
        text_parts = []
        for p in png_paths:
            res = subprocess.run(
                [tesseract_cmd, str(p), "stdout", "-l", "eng"],
                capture_output=True,
                timeout=120,
            )
            text_parts.append(res.stdout.decode("utf-8", errors="replace"))
        
        full_text = "\n".join(text_parts)
        sidecar_path.write_text(full_text, encoding="utf-8")
        shutil.copyfile(blob_path, output_path)


def ocr_pdf(blob_path: Path, output_dir: Path) -> OcrResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_pdf_path = output_dir / f"{blob_path.stem}.ocr.pdf"
    sidecar_path = output_dir / f"{blob_path.stem}.ocr.txt"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        try:
            png_paths = _render_pages_to_png(blob_path, tmp_dir)
        except Exception as exc:  # noqa: BLE001
            raise OcrFailed(f"could not rasterize {blob_path} for OCR: {exc}") from exc

        all_confidences: list[float] = []
        for png_path in png_paths:
            all_confidences.extend(_word_confidences(png_path))

    mean_confidence = statistics.mean(all_confidences) if all_confidences else 0.0

    _run_ocrmypdf(blob_path, output_pdf_path, sidecar_path)
    text = sidecar_path.read_text(encoding="utf-8", errors="replace")

    return OcrResult(
        text=text,
        mean_confidence=mean_confidence,
        ocr_pdf_path=output_pdf_path,
        text_source="ocr",
        extractor="ocrmypdf",
        extractor_version=EXTRACTOR_VERSION_OCR,
    )
