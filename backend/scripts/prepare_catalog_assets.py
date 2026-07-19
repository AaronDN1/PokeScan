"""Cache TCGdex card images and precompute candidate visual features."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import re
from pathlib import Path
from typing import Any, cast

import cv2
import httpx
import numpy as np
from numpy.typing import NDArray

from app.infrastructure.models.composite_artwork import (
    MobileNetV2Embedder,
    perceptual_hash,
)

type ImageArray = NDArray[np.uint8]


def _asset_name(card_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", card_id) + ".webp"


def _compact_asset_url(url: str) -> str:
    """Use TCGdex's documented low WebP asset for local feature preparation."""
    return url.replace("/high.webp", "/low.webp")


async def _download(
    client: httpx.AsyncClient,
    url: str,
    destination: Path,
    semaphore: asyncio.Semaphore,
) -> str | None:
    async with semaphore:
        for attempt in range(3):
            try:
                response = await client.get(url)
                response.raise_for_status()
                array = np.frombuffer(response.content, dtype=np.uint8)
                image = cast(
                    ImageArray | None,
                    cv2.imdecode(array, cv2.IMREAD_COLOR),
                )
                if image is None:
                    raise ValueError("OpenCV could not decode the reference image")
                height, width = image.shape[:2]
                if max(width, height) > 420:
                    scale = 420 / max(width, height)
                    image = cast(
                        ImageArray,
                        cv2.resize(
                            image,
                            (max(1, int(width * scale)), max(1, int(height * scale))),
                            interpolation=cv2.INTER_AREA,
                        ),
                    )
                ok, encoded = cv2.imencode(".webp", image, [cv2.IMWRITE_WEBP_QUALITY, 90])
                if not ok:
                    raise ValueError("OpenCV could not encode the reference image")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(encoded.tobytes())
                return None
            except (httpx.HTTPError, ValueError) as error:
                if attempt == 2:
                    return str(error)
                await asyncio.sleep(0.4 * (2**attempt))
    return "unreachable"


async def prepare_assets(
    *,
    catalog_path: Path,
    model_path: Path,
    asset_dir: Path,
    manifest_path: Path,
) -> tuple[int, list[dict[str, str]]]:
    """Prepare each available asset without failing the batch for isolated downloads."""
    payload: dict[str, Any] = json.loads(catalog_path.read_text(encoding="utf-8"))
    cards = payload.get("cards")
    if not isinstance(cards, list):
        raise ValueError("Catalog must be a versioned JSON object containing a cards list.")
    embedder = MobileNetV2Embedder(
        model_path,
        intra_op_num_threads=min(4, os.cpu_count() or 1),
    )
    if not embedder.available:
        raise FileNotFoundError(f"Pretrained feature model not found: {model_path}")
    failures: list[dict[str, str]] = []
    semaphore = asyncio.Semaphore(24)
    timeout = httpx.Timeout(30.0)
    limits = httpx.Limits(max_connections=24, max_keepalive_connections=24)
    async with httpx.AsyncClient(
        timeout=timeout,
        limits=limits,
        follow_redirects=True,
    ) as client:
        pending: list[tuple[dict[str, Any], Path, asyncio.Task[str | None]]] = []
        for card in cards:
            url = card.get("reference_image_url")
            destination = asset_dir / _asset_name(str(card["id"]))
            if not destination.is_file() and isinstance(url, str):
                task = asyncio.create_task(
                    _download(client, _compact_asset_url(url), destination, semaphore)
                )
                pending.append((card, destination, task))
        for index, (card, _destination, task) in enumerate(pending, start=1):
            error = await task
            if error:
                failures.append({"card_id": str(card["id"]), "error": error})
            if index % 1000 == 0:
                print(f"  downloaded or checked {index:,}/{len(pending):,} new assets")

    prepared = 0
    feature_batch: list[tuple[dict[str, Any], Path, ImageArray]] = []

    def prepare_feature_batch() -> int:
        if not feature_batch:
            return 0
        embeddings = embedder.embed_many([image for _card, _path, image in feature_batch])
        for (card, destination, image), embedding in zip(
            feature_batch,
            embeddings,
            strict=True,
        ):
            card["reference_asset"] = destination.as_posix()
            card["perceptual_hash"] = perceptual_hash(image)
            # ORB descriptors are calculated lazily for shortlisted cards and cached
            # in-process. Persisting hundreds per card makes a full catalog needlessly huge.
            card["orb_descriptors_b64"] = None
            card["visual_embedding_b64"] = (
                base64.b64encode(np.asarray(embedding, dtype=np.float16).tobytes()).decode(
                    "ascii"
                )
                if embedding
                else None
            )
        count = len(feature_batch)
        feature_batch.clear()
        return count

    for index, card in enumerate(cards, start=1):
        destination = asset_dir / _asset_name(str(card["id"]))
        if not destination.is_file():
            continue
        image = cast(
            ImageArray | None,
            cv2.imread(str(destination), cv2.IMREAD_COLOR),
        )
        if image is None:
            failures.append({"card_id": str(card["id"]), "error": "cached image is invalid"})
            continue
        feature_batch.append((card, destination, image))
        if len(feature_batch) >= 32:
            prepared += prepare_feature_batch()
        if index % 1000 == 0:
            print(f"  prepared visual features for {index:,}/{len(cards):,} cards")
    prepared += prepare_feature_batch()

    payload["visual_feature_version"] = 2
    payload["prepared_asset_count"] = prepared
    payload["missing_asset_count"] = len(cards) - prepared
    catalog_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "catalog": catalog_path.as_posix(),
        "asset_count": prepared,
        "missing_asset_count": len(cards) - prepared,
        "failures": failures,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return prepared, failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--model", type=Path, default=Path("models/mobilenetv2-features.onnx"))
    parser.add_argument("--assets", type=Path, default=Path("data/reference-images"))
    parser.add_argument("--manifest", type=Path, default=Path("data/assets-manifest.json"))
    arguments = parser.parse_args()
    count, failures = asyncio.run(
        prepare_assets(
            catalog_path=arguments.catalog,
            model_path=arguments.model,
            asset_dir=arguments.assets,
            manifest_path=arguments.manifest,
        )
    )
    print(f"Prepared {count} reference images; {len(failures)} downloads failed.")


if __name__ == "__main__":
    main()
