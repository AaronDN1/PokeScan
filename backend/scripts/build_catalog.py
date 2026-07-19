"""Build a versioned normalized Pokémon catalog from TCGdex v2."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from app.infrastructure.catalog.tcgdex import TcgDexCatalogProvider, TcgDexOptions


async def build_catalog(*, language: str, output: Path, limit: int | None) -> int:
    """Fetch and save a deterministic provider-neutral catalog envelope."""
    provider = TcgDexCatalogProvider(TcgDexOptions(language=language))
    cards = [card async for card in provider.cards(limit=limit)]
    if not cards:
        raise RuntimeError("TCGdex returned no cards; refusing to write an empty catalog.")
    cards.sort(key=lambda item: str(item["id"]))
    payload = {
        "schema_version": 2,
        "generator_version": 2,
        "provider": provider.name,
        "language": language,
        "generated_at": datetime.now(UTC).isoformat(),
        "requested_limit": limit,
        "card_count": len(cards),
        "cards": cards,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(cards)


def main() -> None:
    """Parse catalog build options and fail loudly on essential errors."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", default="en")
    parser.add_argument("--output", type=Path, default=Path("data/catalog-en.json"))
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional development limit; zero builds the full catalog.",
    )
    arguments = parser.parse_args()
    count = asyncio.run(
        build_catalog(
            language=arguments.language,
            output=arguments.output,
            limit=arguments.limit or None,
        )
    )
    print(f"Wrote {count} real TCGdex cards to {arguments.output}")


if __name__ == "__main__":
    main()
