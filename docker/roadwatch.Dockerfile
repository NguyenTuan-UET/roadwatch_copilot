# RoadWatch demo server: docker compose up roadwatch  ->  http://127.0.0.1:8765
# Models are not in the image: mount ./models (gr14VinAI.onnx from scripts/roadwatch/download_model.py, phrases-demo/).
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 roadwatch

WORKDIR /app
COPY requirements-roadwatch.txt .
RUN pip install --no-cache-dir -r requirements-roadwatch.txt

COPY src/__init__.py src/__init__.py
COPY src/roadwatch src/roadwatch
COPY config config

# Inside the container the server must listen on all interfaces; compose publishes it on 127.0.0.1 only.
ENV RW_HOST=0.0.0.0 RW_PORT=8765 RW_RUNS_DIR=/app/runs/demo PYTHONUNBUFFERED=1
RUN mkdir -p /app/runs/demo /app/models && chown -R roadwatch /app/runs
USER roadwatch
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health')" || exit 1

CMD ["python", "-m", "src.roadwatch.web"]
