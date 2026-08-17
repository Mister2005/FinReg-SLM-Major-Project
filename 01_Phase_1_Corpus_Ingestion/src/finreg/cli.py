from __future__ import annotations

import sqlite3
import subprocess
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import typer

from finreg.config import Config, ConfigError, load_config
from finreg.http.client import Client, HostPolicy
from finreg.logging import configure_logging, get_logger
from finreg.store.manifest import open_manifest

app = typer.Typer(no_args_is_help=True, add_completion=False)
sources_app = typer.Typer(no_args_is_help=True, add_completion=False)
app.add_typer(sources_app, name="sources")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CONFIG_PATH = _REPO_ROOT / "config" / "sources.yaml"
_DEFAULT_MANIFEST_PATH = _REPO_ROOT / "data" / "manifest.db"
_DEFAULT_BLOB_ROOT = _REPO_ROOT / "data" / "raw"
_DEFAULT_LOG_DIR = _REPO_ROOT / "reports" / "logs"

_DEFAULT_EXPORT_DIR = _REPO_ROOT / "data" / "export"
_DEFAULT_REPORTS_DIR = _REPO_ROOT / "reports"


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _load_config_or_exit(config_path: Path) -> Config:
    try:
        return load_config(config_path)
    except ConfigError as exc:
        typer.secho(f"Config error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc


def _open_crawl_run(command: str, config: Config) -> tuple[str, "sqlite3.Connection"]:
    conn = open_manifest(_DEFAULT_MANIFEST_PATH)
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO crawl_runs (run_id, started_at, finished_at, git_commit, config_sha256, command, exit_status)
        VALUES (?, ?, NULL, ?, ?, ?, NULL)
        """,
        (run_id, started_at, _git_commit(), config.sha256, command),
    )
    conn.commit()
    configure_logging(run_id, _DEFAULT_LOG_DIR)
    return run_id, conn


def _close_crawl_run(conn: "sqlite3.Connection", run_id: str, exit_status: str) -> None:
    conn.execute(
        "UPDATE crawl_runs SET finished_at = ?, exit_status = ? WHERE run_id = ?",
        (datetime.now(timezone.utc).isoformat(), exit_status, run_id),
    )
    conn.commit()
    conn.close()


def _run_tracked_command(command: str, body: "callable[[str, sqlite3.Connection, Config], None]") -> None:
    config = _load_config_or_exit(_DEFAULT_CONFIG_PATH)
    run_id, conn = _open_crawl_run(command, config)
    logger = get_logger()
    try:
        body(run_id, conn, config)
        _close_crawl_run(conn, run_id, "success")
    except typer.Exit as exc:
        _close_crawl_run(conn, run_id, f"exit_code_{exc.exit_code}")
        raise
    except Exception as exc:
        logger.error("command_failed", command=command, error=str(exc))
        _close_crawl_run(conn, run_id, "failed")
        raise


@app.command()
def fetch(url: str) -> None:
    def _body(run_id: str, conn, config: Config) -> None:
        blob_root = _DEFAULT_BLOB_ROOT
        with Client(
            contact_email=config.contact_email,
            conn=conn,
            blob_root=blob_root,
            source_name="manual",
            identity_overrides=config.identity_overrides,
        ) as client:
            result = client.get(
                url, host_policy=HostPolicy(min_interval_seconds=config.defaults.min_interval_seconds)
            )
        if result.from_cache:
            typer.echo(f"304 Not Modified (cache hit): {url}")
        else:
            typer.echo(f"{result.status} {url} -> sha256={result.sha256}")

    _run_tracked_command("fetch", _body)


@sources_app.command("verify")
def sources_verify() -> None:
    import finreg.sources.cbdt  # noqa: F401  (registers the CBDT source)
    import finreg.sources.cbic  # noqa: F401  (registers the CBIC source)
    import finreg.sources.indiacode  # noqa: F401  (registers the India Code source)
    import finreg.sources.meity  # noqa: F401  (registers the MeitY source)
    import finreg.sources.rbi  # noqa: F401  (registers the RBI source)
    import finreg.sources.sebi  # noqa: F401  (registers the SEBI source)
    from finreg.sources.registry import get_enabled_sources

    config = _load_config_or_exit(_DEFAULT_CONFIG_PATH)
    conn = open_manifest(_DEFAULT_MANIFEST_PATH)
    enabled = get_enabled_sources(config)

    if not enabled:
        typer.echo("No enabled sources with a registered implementation.")
        raise typer.Exit(code=0)

    with Client(
        contact_email=config.contact_email,
        conn=conn,
        blob_root=_DEFAULT_BLOB_ROOT,
        source_name="verify",
        identity_overrides=config.identity_overrides,
    ) as client:
        all_ok = True
        for name, source in enabled.items():
            report = source.verify(client)
            status = "OK" if report.ok else "FAIL"
            typer.echo(f"[{status}] {name} (access_method={report.access_method}): {report.detail}")
            if not report.ok:
                all_ok = False

    conn.close()
    raise typer.Exit(code=0 if all_ok else 1)


@app.command()
def crawl(
    source: str = typer.Option(None, "--source", help="Crawl only this source; default: all enabled sources"),
    max_ids: int = typer.Option(None, "--max-ids", help="Cap RBI ID enumeration to this many IDs"),
    max_pages: int = typer.Option(None, "--max-pages", help="Cap SEBI-style pagination to this many pages"),
) -> None:
    import finreg.sources.cbdt  # noqa: F401
    import finreg.sources.cbic  # noqa: F401
    import finreg.sources.indiacode  # noqa: F401
    import finreg.sources.meity  # noqa: F401
    import finreg.sources.rbi  # noqa: F401
    import finreg.sources.sebi  # noqa: F401
    from finreg.orchestrate import CRAWL_WRAPPERS, crawl_source, extract_pending_documents
    from finreg.sources.registry import get_enabled_sources
    from finreg.temporal.regime import tag_direct_tax_documents
    from finreg.temporal.resolver import resolve as run_resolve

    def _body(run_id: str, conn, config: Config) -> None:
        enabled = get_enabled_sources(config)
        targets = [source] if source else list(enabled.keys())

        with Client(
            contact_email=config.contact_email, conn=conn, blob_root=_DEFAULT_BLOB_ROOT,
            source_name="crawl", identity_overrides=config.identity_overrides,
        ) as client:
            policy = HostPolicy(min_interval_seconds=config.defaults.min_interval_seconds)
            for name in targets:
                if name not in enabled or name not in CRAWL_WRAPPERS:
                    continue
                limit = max_ids if name == "rbi_notifications" else max_pages
                window_start = date.fromisoformat(config.window.start)
                result = crawl_source(name, client, conn, policy, limit, window_start)
                typer.echo(f"[{result.source_name}] documents_touched={result.documents_touched}")

        extracted = extract_pending_documents(conn, _REPO_ROOT / "data" / "work" / "ocr")
        typer.echo(f"texts_extracted={extracted}")

        summary = run_resolve(conn)
        tagged = tag_direct_tax_documents(conn)
        typer.echo(
            f"resolve: withdrawn={summary.withdrawn_from_listings} "
            f"superseded={summary.superseded_from_citations} cycles={summary.cycles_detected} "
            f"direct_tax_tagged={tagged}"
        )

    _run_tracked_command("crawl", _body)


@app.command()
def extract() -> None:
    from finreg.orchestrate import extract_pending_documents

    def _body(run_id: str, conn, config: Config) -> None:
        count = extract_pending_documents(conn, _REPO_ROOT / "data" / "work" / "ocr")
        typer.echo(f"texts_extracted={count}")

    _run_tracked_command("extract", _body)


@app.command()
def resolve() -> None:
    from finreg.temporal.regime import tag_direct_tax_documents
    from finreg.temporal.resolver import resolve as run_resolve

    def _body(run_id: str, conn, config: Config) -> None:
        summary = run_resolve(conn)
        tagged = tag_direct_tax_documents(conn)
        typer.echo(f"withdrawn_from_listings={summary.withdrawn_from_listings}")
        typer.echo(f"superseded_from_citations={summary.superseded_from_citations}")
        typer.echo(f"in_force_from_defaulted={summary.in_force_from_defaulted}")
        typer.echo(f"cycles_detected={summary.cycles_detected}")
        typer.echo(f"direct_tax_documents_tagged={tagged}")

    _run_tracked_command("resolve", _body)


@app.command()
def dedup() -> None:
    from finreg.dedup.minhash import run_dedup
    from finreg.qa.flags import set_duplicate_non_canonical_flags

    def _body(run_id: str, conn, config: Config) -> None:
        cluster_count = run_dedup(conn)
        flagged = set_duplicate_non_canonical_flags(conn)
        typer.echo(f"clusters={cluster_count} non_canonical_flagged={flagged}")

    _run_tracked_command("dedup", _body)


@app.command()
def export() -> None:
    from finreg.export.parquet import export as run_export

    def _body(run_id: str, conn, config: Config) -> None:
        result = run_export(
            conn, _DEFAULT_EXPORT_DIR, _REPO_ROOT, config.sha256, config.window.start
        )
        typer.echo(f"corpus={result.corpus_count} corpus_clean={result.corpus_clean_count} "
                    f"corpus_in_force={result.corpus_in_force_count}")
        typer.echo(f"corpus_card={result.corpus_card_path}")

    _run_tracked_command("export", _body)


@app.command()
def report() -> None:
    from finreg.qa.report import generate_html, generate_markdown

    def _body(run_id: str, conn, config: Config) -> None:
        markdown_text = generate_markdown(conn)
        html_text = generate_html(markdown_text)
        _DEFAULT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        md_path = _DEFAULT_REPORTS_DIR / "qa-report.md"
        html_path = _DEFAULT_REPORTS_DIR / "qa-report.html"
        md_path.write_text(markdown_text, encoding="utf-8")
        html_path.write_text(html_text, encoding="utf-8")
        typer.echo(f"wrote {md_path}")
        typer.echo(f"wrote {html_path}")

    _run_tracked_command("report", _body)


qa_app = typer.Typer(no_args_is_help=True, add_completion=False)
app.add_typer(qa_app, name="qa")


@qa_app.command("sample")
def qa_sample(seed: int = typer.Option(..., "--seed")) -> None:
    from finreg.qa.sample import write_audit_worksheet

    def _body(run_id: str, conn, config: Config) -> None:
        out_path = _DEFAULT_REPORTS_DIR / f"audit-{datetime.now(timezone.utc).strftime('%Y%m%d')}.md"
        count = write_audit_worksheet(conn, seed, out_path)
        typer.echo(f"wrote {count}-document audit worksheet to {out_path}")

    _run_tracked_command("qa sample", _body)


@qa_app.command("gate")
def qa_gate() -> None:
    from finreg.qa.gate import run_gate

    def _body(run_id: str, conn, config: Config) -> None:
        results = run_gate(
            conn, _DEFAULT_EXPORT_DIR, _DEFAULT_REPORTS_DIR, _REPO_ROOT, config.sha256, config.window.start
        )
        all_passed = True
        for r in results:
            status = "PASS" if r.passed else "FAIL"
            typer.echo(f"[{status}] {r.ac_id} {r.name}: {r.measured}")
            if r.detail:
                typer.echo(f"        {r.detail}")
            if not r.passed:
                all_passed = False
        if not all_passed:
            raise typer.Exit(code=1)

    _run_tracked_command("qa gate", _body)


if __name__ == "__main__":
    app()
