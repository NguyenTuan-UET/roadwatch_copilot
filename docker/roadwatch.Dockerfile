# RoadWatch demo server: docker compose up roadwatch  ->  http://127.0.0.1:8765
# Models are not in the image: mount ./models (gr14VinAI.onnx from scripts/roadwatch/download_model.py, phrases-demo/).
# No secret in the image: RW_PASSWORD and friends come from the environment at run time.

# ---- Stage 1: builder: dependencies into a virtual environment ----
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements-roadwatch.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements-roadwatch.txt \
    # test and offline-tool dependencies are not needed at run time
    && /opt/venv/bin/pip uninstall -y pytest ruff httpx onnx

# ---- Stage 2: production: runtime only, non-root ----
FROM python:3.11-slim AS production
ARG VERSION=dev
LABEL org.opencontainers.image.title="roadwatch" org.opencontainers.image.version="$VERSION" \
      org.opencontainers.image.source="https://github.com/AI20K-Build-Phase-Cohort-4/P-014" \
      org.opencontainers.image.licenses="MIT"

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r roadwatch && useradd -r -g roadwatch -u 1000 -m roadwatch

ENV PATH="/opt/venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    RW_HOST=0.0.0.0 RW_PORT=8765 RW_RUNS_DIR=/app/runs/demo RW_VERSION=$VERSION
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY src/__init__.py src/__init__.py
COPY src/roadwatch src/roadwatch
COPY config config
# Inside the container the server listens on all interfaces; compose publishes it on 127.0.0.1 only.
RUN mkdir -p /app/runs/demo /app/models && chown -R roadwatch:roadwatch /app/runs
USER roadwatch
EXPOSE 8765

# Liveness only: /health is 503 without a mounted model, which is a configuration error, not a crash.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health/live')" || exit 1

CMD ["python", "-m", "src.roadwatch.web"]
