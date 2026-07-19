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
    "marketplace_url": "https://www.tcgplayer.com/product/121772",
    "price": {
      "amount": 31.45,
      "currency": "USD",
      "source": "tcgplayer_api",
      "updated_at": "2026-07-18T12:00:00Z",
      "near_mint": 31.45,
      "lightly_played": 24.0,
      "moderately_played": 18.75,
      "product_id": "121772",
      "marketplace_url": "https://www.tcgplayer.com/product/121772",
      "printing_name": "Normal",
      "price_status": "available"
    }
  },
  "confidence": 0.84,
  "candidates": [],
  "processing_ms": 11000,
  "message": null,
  "diagnostics": null
}
```

`ambiguous` returns the most likely card plus up to three honest candidates, allowing
the UI to show a useful automatic result while clearly labeling the uncertainty.
`unrecognized` leaves `card` null and never chooses a random card. Image errors
return 422, rate limiting 429, and missing OCR/catalog/model capability 503 with
code `recognition_unavailable`.

`GET /api/v1/cards/{id}` and `GET /api/v1/prices/{id}` return cached marketplace
data and refresh stale entries when providers are reachable. The canonical HTTPS
product URL is safe to use as a normal browser link and allows mobile operating
systems to hand supported links to the TCGplayer app. Condition fields remain null
without existing approved TCGplayer API credentials. `POST /api/v1/feedback`
stores identifiers/correction only, never the photo.

`GET /health` reports `recognition_ready` and independent `ocr`, `artwork_matching`, `catalog`, and optional `pricing` capabilities. An empty catalog or missing OCR/artwork model keeps recognition degraded; missing prices do not.
