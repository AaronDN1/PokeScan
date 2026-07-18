# PokéLens

PokéLens is a mobile-first PWA for identifying one Pokémon card from one clear photograph. It is deliberately focused on the shortest trustworthy flow: upload, recognize, verify, price, and scan again.

This repository is a production-oriented foundation rather than a fake model demo. The upload, localization, perspective correction, region extraction, candidate search, artwork verification, confidence, pricing cache, and public API are implemented. Licensed catalog data and trained model binaries are deployment artifacts and are not fabricated or committed; until they are supplied, health checks report `artifacts_required` and recognition fails safely instead of returning a made-up card.

## What is included

- Next.js App Router PWA with TypeScript, Tailwind CSS, shadcn-style primitives, TanStack Query, Zod, camera capture, and responsive result states.
- FastAPI service with clean domain/application/infrastructure boundaries.
- Deterministic Pillow/OpenCV image validation, card localization, perspective correction, and fixed OCR/artwork regions.
- Replaceable CTC OCR and artwork-embedding adapters using ONNX Runtime.
- Indexed SQLAlchemy catalog search for PostgreSQL, SQLite development fallback, cached pricing, and opt-in correction feedback without image retention.
- Redis-backed rate limiting with a safe process-local development fallback.
- PyTorch artwork embedding model and ONNX export contract.
- Docker Compose, CI, unit/integration tests, benchmark policy, and deployment documentation.

## Quick start

Prerequisites: Node.js 22+, pnpm 11+, Python 3.12+, and Docker if you want PostgreSQL and Redis.

```bash
pnpm install
cp .env.example .env.local
pnpm dev
```

In another terminal:

```bash
cd backend
python -m venv .venv
# PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

The PWA runs at `http://localhost:5173`, the API at `http://localhost:8000`, and interactive API docs at `http://localhost:8000/docs` outside production.

To run infrastructure and both services together:

```bash
docker compose up --build
```

## Required production data

1. Place versioned ONNX artifacts described in [`backend/models/README.md`](backend/models/README.md).
2. Prepare a licensed normalized catalog export and import it with:

   ```bash
   cd backend
   python scripts/import_catalog.py path/to/catalog.json
   ```

3. Populate cached prices asynchronously. Recognition reads the cache and never waits on TCGplayer.
4. Run and pass the benchmark promotion gates before enabling production traffic.

## Verification

```bash
pnpm typecheck
pnpm test
pnpm build

cd backend
pytest
ruff check .
mypy app
```

## Documentation

- [Architecture](docs/architecture.md)
- [Recognition pipeline](docs/recognition-pipeline.md)
- [API contracts](docs/api.md)
- [Database schema](docs/database.md)
- [Benchmarks and model promotion](docs/benchmarks.md)
- [Deployment and operations](docs/deployment.md)
- [Security and privacy](docs/security.md)

Pokémon and related marks belong to their respective owners. This project is not affiliated with or endorsed by Nintendo, Creatures, GAME FREAK, The Pokémon Company, or TCGplayer.
