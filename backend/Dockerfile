FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system pokelens && useradd --system --gid pokelens --create-home pokelens
WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
COPY scripts ./scripts
COPY models ./models
COPY data ./data
RUN pip install --upgrade pip && pip install . \
    && python scripts/download_pretrained_models.py \
    && python -c "from app.infrastructure.models.paddle_ocr import PaddleOcrEngine; PaddleOcrEngine(allow_download=True)" \
    && chown -R pokelens:pokelens /app
USER pokelens
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--no-access-log"]
