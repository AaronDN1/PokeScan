"""Deterministic OCR normalization for card names and collector numbers."""

from __future__ import annotations

import re
import unicodedata

_SPACE_PATTERN = re.compile(r"\s+")
_NUMBER_PATTERN = re.compile(r"(?P<number>[A-Z]*\d+[A-Z]*)\s*(?:[/|I]\s*(?P<total>\d+))?", re.I)
_SUFFIXES = (
    (re.compile(r"\bV\s*MAX\b", re.I), "VMAX"),
    (re.compile(r"\bV\s*STAR\b", re.I), "VSTAR"),
    (re.compile(r"\bG\s*X\b", re.I), "GX"),
    (re.compile(r"\bE\s*X\b", re.I), "ex"),
)


def normalize_card_name(raw: str) -> str:
    """Normalize OCR name text while preserving meaningful card suffixes."""
    value = unicodedata.normalize("NFKC", raw).strip()
    value = value.replace("0", "O")
    value = re.sub(r"[^\w\s.'-]", " ", value, flags=re.UNICODE)
    for pattern, replacement in _SUFFIXES:
        value = pattern.sub(replacement, value)
    return _SPACE_PATTERN.sub(" ", value).strip().casefold()


def normalize_collector_number(raw: str) -> str | None:
    """Extract and normalize the numerator portion of a collector number."""
    value = unicodedata.normalize("NFKC", raw).upper()
    match = _NUMBER_PATTERN.search(value)
    if not match:
        return None
    number = match.group("number").upper().lstrip("0")
    return number or "0"


def collector_similarity(observed: str | None, expected: str) -> float:
    """Score an observed collector number without fuzzy matching unrelated cards."""
    if not observed:
        return 0.0
    left = observed.casefold().lstrip("0")
    right = expected.casefold().lstrip("0")
    if left == right:
        return 1.0
    if left and right and (left in right or right in left):
        return 0.72
    return 0.0


def name_similarity(observed: str | None, expected: str) -> float:
    """Return a conservative token overlap score for a normalized name."""
    if not observed:
        return 0.0
    if observed == expected:
        return 1.0
    observed_tokens = set(observed.split())
    expected_tokens = set(expected.split())
    if not observed_tokens or not expected_tokens:
        return 0.0
    overlap = len(observed_tokens & expected_tokens)
    return overlap / max(len(observed_tokens), len(expected_tokens))
