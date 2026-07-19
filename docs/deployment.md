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

## Free personal mobile test deployment

GitHub Pages cannot run the Python recognition service. For a no-cost personal
test deployment, keep the frontend on the existing Sites project and run the
backend as a public Hugging Face Docker Space. The Space's free CPU tier is large
enough for the OCR and visual indexes, but it sleeps after extended inactivity;
the first request after sleep therefore has a cold-start delay.

The workflow in `.github/workflows/deploy-huggingface.yml` creates or updates the
Space manually. Configure these GitHub repository settings before running it:

1. Create a Hugging Face write token.
2. Add that token as the repository secret `HF_TOKEN`.
3. Add `username/pokelens-api` as the repository variable `HF_SPACE_ID`.
4. Run the `deploy recognition api` workflow from the GitHub Actions page.

The deployment bundle uses `deploy/huggingface/Dockerfile`. It builds the full
English catalog and reference index into the image, listens on the Space's port
7860, and runs one worker to avoid duplicating model memory. After the Space
reports `recognition_ready=true` at `/health`, set the Sites production variable
`NEXT_PUBLIC_API_BASE_URL` to `https://username-pokelens-api.hf.space`, rebuild,
and publish the frontend.

The free Space filesystem is ephemeral. That is acceptable for recognition
because the catalog is part of the image; cached prices and user feedback may be
lost on a restart. Move those mutable records to a hosted database before using
this architecture beyond personal testing.
