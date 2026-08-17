from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

_LIGATURES = {
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬀ": "ff",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
}

_CURLY_QUOTES = {
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
}

_CHARSPACE_LINE = re.compile(r"^(?:\S(?: \S)*\s*)+$")
_CHARSPACE_TOKEN = re.compile(r"(?:\S ){2,}\S")

_PAGE_NUMBER_LINE = re.compile(r"^\s*\d+\s*$")
_HYPHEN_BREAK = re.compile(r"(\w+)-\n(\w+)")


@dataclass(frozen=True)
class NormalizationResult:
    text: str
    flags: list[str] = field(default_factory=list)


def _step_nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def _step_ligatures(text: str) -> str:
    for ligature, replacement in _LIGATURES.items():
        text = text.replace(ligature, replacement)
    return text


def _step_quotes_and_dashes(text: str) -> str:
    for curly, straight in _CURLY_QUOTES.items():
        text = text.replace(curly, straight)
    return text


def _is_charspaced_line(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) < 6:
        return False
    tokens = stripped.split(" ")
    single_char_tokens = sum(1 for t in tokens if len(t) == 1)
    return len(tokens) > 0 and (single_char_tokens / len(tokens)) > 0.4


def _collapse_charspaced_line(line: str) -> str:
    leading_ws = line[: len(line) - len(line.lstrip())]
    stripped = line.strip()
    words = []
    current = []
    for token in stripped.split(" "):
        if token == "":
            if current:
                words.append("".join(current))
                current = []
            continue
        if len(token) == 1:
            current.append(token)
        else:
            if current:
                words.append("".join(current))
                current = []
            words.append(token)
    if current:
        words.append("".join(current))
    return leading_ws + " ".join(words)


def _step_charspace_repair(text: str) -> tuple[str, bool]:
    lines = text.split("\n")
    fired = False
    out_lines = []
    for line in lines:
        if _is_charspaced_line(line):
            out_lines.append(_collapse_charspaced_line(line))
            fired = True
        else:
            out_lines.append(line)
    return "\n".join(out_lines), fired


_COMMON_WORDS = {
    "the", "and", "of", "to", "in", "a", "is", "for", "on", "with",
    "regulation", "circular", "notification", "shall", "under", "act",
}


def _step_dehyphenate(text: str) -> str:
    def _join(match: re.Match) -> str:
        prefix, suffix = match.group(1), match.group(2)
        if prefix.lower() in _COMMON_WORDS:
            return match.group(0)
        return f"{prefix}{suffix}"

    return _HYPHEN_BREAK.sub(_join, text)


def _step_remove_header_footer(text: str, boilerplate_lines: set[str]) -> str:
    lines = text.split("\n")
    out_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped in boilerplate_lines:
            continue
        if _PAGE_NUMBER_LINE.match(line):
            continue
        out_lines.append(line)
    return "\n".join(out_lines)


def _step_collapse_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text)


def _step_strip_known_boilerplate(text: str, boilerplate_strings: tuple[str, ...]) -> str:
    for s in boilerplate_strings:
        text = text.replace(s, "")
    return text


def normalize(
    text: str,
    *,
    repeated_header_footer_lines: set[str] | None = None,
    known_boilerplate_strings: tuple[str, ...] = (),
) -> NormalizationResult:
    flags: list[str] = []

    text = _step_nfkc(text)
    text = _step_ligatures(text)
    text = _step_quotes_and_dashes(text)

    text, charspace_fired = _step_charspace_repair(text)
    if charspace_fired:
        flags.append("charspace_repaired")

    text = _step_dehyphenate(text)
    text = _step_remove_header_footer(text, repeated_header_footer_lines or set())
    text = _step_collapse_blank_lines(text)
    text = _step_strip_known_boilerplate(text, known_boilerplate_strings)

    return NormalizationResult(text=text, flags=flags)


def detect_repeated_header_footer_lines(pages: list[str], threshold: float = 0.6) -> set[str]:
    if not pages:
        return set()
    line_page_counts: dict[str, int] = {}
    for page in pages:
        first_last = set()
        lines = [l.strip() for l in page.split("\n") if l.strip()]
        if lines:
            first_last.add(lines[0])
            first_last.add(lines[-1])
        for line in first_last:
            line_page_counts[line] = line_page_counts.get(line, 0) + 1

    min_pages = max(1, int(len(pages) * threshold))
    return {line for line, count in line_page_counts.items() if count >= min_pages}
