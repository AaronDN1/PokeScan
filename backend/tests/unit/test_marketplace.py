from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.models import Card
from app.infrastructure.database.models import Base, CardRecord
from app.infrastructure.marketplace.provider import CachedMarketplacePriceProvider
from app.infrastructure.marketplace.tcgplayer import (
    PokemonTcgMarketplaceResolver,
    TcgPlayerConditionClient,
)


def _card() -> Card:
    return Card(
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
        image_url="https://example.com/basep-1.webp",
    )


async def test_resolver_returns_a_canonical_exact_product_link() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.pokemontcg.io":
            return httpx.Response(
                200,
                json={
                    "data": {
                        "id": "basep-1",
                        "name": "Pikachu",
                        "number": "1",
                        "set": {"name": "Wizards Black Star Promos"},
                        "tcgplayer": {
                            "url": "https://prices.pokemontcg.io/tcgplayer/basep-1",
                            "updatedAt": "2026/07/17",
                            "prices": {"normal": {"market": 31.45}},
                        },
                    }
                },
            )
        assert request.url.host == "prices.pokemontcg.io"
        return httpx.Response(
            302,
            headers={
                "location": (
                    "https://www.tcgplayer.com/product/121772/pokemon-wotc-promo-"
                    "pikachu?Language=English"
                )
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    resolver = PokemonTcgMarketplaceResolver(client=client)
    try:
        mapping = await resolver.resolve(_card())
    finally:
        await client.aclose()

    assert mapping.product_id == "121772"
    assert mapping.product_url == "https://www.tcgplayer.com/product/121772"
    assert mapping.market_price == 31.45
    assert mapping.printing_hint == "Normal"


async def test_approved_tcgplayer_client_returns_nm_lp_and_mp_market_prices() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
        assert request.headers["authorization"] == "bearer token"
        responses: dict[str, dict[str, Any]] = {
            "/v1.39.0/catalog/products/121772/skus": {
                "results": [
                    {"skuId": 101, "languageId": 1, "conditionId": 1, "printingId": 1},
                    {"skuId": 102, "languageId": 1, "conditionId": 2, "printingId": 1},
                    {"skuId": 103, "languageId": 1, "conditionId": 3, "printingId": 1},
                ]
            },
            "/v1.39.0/catalog/printings": {
                "results": [{"printingId": 1, "name": "Normal"}]
            },
            "/v1.39.0/pricing/sku/101,102,103": {
                "results": [
                    {"skuId": 101, "marketPrice": 31.45},
                    {"skuId": 102, "marketPrice": 24.0},
                    {"skuId": 103, "marketPrice": 18.75},
                ]
            },
        }
        return httpx.Response(200, json=responses[request.url.path])

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    tcgplayer = TcgPlayerConditionClient(
        public_key="public",
        private_key="private",
        api_version="v1.39.0",
        client=client,
    )
    try:
        prices = await tcgplayer.get_condition_prices("121772", preferred_printing="Normal")
    finally:
        await client.aclose()

    assert prices is not None
    assert prices.near_mint == 31.45
    assert prices.lightly_played == 24.0
    assert prices.moderately_played == 18.75
    assert prices.printing_name == "Normal"


async def test_marketplace_provider_caches_mapping_without_condition_credentials() -> None:
    request_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if request.url.host == "api.pokemontcg.io":
            return httpx.Response(
                200,
                json={
                    "data": {
                        "id": "basep-1",
                        "name": "Pikachu",
                        "number": "1",
                        "set": {"name": "Wizards Black Star Promos"},
                        "tcgplayer": {
                            "url": "https://prices.pokemontcg.io/tcgplayer/basep-1",
                            "updatedAt": "2026/07/17",
                            "prices": {"normal": {"market": 31.45}},
                        },
                    }
                },
            )
        return httpx.Response(
            302,
            headers={"location": "https://www.tcgplayer.com/product/121772"},
        )

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    card = _card()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        session.add(
            CardRecord(
                id=card.id,
                name=card.name,
                normalized_name=card.normalized_name,
                collector_number=card.collector_number,
                normalized_collector_number=card.normalized_collector_number,
                printed_total=card.printed_total,
                source=card.source,
                source_card_id=card.source_card_id,
                set_id=card.set_id,
                set_name=card.set_name,
                rarity=card.rarity,
                language=card.language,
                reference_image_url=card.image_url,
                marketplace_id=None,
                marketplace_url=None,
                reference_asset=None,
                perceptual_hash=None,
                orb_descriptors=None,
                visual_embedding=None,
            )
        )
        await session.commit()
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CachedMarketplacePriceProvider(
        sessions,
        PokemonTcgMarketplaceResolver(client=client),
        TcgPlayerConditionClient(
            public_key=None,
            private_key=None,
            api_version="v1.39.0",
            client=client,
        ),
    )
    try:
        first = await provider.get_price(card)
        second = await provider.get_price(card)
    finally:
        await client.aclose()
        await engine.dispose()

    assert first.marketplace_url == "https://www.tcgplayer.com/product/121772"
    assert first.amount == 31.45
    assert first.near_mint is None
    assert second == first
    assert request_count == 2
