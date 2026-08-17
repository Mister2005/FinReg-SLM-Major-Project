from __future__ import annotations

import re
from dataclasses import dataclass

from selectolax.parser import HTMLParser

EXTRACTOR_VERSION_HTML = "selectolax-0.3.21-r1"

_BOILERPLATE_TEXT_PATTERNS = (
    re.compile(r"^more links$", re.IGNORECASE),
    re.compile(r"^follow rbi$", re.IGNORECASE),
    re.compile(r"^skip to main content$", re.IGNORECASE),
    re.compile(r"^print$", re.IGNORECASE),
)
_BOILERPLATE_TAGS = ("nav", "script", "style", "footer", "header")


@dataclass(frozen=True)
class HtmlExtractionResult:
    text: str
    char_count: int
    extractor: str
    extractor_version: str


def _is_boilerplate_node(node) -> bool:
    text = node.text(deep=False, strip=True) if node.text else ""
    return any(pattern.match(text) for pattern in _BOILERPLATE_TEXT_PATTERNS)


def extract_html(html: bytes | str, content_selector: str) -> HtmlExtractionResult:
    tree = HTMLParser(html)

    for tag in _BOILERPLATE_TAGS:
        for node in tree.css(tag):
            node.decompose()

    content_nodes = tree.css(content_selector)
    if not content_nodes:
        return HtmlExtractionResult(
            text="", char_count=0, extractor="selectolax", extractor_version=EXTRACTOR_VERSION_HTML
        )

    lines: list[str] = []
    for content_node in content_nodes:
        for descendant in content_node.css("nav, script, style, .navigation, .breadcrumb"):
            descendant.decompose()
        for el in content_node.css("h1, h2, h3, h4, h5, h6, p, li, td, th, pre"):
            text = el.text(deep=True, separator=" ").strip()
            text = re.sub(r"\s+", " ", text)
            if not text:
                continue
            if any(pattern.match(text) for pattern in _BOILERPLATE_TEXT_PATTERNS):
                continue
            lines.append(text)

    body_text = "\n".join(lines)
    return HtmlExtractionResult(
        text=body_text,
        char_count=len(body_text),
        extractor="selectolax",
        extractor_version=EXTRACTOR_VERSION_HTML,
    )
