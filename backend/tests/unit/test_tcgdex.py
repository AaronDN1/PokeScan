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
