# Quant Signal API + Dashboard - Production Container
FROM python:3.12-slim
RUN pip install --upgrade pip

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps for yfinance, ta, torch
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cache layer)
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY service/ ./service/
COPY features/ ./features/
COPY rebuild_cache_v2.py ./rebuild_cache_v2.py

# Expose ports
EXPOSE 8000 8501

# Default command runs API; override in docker-compose for dashboard
CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8000"]
