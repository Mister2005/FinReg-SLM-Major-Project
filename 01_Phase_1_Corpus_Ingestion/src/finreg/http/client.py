from __future__ import annotations

import random
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
import structlog

from finreg.config import IdentityOverride
from finreg.http.robots import RobotsCache
from finreg.http.throttle import HostThrottle, host_of
from finreg.store.blobs import StoredBlob, write_blob
from finreg.store.failures import ReasonCode, record_failure
from pathlib import Path

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 5
_BACKOFF_BASE_SECONDS = 2.0
_BACKOFF_CAP_SECONDS = 120.0


class ClientConfigError(Exception):
    pass


class RetriesExhausted(Exception):
    def __init__(self, url: str, reason: ReasonCode) -> None:
        self.url = url
        self.reason = reason
        super().__init__(f"retries exhausted for {url}: {reason.value}")


@dataclass(frozen=True)
class HostPolicy:
    min_interval_seconds: float
    timeout_seconds: float = 60.0
    max_retries: int = _MAX_RETRIES


@dataclass(frozen=True)
class FetchResult:
    url: str
    final_url: str
    status: int
    headers: dict[str, str]
    body: bytes
    sha256: str
    retrieved_at: datetime
    from_cache: bool


def _classify_terminal_status(status: int) -> ReasonCode:
    if 400 <= status < 500:
        return ReasonCode.HTTP_4XX
    return ReasonCode.HTTP_5XX_EXHAUSTED


def _sleep_for_retry(attempt: int, retry_after: float | None) -> float:
    if retry_after is not None:
        return retry_after
    backoff = min(_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)), _BACKOFF_CAP_SECONDS)
    return random.uniform(0, backoff)


