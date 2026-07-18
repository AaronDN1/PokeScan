"""Benchmark exact recognition against user-supplied real card photographs."""

from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import statistics
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import get_settings
from app.core.container import Container
from app.domain.errors import RecognitionError
from app.domain.models import RecognitionStatus


def _rate(value: int, total: int) -> float:
    return round(value / total, 4) if total else 0.0


async def benchmark(manifest_path: Path, output: Path) -> dict[str, Any]:
    """Run the real composition root; no successful outcome is hardcoded."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    samples = manifest.get("samples", [])
    if not isinstance(samples, list) or not samples:
        raise ValueError("Benchmark manifest contains no samples.")
    container = Container(get_settings())
    await container.start()
    counts = {
        "localized": 0,
        "name_exact": 0,
        "collector_exact": 0,
        "top1": 0,
        "top3": 0,
        "false_confident": 0,
        "ambiguous": 0,
        "unrecognized": 0,
    }
    latencies: list[float] = []
    details: list[dict[str, Any]] = []
    try:
        for sample in samples:
            image_path = (manifest_path.parent / sample["image"]).resolve()
            expected_id = str(sample["card_id"])
            expected_card = await container.cards.get(expected_id)
            if expected_card is None:
                raise ValueError(f"Expected card is not in the catalog: {expected_id}")
            try:
                result = await container.recognize_card.execute(
                    payload=image_path.read_bytes(),
                    declared_mime=mimetypes.guess_type(image_path.name)[0] or "image/jpeg",
                    include_diagnostics=True,
                )
                diagnostics = result.diagnostics or {}
                counts["localized"] += 1
                counts["name_exact"] += int(
                    diagnostics.get("normalized_name") == expected_card.normalized_name
                )
                counts["collector_exact"] += int(
                    diagnostics.get("normalized_collector_number")
                    == expected_card.normalized_collector_number
                )
                candidate_ids = [item.evidence.card.id for item in result.candidates]
                counts["top1"] += int(bool(candidate_ids) and candidate_ids[0] == expected_id)
                counts["top3"] += int(expected_id in candidate_ids[:3])
                counts["false_confident"] += int(
                    result.status is RecognitionStatus.MATCHED
                    and (result.card is None or result.card.id != expected_id)
                )
                counts["ambiguous"] += int(result.status is RecognitionStatus.AMBIGUOUS)
                counts["unrecognized"] += int(result.status is RecognitionStatus.UNRECOGNIZED)
                latencies.append(result.processing_ms)
                details.append(
                    {
                        "image": sample["image"],
                        "expected_card_id": expected_id,
                        "status": result.status.value,
                        "top_candidates": candidate_ids[:3],
                        "latency_ms": result.processing_ms,
                    }
                )
            except RecognitionError as error:
                counts["unrecognized"] += 1
                details.append(
                    {
                        "image": sample["image"],
                        "expected_card_id": expected_id,
                        "error": error.code,
                    }
                )
    finally:
        await container.close()
    total = len(samples)
    results = {
        "sample_count": total,
        "localization_success": _rate(counts["localized"], total),
        "exact_name_ocr_accuracy": _rate(counts["name_exact"], total),
        "exact_collector_ocr_accuracy": _rate(counts["collector_exact"], total),
        "top_1_exact_card_accuracy": _rate(counts["top1"], total),
        "top_3_exact_card_accuracy": _rate(counts["top3"], total),
        "false_confident_match_rate": _rate(counts["false_confident"], total),
        "ambiguous_rate": _rate(counts["ambiguous"], total),
        "unrecognized_rate": _rate(counts["unrecognized"], total),
        "median_latency_ms": round(statistics.median(latencies), 2) if latencies else None,
        "p95_latency_ms": (
            round(float(np.percentile(np.asarray(latencies), 95)), 2) if latencies else None
        ),
        "samples": details,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("benchmarks/manifest.json"))
    parser.add_argument("--output", type=Path, default=Path("benchmarks/results.json"))
    arguments = parser.parse_args()
    results = asyncio.run(benchmark(arguments.manifest, arguments.output))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
