# Deployment and operations

Deploy the web frontend and FastAPI backend separately. The `.chatgpt.site`/Sites project is a frontend host; it does not run the Python recognition service.

## Frontend

Build with `NEXT_PUBLIC_API_BASE_URL=https://your-api.example`. The output is compatible with the existing Sites/Vinext host and can also be adapted for Vercel-compatible frontend hosting. The URL must be absolute HTTP(S); missing/invalid configuration produces a useful offline message.

## Backend

The backend Docker image is suitable for Cloud Run, Render, Railway, Azure Container Apps, or another container service with persistent PostgreSQL/catalog data. It runs non-root, initializes OCR and MobileNet sessions once per worker, and exposes `/health`.

Required or common variables:

```env
POKELENS_ENVIRONMENT=production
POKELENS_DATABASE_URL=postgresql+asyncpg://...
POKELENS_REDIS_URL=redis://...
POKELENS_CORS_ORIGINS=["https://your-frontend.example"]
OCR_BACKEND=paddle
ARTWORK_MATCHER_BACKEND=composite
CUSTOM_ONNX_MODELS_REQUIRED=false
POKELENS_AUTO_CREATE_SCHEMA=false
```

Run catalog/reference preparation before serving traffic and persist `data/` or import into PostgreSQL. The container image downloads pinned pretrained model assets during its explicit build, never during a scan request.

Release order: build the image, run catalog setup/import, deploy the API, verify `recognition_ready=true`, build the web app with the public API URL, then execute real-card and error-case smoke tests. Pricing can remain empty. Scale cautiously because each API worker holds its own CPU model sessions; benchmark worker count and p95 on the chosen instance.

This repository was prepared for deployment but was not deployed by Codex because no backend cloud credentials/target were supplied.
