# Architecture

PokéLens preserves clean architecture: domain protocols own the boundaries, the application use case coordinates them, and infrastructure adapters implement OCR, vision, data, and pricing.

```mermaid
flowchart LR
  W["Vinext/Next web app"] --> A["FastAPI routes"] --> U["RecognizeCard"]
  U --> V["Pillow + OpenCV"]
  U --> O["RapidOCR PP-OCRv6"]
  U --> R["SQLAlchemy catalog"]
  U --> M["pHash + ORB + MobileNetV2"]
  U --> P["Optional cached pricing"]
```

`backend/app/core/container.py` is the only backend-selection point. The default is `paddle` OCR plus the `composite` artwork matcher. The original custom CTC OCR and ONNX embedding adapters remain selectable without changing the use case or HTTP contract.

TCGdex is behind a catalog-provider protocol. Builder, reference asset preparation, feature generation, and import are offline setup stages. Recognition itself is image-stateless and network-independent: request bytes are released after processing, model sessions live for the process, database search is indexed and bounded to eight candidates, and static reference features are cached.

The frontend validates responses with Zod at the trust boundary. Pricing, marketplace mappings, Redis, and custom models are independent capabilities; only OCR, artwork matching, database access, and a non-empty catalog determine recognition readiness.