class Client:
    def __init__(
        self,
        *,
        contact_email: str,
        conn: sqlite3.Connection,
        blob_root: Path,
        source_name: str = "manual",
        transport: httpx.BaseTransport | None = None,
        throttle: HostThrottle | None = None,
        robots_cache: RobotsCache | None = None,
        sleep_fn: "callable[[float], None] | None" = None,
        identity_overrides: dict[str, IdentityOverride] | None = None,
    ) -> None:
        if not contact_email or not contact_email.strip():
            raise ClientConfigError("contact_email is required to construct a Client")

        self._contact_email = contact_email
        self._conn = conn
        self._blob_root = blob_root
        self._source_name = source_name
        self._user_agent = f"FinReg-SLM-Research/1.0 (academic corpus construction; {contact_email})"
        self._identity_overrides = identity_overrides or {}
        self._transport = transport
        self._throttle = throttle or HostThrottle()
        self._robots = robots_cache or RobotsCache(transport=transport, user_agent=self._user_agent)
        self._sleep = sleep_fn or time.sleep
        self._logger = structlog.get_logger()
        self._client = httpx.Client(transport=transport, http2=False, follow_redirects=True)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _conditional_headers(self, url: str) -> dict[str, str]:
        row = self._conn.execute(
            """
            SELECT etag, last_modified FROM fetches
            WHERE source_url = ? AND http_status < 400
            ORDER BY retrieved_at DESC LIMIT 1
            """,
            (url,),
        ).fetchone()
        headers: dict[str, str] = {}
        if row is None:
            return headers
        if row["etag"]:
            headers["If-None-Match"] = row["etag"]
        if row["last_modified"]:
            headers["If-Modified-Since"] = row["last_modified"]
        return headers

    def _record_fetch(
        self,
        *,
        source_url: str,
        final_url: str,
        status: int,
        headers: httpx.Headers,
        body: bytes | None,
        stored_blob: StoredBlob | None,
        from_cache: bool,
        retrieved_at: datetime,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO fetches
                (source_url, final_url, http_status, etag, last_modified, content_type,
                 byte_length, sha256, retrieved_at, from_cache, source_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_url,
                final_url,
                status,
                headers.get("etag"),
                headers.get("last-modified"),
                headers.get("content-type"),
                len(body) if body is not None else None,
                stored_blob.sha256 if stored_blob else None,
                retrieved_at.isoformat(),
                1 if from_cache else 0,
                self._source_name,
            ),
        )
        self._conn.commit()

    def _do_request(
        self,
        method: str,
        url: str,
        *,
        data: dict[str, str] | None,
        host_policy: HostPolicy,
        extra_headers: dict[str, str],
    ) -> FetchResult:
        self._robots.check(url)

        host = host_of(url)
        override = self._identity_overrides.get(host)
        if override is not None:
            self._logger.warning(
                "identity_override_used", host=host, reason=override.reason
            )
            user_agent = override.user_agent
        else:
            user_agent = self._user_agent
        headers = {"User-Agent": user_agent, **extra_headers}

        attempt = 0
        last_reason = ReasonCode.TIMEOUT_EXHAUSTED
        while attempt < host_policy.max_retries:
            attempt += 1
            self._throttle.wait(host, host_policy.min_interval_seconds)
            try:
                if method == "GET":
                    response = self._client.get(
                        url, headers=headers, timeout=host_policy.timeout_seconds
                    )
                else:
                    response = self._client.post(
                        url, data=data, headers=headers, timeout=host_policy.timeout_seconds
                    )
            except httpx.TransportError:
                # Covers TimeoutException, ConnectError, and transient
                # connection-level failures like RemoteProtocolError
                # ("server disconnected without sending a response") —
                # a live-crawl failure that crashed the whole process
                # instead of retrying (verified 2026-08-03, SEBI circular
                # fetch under sebi.gov.in).
                last_reason = ReasonCode.TIMEOUT_EXHAUSTED
                if attempt >= host_policy.max_retries:
                    break
                self._sleep(_sleep_for_retry(attempt, None))
                continue

            retrieved_at = datetime.now(timezone.utc)

            if response.status_code == 304:
                self._record_fetch(
                    source_url=url,
                    final_url=str(response.url),
                    status=304,
                    headers=response.headers,
                    body=None,
                    stored_blob=None,
                    from_cache=True,
                    retrieved_at=retrieved_at,
                )
                return FetchResult(
                    url=url,
                    final_url=str(response.url),
                    status=304,
                    headers=dict(response.headers),
                    body=b"",
                    sha256="",
                    retrieved_at=retrieved_at,
                    from_cache=True,
                )

            if response.status_code in _RETRYABLE_STATUS:
                last_reason = _classify_terminal_status(response.status_code)
                if attempt >= host_policy.max_retries:
                    break
                retry_after_header = response.headers.get("retry-after")
                retry_after = float(retry_after_header) if retry_after_header else None
                self._sleep(_sleep_for_retry(attempt, retry_after))
                continue

            if response.status_code >= 400:
                record_failure(
                    self._conn,
                    source_url=url,
                    source_name=self._source_name,
                    reason_code=ReasonCode.HTTP_4XX,
                    detail=f"status={response.status_code}",
                    attempts=attempt,
                )
                self._record_fetch(
                    source_url=url,
                    final_url=str(response.url),
                    status=response.status_code,
                    headers=response.headers,
                    body=response.content,
                    stored_blob=None,
                    from_cache=False,
                    retrieved_at=retrieved_at,
                )
                return FetchResult(
                    url=url,
                    final_url=str(response.url),
                    status=response.status_code,
                    headers=dict(response.headers),
                    body=response.content,
                    sha256="",
                    retrieved_at=retrieved_at,
                    from_cache=False,
                )

            stored_blob = write_blob(
                self._conn,
                self._blob_root,
                response.content,
                response.headers.get("content-type"),
            )
            self._record_fetch(
                source_url=url,
                final_url=str(response.url),
                status=response.status_code,
                headers=response.headers,
                body=response.content,
                stored_blob=stored_blob,
                from_cache=False,
                retrieved_at=retrieved_at,
            )
            return FetchResult(
                url=url,
                final_url=str(response.url),
                status=response.status_code,
                headers=dict(response.headers),
                body=response.content,
                sha256=stored_blob.sha256,
                retrieved_at=retrieved_at,
                from_cache=False,
            )

        record_failure(
            self._conn,
            source_url=url,
            source_name=self._source_name,
            reason_code=last_reason,
            detail=f"exhausted after {attempt} attempts",
            attempts=attempt,
        )
        raise RetriesExhausted(url, last_reason)

    def get(self, url: str, *, host_policy: HostPolicy) -> FetchResult:
        conditional_headers = self._conditional_headers(url)
        return self._do_request(
            "GET", url, data=None, host_policy=host_policy, extra_headers=conditional_headers
        )

    def post(
        self,
        url: str,
        data: dict[str, str],
        *,
        host_policy: HostPolicy,
        extra_headers: dict[str, str] | None = None,
    ) -> FetchResult:
        return self._do_request(
            "POST", url, data=data, host_policy=host_policy, extra_headers=extra_headers or {}
        )
