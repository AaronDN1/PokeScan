# Model artifacts

Production model binaries are intentionally not committed. Mount or copy these versioned artifacts here:

| File | Input | Output | Purpose |
| --- | --- | --- | --- |
| `ocr-name.onnx` | `float32[1,1,48,320]` | CTC logits `[1,T,C]` | Top-region card name OCR |
| `ocr-number.onnx` | `float32[1,1,48,320]` | CTC logits `[1,T,C]` | Bottom-region collector number OCR |
| `artwork-embedding.onnx` | `float32[1,3,224,224]` | embedding `[1,D]` | Candidate-only artwork verification |

The API remains healthy without the files, but `/health` reports `artifacts_required` and scan requests return a safe `recognition_unavailable` response. This prevents a development checkout from falsely presenting heuristic guesses as confident matches.

Every promoted model must be paired with its benchmark report, dataset manifest, charset, SHA-256 digest, and semantic version. See `../../docs/benchmarks.md`.
