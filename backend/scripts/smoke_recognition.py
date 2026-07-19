"""Run one image through the real composed recognition pipeline."""

from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
from pathlib import Path

from app.core.config import get_settings
from app.core.container import Container


async def recognize(image_path: Path) -> dict[str, object]:
    container = Container(get_settings())
    await container.start()
    try:
        result = await container.recognize_card.execute(
            payload=image_path.read_bytes(),
            declared_mime=mimetypes.guess_type(image_path.name)[0] or "image/jpeg",
            include_diagnostics=True,
        )
        diagnostics = dict(result.diagnostics or {})
        diagnostics.pop("images", None)
        return {
            "status": result.status.value,
            "card_id": result.card.id if result.card else None,
            "card_name": result.card.name if result.card else None,
            "confidence": result.confidence,
            "candidate_ids": [item.evidence.card.id for item in result.candidates],
            "diagnostics": diagnostics,
        }
    finally:
        await container.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(asyncio.run(recognize(arguments.image)), indent=2))


if __name__ == "__main__":
    main()
