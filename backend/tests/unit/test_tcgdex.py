from typing import Any

import httpx

from app.infrastructure.catalog.tcgdex import TcgDexCatalogProvider, TcgDexOptions


class _PaginatedProvider(TcgDexCatalogProvider):
    def __init__(self) -> None:
        super().__init__(TcgDexOptions(page_size=100))
        self.requested_page_sizes: list[int] = []

    async def _get_json(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        params: dict[str, int] | None = None,
    ) -> Any:
        del client, url
        assert params is not None
        page = params["pagination:page"]
        per_page = params["pagination:itemsPerPage"]
        self.requested_page_sizes.append(per_page)
        offset = (page - 1) * per_page
        return [{"id": f"card-{index}"} for index in range(offset, offset + per_page)]


async def test_partial_limit_does_not_change_page_size_and_overlap_results() -> None:
    provider = _PaginatedProvider()

    cards = await provider._list_cards(limit=250)

    assert provider.requested_page_sizes == [100, 100, 100]
    assert len(cards) == 250
    assert len({card["id"] for card in cards}) == 250


def test_fast_summary_catalog_keeps_physical_cards_and_excludes_tcg_pocket() -> None:
    provider = TcgDexCatalogProvider(TcgDexOptions())
    sets = {
        "sv01": {
            "id": "sv01",
            "name": "Scarlet & Violet",
            "cardCount": {"official": 198},
        }
    }
    physical = provider._normalize_brief(
        {
            "id": "sv01-025",
            "localId": "025",
            "name": "Pikachu",
            "image": "https://assets.tcgdex.net/en/sv/sv01/025",
        },
        sets,
    )
    pocket = provider._normalize_brief(
        {
            "id": "A1-001",
            "localId": "001",
            "name": "Bulbasaur",
            "image": "https://assets.tcgdex.net/en/tcgp/A1/001",
        },
        {},
    )

    assert physical is not None
    assert physical["set_name"] == "Scarlet & Violet"
    assert physical["normalized_collector_number"] == "25"
    assert pocket is None
