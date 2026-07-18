FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system pokelens && useradd --system --gid pokelens --create-home pokelens
WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
COPY models ./models
RUN pip install --upgrade pip && pip install .
USER pokelens
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--no-access-log"]
