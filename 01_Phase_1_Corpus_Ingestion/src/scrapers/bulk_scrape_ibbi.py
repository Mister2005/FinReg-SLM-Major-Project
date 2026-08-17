"""Bulk Scraper for Insolvency and Bankruptcy Board of India (IBBI) Circulars."""

import re
import io
import time
import sqlite3
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
import pypdf
import urllib3

urllib3.disable_warnings()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bulk_scrape_ibbi")

ROOT_DIR = Path(r"c:\Users\Varun\Desktop\Main\Sem 7\Major Project")
MANIFEST_DB = ROOT_DIR / "Phase 1" / "data" / "manifest.db"
BASE_URL = "https://ibbi.gov.in/legal-framework/circulars"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

def extract_pdf_text(pdf_bytes: bytes) -> str:
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        pages_text = []
        for p in reader.pages:
            t = p.extract_text()
            if t:
                pages_text.append(t.strip())
        return "\n\n".join(pages_text)
    except Exception as e:
        logger.warning(f"Error parsing PDF: {e}")
        return ""

def crawl_ibbi():
    logger.info("=== STARTING BULK IBBI SCRAPER ===")
    conn = sqlite3.connect(str(MANIFEST_DB))
    cur = conn.cursor()
    now_iso = datetime.utcnow().isoformat() + "Z"

    client = httpx.Client(verify=False, headers=HEADERS, timeout=25.0, follow_redirects=True)
    
    total_found = 0
    total_ingested = 0

    # IBBI circulars pagination
    for page in range(1, 15):
        page_url = f"{BASE_URL}?page={page}" if page > 1 else BASE_URL
        logger.info(f"Fetching IBBI Circulars Page {page}: {page_url}")
        try:
            resp = client.get(page_url)
            if resp.status_code != 200:
                logger.info(f"Page {page} returned status {resp.status_code}. Ending crawl.")
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table")
            if not table:
                logger.info(f"No table found on page {page}. Ending crawl.")
                break

            rows = table.find_all("tr")
            page_entries = 0

            for r in rows:
                cells = r.find_all("td")
                if len(cells) < 4:
                    continue

                # Columns typically: [S.No, Date, Subject, PDF/Download]
                date_text = cells[1].get_text().strip()
                subject_text = cells[2].get_text().strip()
                link = cells[3].find("a")
                if not link or not link.get("href"):
                    continue

                pdf_href = link.get("href")
                pdf_url = urljoin(BASE_URL, pdf_href)
                if not pdf_url.lower().endswith(".pdf") and ".pdf" not in pdf_url.lower():
                    continue

                total_found += 1
                page_entries += 1

                # Parse date
                issue_date = None
                date_match = re.search(r"\d{2}[-/.]\d{2}[-/.]\d{4}", date_text)
                if date_match:
                    try:
                        raw_d = date_match.group(0).replace("/", "-").replace(".", "-")
                        parts = raw_d.split("-")
                        if len(parts[0]) == 4:
                            issue_date = raw_d
                        else:
                            issue_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
                    except Exception:
                        issue_date = "2020-01-01"

                # Extract Circular Number from subject or text
                c_num_match = re.search(r"IBBI/[A-Z0-9/_.-]+", subject_text)
                doc_number = c_num_match.group(0) if c_num_match else f"IBBI/CIR/{total_found}"
                natural_id = re.sub(r"[^a-zA-Z0-9_]", "_", doc_number.lower())
                doc_id = f"ibbi:circulars:{natural_id}"

                logger.info(f"[{total_found}] Found IBBI Circular: {doc_number} | Date: {issue_date} | Downloading PDF...")

                # Download PDF and extract text
                try:
                    pdf_resp = client.get(pdf_url)
                    if pdf_resp.status_code == 200:
                        pdf_text = extract_pdf_text(pdf_resp.content)
                        if len(pdf_text) > 50:
                            body = f"{doc_number}\nDate: {issue_date}\nSubject: {subject_text}\n\n{pdf_text}"
                            sha256_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()

                            cur.execute(
                                """
                                INSERT OR REPLACE INTO documents (
                                    doc_id, regulator, source_name, doc_type, doc_number, title,
                                    issue_date, source_url, pdf_url, retrieved_at, status,
                                    in_force_from, in_force_to, licence
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    doc_id, "ibbi", "ibbi_official_portal", "circular", doc_number, subject_text,
                                    issue_date, page_url, pdf_url, now_iso, "in_force",
                                    issue_date, "PRESENT", "godl_india"
                                )
                            )

                            cur.execute(
                                """
                                INSERT OR REPLACE INTO texts (
                                    doc_id, blob_sha256, text_source, extractor, extractor_version,
                                    page_count, char_count, mean_ocr_conf, body, extracted_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    doc_id, sha256_hash, "pdf_layer", "pypdf_extractor", "v3.0",
                                    1, len(body), 1.0, body, now_iso
                                )
                            )
                            total_ingested += 1
                            conn.commit()
                except Exception as exc:
                    logger.warning(f"Failed to download/extract {pdf_url}: {exc}")

                time.sleep(0.5)

            logger.info(f"Page {page} complete: {page_entries} circulars processed.")
            if page_entries == 0:
                break
        except Exception as e:
            logger.error(f"Error on page {page}: {e}")
            break

    conn.close()
    logger.info(f"=== IBBI CRAWL COMPLETE: Found {total_found}, Successfully Ingested {total_ingested} Full-Text Circulars ===")

if __name__ == "__main__":
    crawl_ibbi()
