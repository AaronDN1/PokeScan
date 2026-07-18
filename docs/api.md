# API contracts

All product endpoints are versioned under `/api/v1`; `/health` is unversioned for infrastructure probes. Responses are JSON except for the multipart upload.

## `POST /api/v1/recognitions`

Multipart field: `image`. Accepted content: JPEG, PNG, WebP, HEIC/HEIF up to 12 MB and 24 megapixels.

Matched response:

```json
{
  "recognition_id": "d8e9bb7d-2630-4dfa-97f2-518888cf58d8",
  "status": "matched",
  "card": {
    "id": "sv3pt5-006",
    "name": "Charizard ex",
    "set_name": "Scarlet & Violet—151",
    "collector_number": "6",
    "printed_total": "165",
    "rarity": "Double Rare",
    "language": "English",
    "image_url": "https://catalog.example/cards/sv3pt5-006.webp",
    "marketplace_url": "https://www.tcgplayer.com/product/example",
    "price": {
      "amount": 8.42,
      "currency": "USD",
      "source": "tcgplayer",
      "updated_at": "2026-07-18T15:00:00Z"
    }
  },
  "confidence": 0.94,
  "candidates": [],
  "processing_ms": 742.3,
  "message": null
}
```

`ambiguous` responses set `card` to `null` and include up to three candidates. `unrecognized` returns an empty candidate list when retrieval or verification is insufficient.

Expected upload/recognition failures use HTTP 422:

```json
{ "detail": "The photo is too blurry to identify safely.", "code": "image_too_blurry" }
```

Codes include `invalid_image`, `image_too_large`, `image_too_blurry`, `card_not_found`, `multiple_cards`, and `recognition_unavailable`. Rate limiting returns 429. Unhandled failures use FastAPI's generic production response and never expose exception text.

## `GET /api/v1/cards/{id}`

Returns one card with its cached price, or 404.

## `GET /api/v1/prices/{id}`

Returns only the cached price. `amount` may be `null`; marketplace failure is never a recognition failure.

## `POST /api/v1/feedback`

```json
{
  "recognition_id": "d8e9bb7d-2630-4dfa-97f2-518888cf58d8",
  "predicted_card_id": "sv3pt5-006",
  "correct_card_id": "sv3pt5-199",
  "is_correct": false
}
```

Returns 204. No image reference is accepted.

## `GET /health`

Returns API version plus `database` and `models` readiness. Missing model artifacts are reported as `artifacts_required`; database loss degrades the overall status.
