"""Download and prepare the pinned pretrained MobileNetV2 feature model."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import httpx
import onnx
from onnx import TensorProto, helper

MODEL_URL = (
    "https://huggingface.co/onnxmodelzoo/mobilenetv2-12/resolve/main/mobilenetv2-12.onnx"
)
MODEL_SHA256 = "c0c3f76d93fa3fd6580652a45618618a220fced18babf65774ed169de0432ad5"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _download(destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(".partial")
    with httpx.stream("GET", MODEL_URL, follow_redirects=True, timeout=90.0) as response:
        response.raise_for_status()
        with partial.open("wb") as handle:
            for block in response.iter_bytes(chunk_size=1024 * 1024):
                handle.write(block)
    actual = _sha256(partial)
    if actual != MODEL_SHA256:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"MobileNetV2 checksum mismatch: expected {MODEL_SHA256}, got {actual}")
    partial.replace(destination)


def _feature_output(model: onnx.ModelProto) -> str:
    producer = {output: node for node in model.graph.node for output in node.output}
    current = model.graph.output[0].name
    visited: set[str] = set()
    while current not in visited:
        visited.add(current)
        node = producer.get(current)
        if node is None:
            break
        if node.op_type in {"Gemm", "MatMul"}:
            return node.input[0]
        current = node.input[0]
    classifier = next(
        (node for node in reversed(model.graph.node) if node.op_type in {"Gemm", "MatMul"}),
        None,
    )
    if classifier is None:
        raise RuntimeError("Could not find the MobileNetV2 classifier input.")
    return classifier.input[0]


def _convert_to_features(source: Path, output: Path) -> None:
    model = onnx.shape_inference.infer_shapes(onnx.load(source))
    feature_name = _feature_output(model)
    value_info = next(
        (
            value
            for value in (*model.graph.value_info, *model.graph.input, *model.graph.output)
            if value.name == feature_name
        ),
        None,
    )
    del model.graph.output[:]
    if value_info is not None and value_info.type.tensor_type.HasField("shape"):
        model.graph.output.append(value_info)
    else:
        model.graph.output.append(
            helper.make_tensor_value_info(feature_name, TensorProto.FLOAT, [None, 1280])
        )
    onnx.checker.check_model(model)
    output.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, output)


def ensure_model(output: Path, *, force: bool = False) -> Path:
    """Download the pinned classifier and expose its penultimate feature tensor."""
    if output.is_file() and not force:
        return output
    source = output.with_name("mobilenetv2-12.onnx")
    if not source.is_file() or _sha256(source) != MODEL_SHA256:
        _download(source)
    _convert_to_features(source, output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("models/mobilenetv2-features.onnx"),
    )
    parser.add_argument("--force", action="store_true")
    arguments = parser.parse_args()
    result = ensure_model(arguments.output, force=arguments.force)
    print(f"Pretrained MobileNetV2 feature model ready: {result}")


if __name__ == "__main__":
    main()
