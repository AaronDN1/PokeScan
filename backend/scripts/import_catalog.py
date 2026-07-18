"""Import normalized card and cached price records from a versioned JSON export."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.infrastructure.database.models import Base, CardRecord, PriceRecord


def _decode_bytes(value: str | None) -> bytes | None:
    return base64.b64decode(value) if value else None


def _embedding_bytes(item: dict[str, Any]) -> bytes | None:
    encoded = item.get("visual_embedding_b64")
    if isinstance(encoded, str):
        values = np.frombuffer(base64.b64decode(encoded), dtype=np.float16).astype(np.float32)
        return values.tobytes()
    legacy = item.get("visual_embedding")
    return np.asarray(legacy, dtype=np.float32).tobytes() if legacy else None


async def import_catalog(path: Path, *, database_url: str | None = None) -> int:
    """Upsert real card records and their optional cached prices."""
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    cards = payload.get("cards") if isinstance(payload, dict) else payload
    if not isinstance(cards, list) or not cards:
        raise ValueError("Catalog export contains no cards; refusing an empty import.")
    url = database_url or get_settings().database_url
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        imported = 0
        for item in cards:
            if not isinstance(item, dict):
                continue
            reference_image_url = item.get("reference_image_url")
            if not isinstance(reference_image_url, str):
                continue
            record = CardRecord(
                id=item["id"],
                name=item["name"],
                normalized_name=item["normalized_name"],
                collector_number=item["collector_number"],
                normalized_collector_number=item["normalized_collector_number"],
                printed_total=item.get("printed_total"),
                source=item["source"],
                source_card_id=item["source_card_id"],
                set_id=item["set_id"],
                set_name=item["set_name"],
                rarity=item.get("rarity"),
                language=item.get("language", "en"),
                reference_image_url=reference_image_url,
                marketplace_id=item.get("marketplace_id"),
                marketplace_url=item.get("marketplace_url"),
                reference_asset=item.get("reference_asset"),
                perceptual_hash=item.get("perceptual_hash"),
                orb_descriptors=_decode_bytes(item.get("orb_descriptors_b64")),
                visual_embedding=_embedding_bytes(item),
            )
            await session.merge(record)
            imported += 1
            price = item.get("price")
            if isinstance(price, dict) and price.get("amount") is not None:
                updated_at = (
                    datetime.fromisoformat(price["updated_at"]).astimezone(UTC)
                    if price.get("updated_at")
                    else datetime.now(UTC)
                )
                await session.merge(
                    PriceRecord(
                        card_id=item["id"],
                        amount=float(price["amount"]),
                        currency=price.get("currency", "USD"),
                        source=price.get("source"),
                        updated_at=updated_at,
                    )
                )
        await session.commit()
    await engine.dispose()
    return imported


def main() -> None:
    """Parse a catalog path and run the asynchronous importer."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to a versioned normalized catalog")
    parser.add_argument("--database-url", help="Override POKELENS_DATABASE_URL")
    arguments = parser.parse_args()
    count = asyncio.run(import_catalog(arguments.path, database_url=arguments.database_url))
    print(f"Imported {count} catalog cards.")


if __name__ == "__main__":
    main()
