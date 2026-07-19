# =============================================================================
# AlphaStack MT5 Bridge — Dockerfile
# =============================================================================
# Base image: MT5 running under Wine with VNC access.
# Layers AlphaStack bridge_api.py + Prometheus metrics on top.
# =============================================================================

FROM jsfrnc/mt5-docker-api:latest

# Install bridge dependencies
RUN pip install --no-cache-dir \
    requests \
    uvicorn[standard] \
    fastapi \
    websockets \
    prometheus-client

# Fix: add wine_version to DefaultSettings (missing in some base image versions)
RUN sed -i 's/required_packages = \[/wine_version = "wine-11.0"\n        required_packages = [/' /app/Metatrader/start.py 2>/dev/null || true

# Copy AlphaStack bridge API
COPY bridge_api.py /app/bridge_api.py
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Environment defaults
ENV API_PORT=8080
ENV VNC_PORT=3000
ENV VNC_PASSWORD=alphastack
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

EXPOSE 3000 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -sf http://localhost:8080/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
