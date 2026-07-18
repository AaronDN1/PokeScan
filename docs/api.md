# API contracts

`POST /api/v1/recognitions` accepts one multipart `image` (JPEG, PNG, WebP, HEIC/HEIF; 12 MB and 24 MP limits). A matched response contains the exact catalog card, bounded alternatives, real confidence, latency, and optional cached price:

```json
{
  "recognition_id": "uuid",
  "status": "matched",
  "card": {
    "id": "tcgdex:en:basep:basep-1",
    "name": "Pikachu",
    "set_name": "Wizards Black Star Promos",
    "collector_number": "1",
    "printed_total": "53",
    "rarity": "Common",
    "language": "en",
    "image_url": "https://assets.tcgdex.net/en/base/basep/1/high.webp",
    "marketplace_url": null,
    "price": {
      "amount": null,
      "currency": "USD",
      "source": null,
      "updated_at": null,
      "price_status": "unavailable"
    }
  },
  "confidence": 0.84,
  "candidates": [],
  "processing_ms": 11000,
  "message": null,
  "diagnostics": null
}
```

`ambiguous` sets `card` to null and exposes up to three honest candidates. `unrecognized` never chooses a random card. Image errors return 422, rate limiting 429, and missing OCR/catalog/model capability 503 with code `recognition_unavailable`.

`GET /api/v1/cards/{id}` and `GET /api/v1/prices/{id}` read local data. `POST /api/v1/feedback` stores identifiers/correction only, never the photo.

`GET /health` reports `recognition_ready` and independent `ocr`, `artwork_matching`, `catalog`, and optional `pricing` capabilities. An empty catalog or missing OCR/artwork model keeps recognition degraded; missing prices do not.
