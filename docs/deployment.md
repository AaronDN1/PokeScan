# Deployment and operations

## Services

- `web`: stateless Next.js/Vinext PWA.
- `api`: stateless FastAPI workers with process-scoped ONNX sessions.
- `postgres`: normalized catalog, price cache, feedback.
- `redis`: distributed recognition rate limit.
- scheduled catalog/price workers: separate deployables, not request handlers.

Docker Compose mirrors these boundaries for development. Production should use managed PostgreSQL/Redis, an HTTPS ingress, health probes, autoscaling, and a read-only model volume or immutable image layer.

## Required environment

Frontend:

- `NEXT_PUBLIC_API_URL`: public HTTPS API origin.

Backend variables use the `POKELENS_` prefix:

- `DATABASE_URL`: async SQLAlchemy PostgreSQL URL.
- `REDIS_URL`: Redis URL.
- `CORS_ORIGINS`: JSON array of allowed web origins.
- `NAME_OCR_MODEL_PATH`, `NUMBER_OCR_MODEL_PATH`, `ARTWORK_MODEL_PATH`.
- `AUTO_CREATE_SCHEMA=false` after production migrations are adopted.

No marketplace key is required on the recognition path. Price refresh workers own those credentials.

## Release order

1. Apply a reviewed database migration.
2. Import and validate the catalog snapshot and embeddings.
3. Deploy the API with benchmark-approved model artifacts.
4. Verify `/health` reports database and models ready.
5. Deploy the PWA with its API origin.
6. Run single-card smoke scans and error cases.
7. Shift traffic gradually while watching false-confidence feedback and p95 latency.

## Observability

Alert on API 5xx rate, recognition 422 mix changes, Redis/database readiness, model-load failures, p95/p99 latency, price-cache age, rate-limit volume, and feedback indicating incorrect confident matches. Timings should be split into validation, localization, OCR, retrieval, artwork verification, pricing cache, and total.

Uploaded images are never acceptable observability payloads.
