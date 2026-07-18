from app.application.normalization import (
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
    assert collector_similarity("6", "60") == 0.72
    assert collector_similarity("6", "151") == 0.0
    assert name_similarity("charizard ex", "charizard ex") == 1.0
    assert name_similarity("charizard", "charizard ex") == 0.5
