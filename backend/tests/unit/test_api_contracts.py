from app.api.schemas import CardResponse
from app.domain.models import Card, Price


def test_nullable_marketplace_and_unavailable_price_are_valid() -> None:
    card = Card(
        id="tcgdex:en:test:test-1",
        name="Pikachu",
        normalized_name="pikachu",
        collector_number="1",
        normalized_collector_number="1",
        printed_total=None,
        source="tcgdex",
        source_card_id="test-1",
        set_id="test",
        set_name="Test",
        rarity=None,
        language="en",
        image_url="https://example.com/card.webp",
        marketplace_url=None,
    )
    response = CardResponse.from_domain(card, Price(amount=None))
    assert response.marketplace_url is None
    assert response.price.amount is None
    assert response.price.price_status == "unavailable"
