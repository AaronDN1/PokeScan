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


def test_condition_prices_and_resolved_product_link_are_exposed() -> None:
    card = Card(
        id="tcgdex:en:basep:basep-1",
        name="Pikachu",
        normalized_name="pikachu",
        collector_number="1",
        normalized_collector_number="1",
        printed_total="53",
        source="tcgdex",
        source_card_id="basep-1",
        set_id="basep",
        set_name="Wizards Black Star Promos",
        rarity="Common",
        language="en",
        image_url="https://example.com/card.webp",
        marketplace_url=None,
    )
    price = Price(
        amount=12.5,
        source="tcgplayer_api",
        near_mint=12.5,
        lightly_played=10.25,
        moderately_played=8.0,
        product_id="121772",
        marketplace_url="https://www.tcgplayer.com/product/121772",
        printing_name="Normal",
    )

    response = CardResponse.from_domain(card, price)

    assert response.marketplace_url == "https://www.tcgplayer.com/product/121772"
    assert response.price.near_mint == 12.5
    assert response.price.lightly_played == 10.25
    assert response.price.moderately_played == 8.0
    assert response.price.price_status == "available"
