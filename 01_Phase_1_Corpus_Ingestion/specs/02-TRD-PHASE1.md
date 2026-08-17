# 02 — Technical Requirements, Phase 1

## Architecture

Five stages, each writing to the manifest, each independently resumable.

```
discover → fetch → extract → normalize+parse → resolve-temporal → export
```

Stages communicate only through the manifest and the blob store. No stage holds another stage's state in memory. This is what makes `SIGKILL` safe.

```
┌─────────────┐
│  sources/   │  one module per regulator; declares discovery strategy,
│             │  URL templates, listing parser, verify() health check
└──────┬──────┘
       │ yields DocumentRef(source_url, doc_meta)
┌──────▼──────┐
│  http/      │  single choke point: robots, throttle, retry, cache, UA
└──────┬──────┘
       │ yields FetchResult(bytes, headers, status)
┌──────▼──────┐
│  store/     │  blob write (content-addressed) + manifest row
└──────┬──────┘
       │
┌──────▼──────┐
│  extract/   │  router by content type → pdf | html | ocr; tables
└──────┬──────┘
       │
┌──────▼──────┐
│ normalize/  │  whitespace, ligatures, hyphenation, headers/footers,
│             │  document-number + citation parsing
└──────┬──────┘
       │
┌──────▼──────┐
│ temporal/   │  withdrawal lists, supersession graph, regime tagging
└──────┬──────┘
       │
┌──────▼──────┐
│  qa/ + export
└─────────────┘
```

## Technology decisions

| Concern | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Ecosystem for PDF and OCR; matches Phase 2. |
| Dependency management | `uv` with `pyproject.toml` | Fast, lockfile-based, reproducible. `pip` acceptable fallback. |
| HTTP | `httpx` (sync client, HTTP/2 off) | Explicit timeouts, clean redirect history. Wrapped, never used directly (I4). |
| Throttling | Custom token bucket per host in `http/throttle.py` | Needs per-host granularity; off-the-shelf limiters assume global. |
| robots.txt | `urllib.robotparser`, cached per host per run | Standard library, sufficient. |
| Manifest | SQLite with WAL mode | Single file, no server, transactional, queryable. Concurrency needs are low. |
| PDF text | `pypdfium2` primary, `pdfplumber` for tables | pdfium is fast and handles malformed files better than pypdf; pdfplumber's table extraction is the best available without Java. |
| PDF fallback | `pdftotext` (poppler-utils) via subprocess | Catches files pdfium mis-renders. Used when primary yields low character count but the page is not an image. |
| OCR | `ocrmypdf` (which wraps Tesseract and Ghostscript) | Produces a searchable PDF plus text, handles deskew and rasterisation. `-l eng`, `--skip-text`. |
| HTML | `selectolax` for parsing, custom boilerplate stripping | Faster than lxml, sufficient API. Generic extractors like trafilatura over-strip legal documents and drop numbered clauses; do not use them for primary source text. |
| Near-duplicate detection | MinHash LSH via `datasketch` | Standard, scales to the corpus size, tunable threshold. |
| Export | `pyarrow` Parquet, ZSTD compression | Columnar, partition-friendly, reads cleanly into Phase 2. |
| CLI | `typer` | Minimal boilerplate, generates help, testable. |
| Logging | `structlog` to JSONL | Machine-readable run logs for the QA report. |
| Tests | `pytest` with `respx` for HTTP mocking and committed fixture files | Never hit the network in tests. |

## Module contracts

### `finreg.http.client`

```python
class FetchResult:
    url: str
    final_url: str
    status: int
    headers: dict[str, str]
    body: bytes
    sha256: str
    retrieved_at: datetime
    from_cache: bool

class Client:
    def get(self, url: str, *, host_policy: HostPolicy) -> FetchResult: ...
    def post(self, url: str, data: dict, *, host_policy: HostPolicy) -> FetchResult: ...
```

Behaviour:
- Consults robots.txt for the host before the first request; a disallowed path raises `RobotsDisallowed` and is recorded as a skipped, not failed, fetch.
- Token bucket enforces `host_policy.min_interval_seconds`.
- Retries on 429, 500, 502, 503, 504 and on connection/read timeouts: 5 attempts, exponential backoff base 2 s, cap 120 s, full jitter. Honours `Retry-After` when present.
- Sends `User-Agent: FinReg-SLM-Research/1.0 (academic corpus construction; <contact-email>)`. The contact email is a required config value; the client refuses to start without it.
- Conditional requests: if the manifest has an `ETag` or `Last-Modified` for the URL, sends `If-None-Match` / `If-Modified-Since`. A 304 is a cache hit, recorded but producing no new blob.

### `finreg.sources.base`

```python
class Source(Protocol):
    name: str
    regulator: str

    def verify(self, client: Client) -> VerifyReport: ...
    def discover(self, client: Client, window: DateWindow) -> Iterator[DocumentRef]: ...
    def parse_listing_meta(self, raw: bytes) -> list[DocumentMeta]: ...
```

`verify()` asserts every structural assumption the module depends on — that a known listing page still returns the expected element, that a known document ID still resolves, that the record-count element is still parseable. It returns a report, and `finreg crawl` refuses to run a source whose `verify()` fails unless `--force` is given.

### `finreg.extract.router`

```python
def extract(blob_path: Path, content_type: str) -> ExtractionResult
```

Returns text, page count, per-page character counts, `text_source` ∈ {`pdf_layer`, `pdftotext`, `ocr`, `html`}, extractor name and version, tables as a list of row-lists, and a list of quality flags.

### `finreg.temporal.resolver`

Consumes the withdrawal and archive listings plus parsed citations, and writes `status`, `in_force_from`, `in_force_to`, `superseded_by` onto document rows. Runs as a separate stage so it can be re-run after new evidence arrives without re-crawling.

## Concurrency model

Per-host worker with concurrency 1; hosts run in parallel via a thread pool sized to the number of active sources (6). Extraction is CPU-bound and runs in a separate process pool sized to `os.cpu_count() - 1`, reading from the manifest work queue. Crawling and extraction can run simultaneously or as separate passes; both must produce identical results.

## Failure taxonomy

Every failure is classified into exactly one of these, stored in `fetch_failures.reason_code`:

| Code | Meaning | Retry? |
|---|---|---|
| `http_4xx` | Terminal client error other than 429 | No |
| `http_5xx_exhausted` | Server error after all retries | Manual |
| `timeout_exhausted` | Network timeout after all retries | Manual |
| `robots_disallowed` | Path disallowed | No |
| `content_type_unexpected` | Fetched, but not a document type we handle | No |
| `pdf_corrupt` | Bytes retrieved but no extractor could open the file | Manual |
| `extraction_empty` | Opened but yielded no usable text, including after OCR | Manual |
| `listing_parse_failed` | Listing page structure changed | Blocks source |

There is no `unknown` code. An unclassifiable failure is a bug in the classifier and must be fixed.

## Configuration shape (`config/sources.yaml`)

```yaml
contact_email: "REQUIRED — set before first run"
window:
  start: "2016-04-01"
  end: null            # null means "today"
defaults:
  min_interval_seconds: 2.0
  max_retries: 5
  timeout_seconds: 60
  max_failure_rate: 0.02
sources:
  rbi_notifications:
    enabled: true
    host: "www.rbi.org.in"
    strategy: "id_enumeration"
    min_interval_seconds: 2.0
  sebi_circulars:
    enabled: true
    host: "www.sebi.gov.in"
    strategy: "paginated_post"
  # ... see 03-DATA-SOURCES.md for the full set
```

No source endpoint appears anywhere in `src/`. All of them live here.
