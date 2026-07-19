"""Prepare pretrained models, a real catalog, reference features, and the database."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from build_catalog import build_catalog
from download_pretrained_models import ensure_model
from import_catalog import import_catalog
from prepare_catalog_assets import prepare_assets

from app.core.config import get_settings
from app.infrastructure.models.paddle_ocr import PaddleOcrEngine


def _catalog_matches_request(path: Path, limit: int | None) -> bool:
    """Only reuse a catalog produced for the same requested scope."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (
        isinstance(payload, dict)
        and payload.get("generator_version") == 2
        and payload.get("requested_limit", "missing") == limit
    )


async def bootstrap(*, limit: int | None, rebuild_catalog: bool) -> None:
    """Run every essential setup stage and refuse to hide setup failures."""
    settings = get_settings()
    catalog_path = Path("data/catalog-en.json")
    manifest_path = Path("data/assets-manifest.json")

    print("[1/5] Initializing pretrained PP-OCRv6 through RapidOCR...")
    PaddleOcrEngine(model_type=settings.rapidocr_model_type, allow_download=True)

    print("[2/5] Preparing the pinned pretrained MobileNetV2 feature extractor...")
    ensure_model(settings.pretrained_artwork_model_path)

    if rebuild_catalog or not _catalog_matches_request(catalog_path, limit):
        label = "full" if limit is None else str(limit)
        print(f"[3/5] Building a real TCGdex catalog ({label} cards requested)...")
        await build_catalog(language="en", output=catalog_path, limit=limit)
    else:
        print(f"[3/5] Reusing matching existing catalog: {catalog_path}")

    print("[4/5] Caching permitted card images and calculating visual features...")
    reference_count, failures = await prepare_assets(
        catalog_path=catalog_path,
        model_path=settings.pretrained_artwork_model_path,
        asset_dir=settings.reference_assets_dir,
        manifest_path=manifest_path,
    )

    print("[5/5] Importing normalized cards and cached optional prices...")
    catalog_count = await import_catalog(catalog_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    missing = int(manifest.get("missing_asset_count", len(failures)))
    healthy = catalog_count > 0 and reference_count > 0
    print("\nPokéLens development bootstrap complete")
    print(f"  catalog card count: {catalog_count}")
    print("  OCR backend: paddle_ppocrv6_rapidocr")
    print("  artwork matcher: composite_phash_orb_mobilenetv2")
    print(f"  database: {'ready' if healthy else 'incomplete'}")
    print(f"  reference image count: {reference_count}")
    print(f"  missing asset count: {missing}")
    print("  frontend URL: http://localhost:5173")
    print("  API URL: http://localhost:8000")
    print(f"  expected health: {'ready' if healthy else 'degraded'}")
    if not healthy:
        raise RuntimeError("Bootstrap completed without enough data for recognition.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional quick-start card limit; zero builds the complete English catalog.",
    )
    parser.add_argument("--rebuild-catalog", action="store_true")
    arguments = parser.parse_args()
    asyncio.run(
        bootstrap(
            limit=arguments.limit or None,
            rebuild_catalog=arguments.rebuild_catalog,
        )
    )


if __name__ == "__main__":
    main()
