from __future__ import annotations

import structlog
import httpx
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser


class RobotsDisallowed(Exception):
    def __init__(self, url: str) -> None:
        self.url = url
        super().__init__(f"robots.txt disallows: {url}")


class RobotsCache:
    def __init__(self, transport: httpx.BaseTransport | None = None, user_agent: str = "*") -> None:
        self._parsers: dict[str, RobotFileParser] = {}
        self._transport = transport
        self._user_agent = user_agent
        self._logger = structlog.get_logger()

    def _fetch_robots_text(self, robots_url: str) -> str | None:
        try:
            with httpx.Client(transport=self._transport, timeout=10.0) as client:
                response = client.get(robots_url)
            if response.status_code >= 400:
                return None
            return response.text
        except httpx.HTTPError:
            return None

    def _parser_for_host(self, url: str) -> RobotFileParser:
        parsed = urlparse(url)
        host = parsed.netloc
        if host in self._parsers:
            return self._parsers[host]

        robots_url = f"{parsed.scheme}://{host}/robots.txt"
        parser = RobotFileParser()
        parser.set_url(robots_url)

        text = self._fetch_robots_text(robots_url)
        if text is None:
            self._logger.warning("robots_txt_unreachable", host=host)
            parser.parse([])
        else:
            parser.parse(text.splitlines())

        self._parsers[host] = parser
        return parser

    def check(self, url: str) -> None:
        parser = self._parser_for_host(url)
        if not parser.can_fetch(self._user_agent, url):
            raise RobotsDisallowed(url)
