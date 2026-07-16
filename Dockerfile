FROM python:3.12-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy ONLY backend files (not mobile, docs, desktop, etc.)
COPY live_server.py .
COPY start.py .
COPY test_startup.py .
COPY src/ src/
COPY config/ config/

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

COPY test_startup.py .
RUN python3 test_startup.py
CMD ["python", "start.py"]
