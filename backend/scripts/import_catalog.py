"""Import normalized card and cached price records from a versioned JSON export."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.infrastructure.database.models import Base, CardRecord, PriceRecord


def _embedding_bytes(values: list[float] | None) -> bytes | None:
    return np.asarray(values, dtype=np.float32).tobytes() if values else None


async def import_catalog(path: Path) -> None:
    """Upsert card records and their optional cached prices."""
    payload: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    engine = create_async_engine(get_settings().database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        for item in payload:
            record = CardRecord(
                id=item["id"],
                name=item["name"],
                normalized_name=item["normalized_name"],
                collector_number=item["collector_number"],
                printed_total=item.get("printed_total"),
                set_name=item["set_name"],
                rarity=item.get("rarity"),
                language=item.get("language", "English"),
                reference_image_url=item["reference_image_url"],
                marketplace_id=item["marketplace_id"],
                marketplace_url=item["marketplace_url"],
                visual_embedding=_embedding_bytes(item.get("visual_embedding")),
            )
            await session.merge(record)
            if price := item.get("price"):
                await session.merge(
                    PriceRecord(
                        card_id=item["id"],
                        amount=price.get("amount"),
                        currency=price.get("currency", "USD"),
                        source=price.get("source"),
                        updated_at=datetime.fromisoformat(price["updated_at"]).astimezone(UTC)
                        if price.get("updated_at")
                        else datetime.now(UTC),
                    )
                )
        await session.commit()
    await engine.dispose()


def main() -> None:
    """Parse a catalog path and run the asynchronous importer."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to a JSON array of normalized card records")
    arguments = parser.parse_args()
    asyncio.run(import_catalog(arguments.path))


if __name__ == "__main__":
    main()
