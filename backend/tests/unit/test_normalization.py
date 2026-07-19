import pytest

from app.application.normalization import (
    collector_number_alternatives,
    collector_similarity,
    name_similarity,
    normalize_card_name,
    normalize_collector_number,
)


def test_normalizes_known_suffix_spacing_and_case() -> None:
    assert normalize_card_name("  Pikachu V MAX ") == "pikachu vmax"
    assert normalize_card_name("Mew E X") == "mew ex"


def test_normalizes_collector_number_confusions() -> None:
    assert normalize_collector_number(" 006 / 165 ") == "6"
    assert normalize_collector_number("SV107|SV122") == "SV107"
    assert normalize_collector_number("not a number") is None


def test_similarity_is_conservative() -> None:
    assert collector_similarity("6", "006") == 1.0
    assert collector_similarity("6", "60") == 0.68
    assert collector_similarity("6", "151") == 0.0
    assert name_similarity("charizard ex", "charizard ex") == 1.0
    assert name_similarity("charizard", "charizard ex") == 0.7886


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("025/198", "25"),
        ("TG23/TG30", "TG23"),
        ("GG44/GG70", "GG44"),
        ("SV107/SV122", "SV107"),
        ("RC29/RC32", "RC29"),
        ("SWSH262", "SWSH262"),
        ("SM211", "SM211"),
        ("XY121", "XY121"),
        ("001", "1"),
    ],
)
def test_normalizes_supported_collector_formats(raw: str, expected: str) -> None:
    assert normalize_collector_number(raw) == expected


def test_generates_bounded_contextual_collector_alternatives() -> None:
    alternatives = collector_number_alternatives("SVO07/SV122")
    assert len(alternatives) <= 12
    assert any(item.startswith("SV") for item in alternatives)
