"""Export a trained artwork checkpoint to the deployment ONNX contract."""

from __future__ import annotations

import argparse
from pathlib import Path

import torch

from pokelens_ml.artwork import ArtworkEmbeddingModel


def export(checkpoint: Path, output: Path, embedding_size: int) -> None:
    """Load a checkpoint and export a statically shaped CPU-compatible graph."""
    model = ArtworkEmbeddingModel(embedding_size=embedding_size, pretrained=False)
    model.load_state_dict(torch.load(checkpoint, map_location="cpu", weights_only=True))
    model.eval()
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        model,
        (torch.zeros(1, 3, 224, 224),),
        output,
        input_names=["image"],
        output_names=["embedding"],
        dynamic_axes={"image": {0: "batch"}, "embedding": {0: "batch"}},
        opset_version=18,
        dynamo=False,
    )


def main() -> None:
    """Parse export arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--embedding-size", type=int, default=256)
    args = parser.parse_args()
    export(args.checkpoint, args.output, args.embedding_size)


if __name__ == "__main__":
    main()
