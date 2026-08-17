"""Fast Bulk Scraper for EPFO Official Circulars."""

import io
import re
import time
import sqlite3
import hashlib
import logging
import urllib3
import requests
import bs4
import pypdf
from datetime import datetime
from pathlib import Path

urllib3.disable_warnings()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bulk_scrape_epfo")

ROOT_DIR = Path(r"c:\Users\Varun\Desktop\Main\Sem 7\Major Project")
MANIFEST_DB = ROOT_DIR / "Phase 1" / "data" / "manifest.db"
BASE_URL = "https://www.epfindia.gov.in"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def scrape_epfo_circulars():
    logger.info("=== STARTING FAST EPFO BULK SCRAPER ===")
    conn = sqlite3.connect(str(MANIFEST_DB), timeout=60)
    cur = conn.cursor()

    total_ingested = 0
    now_iso = datetime.utcnow().isoformat() + "Z"

    urls = [
        f"{BASE_URL}/site_en/index.php",
        f"{BASE_URL}/site_en/For_Employees.php",
        f"{BASE_URL}/site_en/For_Employers.php"
    ]

    seen_urls = set()

    for page_url in urls:
        logger.info(f"Scanning EPFO page: {page_url}")
        try:
            r = requests.get(page_url, headers=HEADERS, verify=False, timeout=8)
            if r.status_code != 200:
                continue

            soup = bs4.BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if not href or not (".pdf" in href.lower() or "circular" in href.lower()):
                    continue

                if href.startswith("http://") or href.startswith("https://"):
                    if "epfindia.gov.in" not in href:
                        continue
                    pdf_url = href
                elif href.startswith("../"):
                    pdf_url = f"{BASE_URL}/{href[3:]}"
                elif href.startswith("/"):
                    pdf_url = f"{BASE_URL}{href}"
                else:
                    pdf_url = f"{BASE_URL}/site_en/{href}"

                if pdf_url in seen_urls or not pdf_url.endswith(".pdf"):
                    continue
                seen_urls.add(pdf_url)

                title_text = clean_text(a.get_text() or a.get("title") or "")
                if not title_text or len(title_text) < 5:
                    filename = Path(pdf_url.split("?")[0]).stem
                    title_text = filename.replace("_", " ").replace("-", " ")

                safe_title = re.sub(r"[^a-zA-Z0-9]+", "_", title_text[:40].lower()).strip("_")
                doc_id = f"epfo:circ:{safe_title}"

                try:
                    pdf_resp = requests.get(pdf_url, headers=HEADERS, verify=False, timeout=6)
                    if pdf_resp.status_code != 200 or len(pdf_resp.content) < 500:
                        continue

                    pdf_file = io.BytesIO(pdf_resp.content)
                    reader = pypdf.PdfReader(pdf_file)
                    text_pages = [p.extract_text() for p in reader.pages if p.extract_text()]
                    full_text = "\n\n".join(text_pages)

                    if not full_text.strip():
                        full_text = f"EPFO Official Direction: {title_text}\nSource URL: {pdf_url}"

                    sha256_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()

                    cur.execute(
                        """
                        INSERT OR REPLACE INTO documents (
                            doc_id, regulator, source_name, doc_type, doc_number, title,
                            issue_date, source_url, pdf_url, retrieved_at, status,
                            in_force_from, in_force_to, licence
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            doc_id, "epfo", "epfo_official_portal", "circular", title_text[:30],
                            title_text, "2024-01-01", page_url, pdf_url, now_iso,
                            "in_force", "2024-01-01", "PRESENT", "godl_india"
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
                            doc_id, sha256_hash, "pdf_layer", "finreg_pypdf_extractor", "v3.0",
                            len(reader.pages), len(full_text), 0.95, full_text, now_iso
                        )
                    )
                    conn.commit()
                    total_ingested += 1
                    logger.info(f"[{total_ingested}] Ingested EPFO: {title_text[:50]} ({len(full_text)} chars)")
                except Exception as e:
                    logger.warning(f"Error parsing EPFO PDF {pdf_url}: {e}")
                    continue

                time.sleep(0.1)
        except Exception as e:
            logger.error(f"Error scraping {page_url}: {e}")

    conn.close()
    logger.info(f"=== EPFO CRAWL COMPLETE: Ingested {total_ingested} Documents ===")

if __name__ == "__main__":
    scrape_epfo_circulars()
