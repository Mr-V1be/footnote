# syntax=docker/dockerfile:1.7
# One image for the API, the worker and the one-off commands (migrations,
# corpus, demo stand). Build from the repository root:
#   docker build -f backend/Dockerfile -t snoska-backend .

FROM ghcr.io/astral-sh/uv:0.9.26 AS uv

FROM python:3.13-slim-trixie AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/app/backend/.venv
WORKDIR /app/backend
# Dependencies first: they change less often than the sources.
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY backend/src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

FROM python:3.13-slim-trixie AS runtime
# Tesseract reads scans (Russian and English).
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 snoska \
    && useradd --system --uid 10001 --gid snoska --home-dir /app --no-create-home snoska
WORKDIR /app/backend
COPY --from=build /app/backend /app/backend
COPY backend/alembic.ini ./alembic.ini
COPY backend/migrations ./migrations
COPY backend/data ./data
COPY backend/demo ./demo
# Uploaded files live under /app/var (a volume).
RUN mkdir -p /app/var/blobs && chown -R snoska:snoska /app/var
ENV PATH=/app/backend/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    FOOTNOTE_API_HOST=0.0.0.0 \
    FOOTNOTE_API_PORT=8000
USER snoska
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/live', timeout=4)"]
CMD ["footnote", "api"]
