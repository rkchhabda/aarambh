# Quant Signal API — Production Container (Render-optimized)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps for yfinance, ta, and healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cache layer) — lean set, no torch/streamlit
COPY requirements-render.txt .
RUN pip install --upgrade pip && pip install -r requirements-render.txt

# Copy application code
COPY service/ ./service/
COPY features/ ./features/
COPY scripts/ ./scripts/
COPY rebuild_cache_v2.py ./rebuild_cache_v2.py

# Render injects PORT env var (default 10000)
EXPOSE 10000

# Use shell form so $PORT is expanded at runtime
CMD sh -c "uvicorn service.app:app --host 0.0.0.0 --port ${PORT:-10000}"
