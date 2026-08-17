"""Bulk Scraper for Central Board of Indirect Taxes and Customs (CBIC) GST Circulars."""

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
logger = logging.getLogger("bulk_scrape_cbic")

ROOT_DIR = Path(r"c:\Users\Varun\Desktop\Main\Sem 7\Major Project")
MANIFEST_DB = ROOT_DIR / "Phase 1" / "data" / "manifest.db"
BASE_URL = "https://cbic-gst.gov.in/circulars-cgst.html"
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

def crawl_cbic():
    logger.info("=== STARTING BULK CBIC CGST SCRAPER ===")
    conn = sqlite3.connect(str(MANIFEST_DB))
    cur = conn.cursor()
    now_iso = datetime.utcnow().isoformat() + "Z"

    client = httpx.Client(verify=False, headers=HEADERS, timeout=25.0, follow_redirects=True)
    
    total_found = 0
    total_ingested = 0

    logger.info(f"Fetching CBIC master index: {BASE_URL}")
    try:
        resp = client.get(BASE_URL)
        if resp.status_code != 200:
            logger.error(f"Failed to fetch CBIC: {resp.status_code}")
            return

        soup = BeautifulSoup(resp.text, "html.parser")
        tables = soup.find_all("table")
        logger.info(f"Found {len(tables)} tables on CBIC index page.")

        for t_idx, table in enumerate(tables):
            rows = table.find_all("tr")
            for r in rows:
                cells = r.find_all("td")
                if len(cells) < 4:
                    continue

                c_no = cells[0].get_text().strip()
                link = cells[1].find("a") if len(cells) > 1 else None
                if not link:
                    link = r.find("a")
                
                pdf_url = urljoin(BASE_URL, link.get("href")) if link and link.get("href") else None
                date_str = cells[3].get_text().strip() if len(cells) > 3 else ""
                subject = cells[4].get_text().strip() if len(cells) > 4 else cells[-1].get_text().strip()

                if not c_no or not pdf_url:
                    continue

                total_found += 1
                doc_number = f"Circular No. {c_no}-GST"
                natural_id = re.sub(r"[^a-zA-Z0-9_]", "_", c_no.lower())
                doc_id = f"cbic:cgst_circulars:{natural_id}"

                # Parse date
                issue_date = None
                date_match = re.search(r"\d{2}[-/.]\d{2}[-/.]\d{4}", date_str)
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

                logger.info(f"[{total_found}] Found CBIC Circular: {c_no} | Date: {issue_date} | Downloading PDF...")

                try:
                    pdf_resp = client.get(pdf_url)
                    if pdf_resp.status_code == 200:
                        pdf_text = extract_pdf_text(pdf_resp.content)
                        if len(pdf_text) > 50:
                            body = f"{doc_number}\nDate: {issue_date}\nSubject: {subject}\n\n{pdf_text}"
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
                                    doc_id, "cbic", "cbic_official_portal", "circular", doc_number, subject,
                                    issue_date, BASE_URL, pdf_url, now_iso, "in_force",
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

                time.sleep(0.3)

    except Exception as e:
        logger.error(f"Error in CBIC crawl: {e}")

    conn.close()
    logger.info(f"=== CBIC CRAWL COMPLETE: Found {total_found}, Ingested {total_ingested} Circulars ===")

if __name__ == "__main__":
    crawl_cbic()
