from __future__ import annotations

import threading
import time
from urllib.parse import urlparse


class HostThrottle:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_request_at: dict[str, float] = {}
        self._host_locks: dict[str, threading.Lock] = {}

    def _lock_for_host(self, host: str) -> threading.Lock:
        with self._lock:
            if host not in self._host_locks:
                self._host_locks[host] = threading.Lock()
            return self._host_locks[host]

    def wait(self, host: str, min_interval_seconds: float) -> None:
        host_lock = self._lock_for_host(host)
        with host_lock:
            last = self._last_request_at.get(host)
            now = time.monotonic()
            if last is not None:
                elapsed = now - last
                remaining = min_interval_seconds - elapsed
                if remaining > 0:
                    time.sleep(remaining)
            self._last_request_at[host] = time.monotonic()


def host_of(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc
