# PokéLens

PokéLens identifies one English Pokémon card from one clear front-side photograph. The default baseline is fully local at recognition time: OpenCV locates and warps the card, pretrained PP-OCRv6 reads targeted text regions, a normalized TCGdex catalog retrieves candidates, and pHash + ORB + pretrained MobileNetV2 features verify the printing.

The project does not require custom-trained models. The original custom ONNX adapters remain available for future use.

## What was “scanner offline”

The hosted `.chatgpt.site` was the web frontend only. A browser cannot run this FastAPI/SQLite/OpenCV/ONNX backend, and the old health contract disabled the upload button when three uncommitted custom model files were absent. Copying `.env.example` only created a local configuration file; it did not install, initialize, or start the API.

`pnpm` is the package manager declared by this repository and used by CI. `npm install` can install the frontend dependencies, but use pnpm for reproducible lockfile behavior. The Python package lives in `backend/`, which is why running `pip install -e ".[dev]"` from the repository root reported that no `pyproject.toml` existed.

## Working local setup (Windows PowerShell)

Prerequisites: Node.js 22+, pnpm 11+, and Python 3.12+.

From the repository root, these are the only commands required:

```powershell
pnpm.cmd --version
pnpm.cmd install
pnpm.cmd setup
pnpm.cmd dev
```

The repository expects pnpm 11.9.0. If `pnpm.cmd --version` says the command is missing,
install it for your Windows user without enabling Corepack system-wide:

```powershell
npm.cmd install --global pnpm@11.9.0
```

`corepack enable` is optional and commonly requires an Administrator terminal when
Node.js is installed under `C:\Program Files\nodejs`; it is not required to run this project.

`pnpm.cmd setup` creates the Python environment, installs the recognition
dependencies, downloads the pretrained models, and prepares the complete
physical English catalog. Run it once; the catalog/image preparation is the
longest part of the first setup. For a fast developer smoke test only, use:

```powershell
pnpm.cmd setup:quick
```

The quick setup contains only 250 cards and is not suitable for judging real
recognition coverage. `pnpm.cmd setup:full` remains an alias for the normal full
setup.

`pnpm.cmd dev` starts both the recognition API and the web app in one terminal.
It reuses an already-healthy PokéLens API instead of failing when port 8000 is
occupied. Stop it with `Ctrl+C`.

Open `http://localhost:5173`. The API is at `http://localhost:8000`, health at
`http://localhost:8000/health`, and development API docs at
`http://localhost:8000/docs`.

macOS/Linux uses `pnpm` instead of `pnpm.cmd`; the setup launcher creates the
platform-appropriate virtual environment.

## Explicit full catalog pipeline

Run from `backend/` with the environment activated:

```bash
python scripts/download_pretrained_models.py
python scripts/build_catalog.py --language en --output data/catalog-en.json
python scripts/prepare_catalog_assets.py data/catalog-en.json
python scripts/import_catalog.py data/catalog-en.json
```

The builder uses TCGdex v2 structured data and its documented WebP assets. It
filters out digital TCG Pocket entries, uses compact reference images for local
visual indexing, and preserves high-resolution URLs for display. IDs include
source, language, set, and source card identity. Isolated missing metadata/images
are recorded or skipped; recognition never downloads catalog images or calls a
marketplace.

## Configuration

Frontend:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Backend defaults (all may also use the `POKELENS_` prefix):

```env
OCR_BACKEND=paddle
ARTWORK_MATCHER_BACKEND=composite
CUSTOM_ONNX_MODELS_REQUIRED=false
POKELENS_DATABASE_URL=sqlite+aiosqlite:///./data/pokelens.db
POKELENS_CORS_ORIGINS=["http://localhost:5173"]
```

Future custom adapters remain selectable with `OCR_BACKEND=onnx_ctc`, `ARTWORK_MATCHER_BACKEND=onnx_embedding`, and `CUSTOM_ONNX_MODELS_REQUIRED=true` after supplying the documented custom files.

## Verification and benchmarks

```bash
pnpm typecheck
pnpm test
pnpm build

cd backend
ruff check .
mypy app
pytest
python scripts/smoke_recognition.py path/to/one-real-card-photo.jpg
python scripts/benchmark_recognition.py --manifest benchmarks/manifest.json --output benchmarks/results.json --stress
```

Copy `backend/benchmarks/manifest.example.json` to `manifest.json`, place consented photographs in `backend/benchmarks/photos/`, and replace each expected ID with the imported TCGdex internal ID. No accuracy claim is made until a representative benchmark has been run.

## Docker

The backend image explicitly installs the pinned runtimes and downloads pretrained models during its build. Catalog preparation remains an explicit setup operation:

```bash
docker compose build
docker compose --profile setup run --rm setup
docker compose up
```

For a bounded Docker smoke catalog, override the setup command with `python scripts/bootstrap_dev.py --limit 250 --rebuild-catalog`.

## Supported scope and limitations

- One fully visible, front-side English card per image.
- Modern layouts are the initial optimization target; many vintage cards work, but tiny collector numbers are harder.
- Moderate rotation/perspective and ordinary sleeves may work; glare, strong blur, occlusion, severe foreshortening, and unusual layouts reduce reliability.
- Missing pricing or marketplace mappings do not affect recognition.
- Baseline thresholds are conservative engineering defaults, not scientifically calibrated accuracy claims.
- CPU latency varies materially by hardware; benchmark on the intended deployment CPU.

See [architecture](docs/architecture.md), [pipeline](docs/recognition-pipeline.md), [API](docs/api.md), [database](docs/database.md), [benchmarks](docs/benchmarks.md), [deployment](docs/deployment.md), and [security](docs/security.md).

Pokémon and related marks belong to their respective owners. This project is not affiliated with or endorsed by Nintendo, Creatures, GAME FREAK, The Pokémon Company, TCGdex, or TCGplayer.
