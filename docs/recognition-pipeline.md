# Recognition pipeline

```mermaid
flowchart LR
  U["Upload"] --> V["Validate"] --> L["Locate"] --> W["Warp once"]
  W --> O["Choose orientation"] --> T["Targeted OCR"] --> N["Normalize"]
  N --> C["Retrieve ≤8"] --> A["Visual verify"] --> S["Confidence"] --> X["Result"]
```

1. Pillow validates MIME, decoded format, byte and pixel limits, dimensions, and integrity.
2. OpenCV downsizes only oversized inputs, detects a visible card quadrilateral, rejects distinct multiple cards, perspective-warps once to 744×1039, and measures localization/blur quality.
3. The orientation resolver evaluates 0°, 90°, 180°, and 270° name regions. It evaluates collector OCR for the two most plausible rotations and reuses the selected OCR outputs.
4. RapidOCR runs pretrained PP-OCRv6 only on configurable name and collector crops. One resize and optional grayscale histogram equalization are the only preprocessing variants.
5. Unicode, punctuation, suffixes, collector formats, and bounded contextual OCR alternatives are normalized while raw OCR and real confidence remain available in development diagnostics.
6. Indexed exact/fuzzy text retrieval returns at most eight candidates. Name-only and number-only fallback paths are supported; no random catalog-wide visual fallback exists.
7. The scan artwork is processed once for pHash, ORB descriptors, and a normalized MobileNetV2 feature. Only candidate records are compared against cached static features.
8. Confidence requires text and visual agreement plus a runner-up margin. Outcomes are `matched`, `ambiguous`, or `unrecognized`; unavailable required capability returns HTTP 503 `recognition_unavailable`.

Structured logs record validation, localization/warp, orientation, name OCR, collector OCR, retrieval, artwork, price lookup, and total milliseconds. Images and crops are never logged. Development-only base64 diagnostics require both `POKELENS_DEVELOPMENT_DIAGNOSTICS=true` and `?debug=true`.

Thresholds are conservative defaults pending a representative benchmark; they are not accuracy claims.
