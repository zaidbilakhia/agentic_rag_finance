"""Text cleaning and low-cost page filtering helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable

from src.config import MIN_PAGE_CHARS, USEFUL_KEYWORDS


WHITESPACE_RE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    """Normalize extracted PDF text while preserving readable paragraphs."""
    if not text:
        return ""
    text = text.replace("\x00", " ")
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip()


def contains_useful_keyword(
    text: str,
    keywords: Iterable[str] = USEFUL_KEYWORDS,
) -> bool:
    """Return True when a page contains at least one finance/risk keyword."""
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def is_useful_page(
    text: str,
    keywords: Iterable[str] = USEFUL_KEYWORDS,
    min_chars: int = MIN_PAGE_CHARS,
) -> bool:
    """Filter out tiny or irrelevant pages before embedding."""
    cleaned = clean_text(text)
    if len(cleaned) < min_chars:
        return False
    return contains_useful_keyword(cleaned, keywords)

