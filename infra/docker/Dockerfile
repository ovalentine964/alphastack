# =============================================================================
# AlphaStack – Multi-stage Docker build (with Rust core)
# =============================================================================

# --------------- Stage 1: Build Rust core -----------------------------------
FROM python:3.12-slim AS rust-builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Install maturin for building PyO3 extensions
RUN pip install --no-cache-dir maturin>=1.4.0

# Build the Rust extension
COPY src/rust_core/ src/rust_core/
WORKDIR /build/src/rust_core
RUN maturin build --release --out /build/wheels
WORKDIR /build


# --------------- Stage 2: Build Python dependencies -------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# System deps for TA-Lib, psycopg2, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install TA-Lib C library
RUN wget -q https://github.com/TA-Lib/ta-lib/releases/download/v0.6.4/ta-lib-0.6.4-src.tar.gz \
    && tar -xzf ta-lib-0.6.4-src.tar.gz \
    && cd ta-lib-0.6.4 \
    && ./configure --prefix=/usr/local \
    && make -j"$(nproc)" && make install \
    && cd .. && rm -rf ta-lib-0.6.4 ta-lib-0.6.4-src.tar.gz

# Copy Rust wheels from stage 1
COPY --from=rust-builder /build/wheels/ /build/wheels/

# Python deps — install Rust wheel first, then project
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir /build/wheels/*.whl || true \
    && pip install --no-cache-dir .


# --------------- Stage 3: runtime ------------------------------------------
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.source="https://github.com/your-org/alphastack"
LABEL org.opencontainers.image.description="AlphaStack Multi-Agent Trading System"
LABEL org.opencontainers.image.licenses="Proprietary"

WORKDIR /app

# Runtime system libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy TA-Lib shared libraries
COPY --from=builder /usr/local/lib/libta_lib* /usr/local/lib/
RUN ldconfig

# Copy installed Python packages
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source
COPY src/ src/
COPY config/ config/

# Non-root user
RUN useradd --create-home --shell /bin/bash alphastack \
    && mkdir -p /app/logs /app/data && chown -R alphastack:alphastack /app
USER alphastack

# Health check — hits the /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

EXPOSE 8000

# Default: run API server. Override via docker-compose command for workers.
CMD ["uvicorn", "alphastack.api.rest.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
