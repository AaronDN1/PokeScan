# Model artifacts

The default baseline does not require custom-trained models.

- `rapidocr==3.9.1` initializes pretrained PP-OCRv6 tiny detector/recognizer assets during `scripts/bootstrap_dev.py`.
- `scripts/download_pretrained_models.py` downloads the pinned ONNX Model Zoo MobileNetV2-12 classifier, verifies SHA-256, and exposes its 1,280-value penultimate feature tensor as `mobilenetv2-features.onnx`.
- ONNX Runtime CPU sessions are retained per API process.

Downloaded binaries are intentionally ignored by Git. Setup is explicit; normal scan requests never download a model.

The future custom backends still accept `ocr-name.onnx`, `ocr-number.onnx`, and `artwork-embedding.onnx` using the original input/output contracts. Enable them only with the matching backend environment variables and benchmark report.
