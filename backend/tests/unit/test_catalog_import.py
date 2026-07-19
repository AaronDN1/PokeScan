from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.infrastructure.database.models import CardRecord
from scripts.import_catalog import import_catalog


def _card(card_id: str, number: str) -> dict[str, object]:
    return {
        "id": card_id,
        "source": "tcgdex",
        "source_card_id": card_id.rsplit(":", 1)[-1],
        "set_id": "basep",
        "name": "Pikachu",
        "normalized_name": "PIKACHU",
        "collector_number": number,
        "normalized_collector_number": number,
        "printed_total": "53",
        "set_name": "Wizards Black Star Promos",
        "rarity": None,
        "language": "English",
        "reference_image_url": f"https://example.test/{number}/high.webp",
    }


@pytest.mark.asyncio
async def test_import_replaces_stale_cards_in_the_same_catalog_scope(tmp_path: Path) -> None:
    database = tmp_path / "catalog.db"
    database_url = f"sqlite+aiosqlite:///{database.as_posix()}"
    catalog = tmp_path / "catalog.json"
    first = _card("tcgdex:en:basep:basep-1", "1")
    stale = _card("tcgdex:en:basep:basep-2", "2")
    catalog.write_text(json.dumps({"cards": [first, stale]}), encoding="utf-8")
    assert await import_catalog(catalog, database_url=database_url) == 2

    catalog.write_text(json.dumps({"cards": [first]}), encoding="utf-8")
    assert await import_catalog(catalog, database_url=database_url) == 1

    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine)
    async with sessions() as session:
        count = await session.scalar(select(func.count(CardRecord.id)))
        remaining = await session.scalar(select(CardRecord.id))
    await engine.dispose()

    assert count == 1
    assert remaining == "tcgdex:en:basep:basep-1"
