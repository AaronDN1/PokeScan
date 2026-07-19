FROM python:3.12-slim AS runtime

ARG POKELENS_CATALOG_LIMIT=0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    OMP_NUM_THREADS=2 \
    POKELENS_ENVIRONMENT=production \
    POKELENS_DATABASE_URL=sqlite+aiosqlite:///./data/pokelens.db \
    POKELENS_AUTO_CREATE_SCHEMA=false \
    POKELENS_REDIS_URL=

RUN apt-get update \
    && apt-get install --yes --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system pokelens \
    && useradd --system --gid pokelens --create-home pokelens

WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
COPY scripts ./scripts
COPY models ./models
COPY data ./data

# The Space has ephemeral runtime storage. Build the complete catalog and
# visual index into the image so waking or restarting never downloads 19,000+
# reference cards before the API can become healthy. A nonzero build argument is
# available only for local smoke builds; hosted builds intentionally use zero.
RUN python -m pip install --upgrade pip \
    && python -m pip install . \
    && python scripts/bootstrap_dev.py --limit "${POKELENS_CATALOG_LIMIT}" --rebuild-catalog \
    && rm -f models/mobilenetv2-12.onnx data/catalog-en.json data/assets-manifest.json \
    && chown -R pokelens:pokelens /app

USER pokelens
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/health', timeout=8)"

# One worker avoids duplicating the in-memory OCR and visual indexes. This CPU
# configuration is intended for personal mobile testing, not concurrent load.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1", "--no-access-log"]
