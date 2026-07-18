"""Unicode-safe OCR normalization and conservative catalog-aware alternatives."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

_SPACE_PATTERN = re.compile(r"\s+")
_COLLECTOR_PATTERN = re.compile(
    r"(?<![A-Z0-9])(?P<number>[A-Z0-9]{1,12})\s*(?:[/|]\s*(?P<total>[A-Z0-9]{1,12}))?",
    re.I,
)
_CANONICAL_COLLECTOR_PATTERN = re.compile(
    r"^(?P<prefix>[A-Z]*)(?P<digits>\d+)(?P<suffix>[A-Z]*)$"
)
_SUFFIX_REPLACEMENTS = (
    (re.compile(r"\bV\s*[- ]?\s*UNION\b", re.I), "V-UNION"),
    (re.compile(r"\bV\s*MAX\b", re.I), "VMAX"),
    (re.compile(r"\bV\s*STAR\b", re.I), "VSTAR"),
    (re.compile(r"\bG\s*X\b", re.I), "GX"),
    (re.compile(r"\bE\s*X\b", re.I), "ex"),
)
_KNOWN_SUFFIXES = ("v-union", "vmax", "vstar", "gx", "ex", "v", "break", "lv.x")
_NUMERIC_CONFUSIONS = {"O": "0", "I": "1", "L": "1", "S": "5", "B": "8", "Z": "2"}
_NAME_CONFUSIONS = {"0": ("o",), "1": ("i", "l"), "5": ("s",), "8": ("b",), "2": ("z",)}


@dataclass(frozen=True, slots=True)
class CollectorObservation:
    """A parsed collector numerator and optional printed denominator."""

    number: str
    total: str | None = None


def _clean_unicode(raw: str) -> str:
    value = unicodedata.normalize("NFKC", raw)
    return (
        value.replace("’", "'")
        .replace("‘", "'")
        .replace("–", "-")
        .replace("—", "-")
    )


def normalize_card_name(raw: str) -> str:
    """Normalize spacing and punctuation without erasing meaningful suffixes."""
    value = _clean_unicode(raw).strip()
    value = re.sub(r"(?<=[^\W\d_])0|0(?=[^\W\d_])", "O", value, flags=re.UNICODE)
    value = re.sub(r"[^\w\s.'\-♀♂]", " ", value, flags=re.UNICODE)
    for pattern, replacement in _SUFFIX_REPLACEMENTS:
        value = pattern.sub(replacement, value)
    return _SPACE_PATTERN.sub(" ", value).strip().casefold()


def name_alternatives(raw: str, *, limit: int = 16) -> tuple[str, ...]:
    """Generate bounded, context-aware name variants for common OCR confusions."""
    base = normalize_card_name(raw)
    if not base:
        return ()
    variants: list[str] = [base]
    for index, character in enumerate(base):
        replacements = _NAME_CONFUSIONS.get(character)
        if not replacements:
            continue
        left_is_letter = index > 0 and base[index - 1].isalpha()
        right_is_letter = index + 1 < len(base) and base[index + 1].isalpha()
        if not (left_is_letter or right_is_letter):
            continue
        for replacement in replacements:
            candidate = f"{base[:index]}{replacement}{base[index + 1:]}"
            if candidate not in variants:
                variants.append(candidate)
                if len(variants) >= limit:
                    return tuple(variants)
    return tuple(variants)


def _canonical_collector_token(token: str) -> str | None:
    cleaned = re.sub(r"[^A-Z0-9]", "", token.upper())
    if not cleaned or not any(character.isdigit() for character in cleaned):
        return None
    match = _CANONICAL_COLLECTOR_PATTERN.fullmatch(cleaned)
    if not match:
        return cleaned
    digits = match.group("digits").lstrip("0") or "0"
    return f"{match.group('prefix')}{digits}{match.group('suffix')}"


def parse_collector_number(raw: str) -> CollectorObservation | None:
    """Extract the first plausible collector number and its optional total."""
    value = _clean_unicode(raw).upper()
    for match in _COLLECTOR_PATTERN.finditer(value):
        number = _canonical_collector_token(match.group("number"))
        if number is None:
            continue
        total_raw = match.group("total")
        total = _canonical_collector_token(total_raw) if total_raw else None
        return CollectorObservation(number=number, total=total)
    return None


def normalize_collector_number(raw: str) -> str | None:
    """Return the canonical numerator portion of a collector number."""
    observation = parse_collector_number(raw)
    return observation.number if observation else None


def collector_number_alternatives(raw: str, *, limit: int = 24) -> tuple[str, ...]:
    """Generate bounded collector variants without globally rewriting identifiers."""
    value = _clean_unicode(raw).upper()
    match = next(
        (
            candidate
            for candidate in _COLLECTOR_PATTERN.finditer(value)
            if any(character.isdigit() for character in candidate.group("number"))
        ),
        None,
    )
    if match is None:
        return ()
    token = match.group("number")
    variants: list[str] = []

    def add(candidate: str) -> None:
        canonical = _canonical_collector_token(candidate)
        if canonical and canonical not in variants and len(variants) < limit:
            variants.append(canonical)

    add(token)
    frontier = [token]
    for _ in range(2):
        next_frontier: list[str] = []
        for candidate in frontier:
            for index, character in enumerate(candidate):
                replacement = _NUMERIC_CONFUSIONS.get(character)
                if replacement is None:
                    continue
                numeric_context = (
                    (index > 0 and candidate[index - 1].isdigit())
                    or (index + 1 < len(candidate) and candidate[index + 1].isdigit())
                    or not any(item.isdigit() for item in candidate[: index + 1])
                )
                if not numeric_context:
                    continue
                changed = f"{candidate[:index]}{replacement}{candidate[index + 1:]}"
                add(changed)
                next_frontier.append(changed)
                if len(variants) >= limit:
                    return tuple(variants)
        frontier = next_frontier
    return tuple(variants)


def collector_similarity(observed: str | None, expected: str) -> float:
    """Score collector identifiers with conservative edit tolerance."""
    if not observed:
        return 0.0
    left = _canonical_collector_token(observed)
    right = _canonical_collector_token(expected)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    ratio = SequenceMatcher(None, left, right).ratio()
    if ratio >= 0.88:
        return round(0.82 * ratio, 4)
    if left in right or right in left:
        return 0.68
    return 0.0


def name_similarity(observed: str | None, expected: str) -> float:
    """Combine character and token similarity for short card names."""
    if not observed:
        return 0.0
    left = normalize_card_name(observed)
    right = normalize_card_name(expected)
    if left == right:
        return 1.0
    if not left or not right:
        return 0.0
    character_ratio = SequenceMatcher(None, left, right).ratio()
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    token_ratio = len(left_tokens & right_tokens) / max(len(left_tokens), len(right_tokens))
    return round(max(character_ratio * 0.92, token_ratio * 0.88), 4)


def _suffix(value: str | None) -> str | None:
    if not value:
        return None
    normalized = normalize_card_name(value)
    return next((suffix for suffix in _KNOWN_SUFFIXES if normalized.endswith(f" {suffix}")), None)


def suffix_similarity(observed: str | None, expected: str) -> float:
    """Reward matching gameplay suffixes and penalize contradictory suffixes."""
    left = _suffix(observed)
    right = _suffix(expected)
    if left is None and right is None:
        return 1.0
    if left == right:
        return 1.0
    if left is None or right is None:
        return 0.45
    return 0.0
