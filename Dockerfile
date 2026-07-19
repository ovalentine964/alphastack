# =============================================================================
# AlphaStack — Multi-stage Production Dockerfile
# =============================================================================
# Stage 1: builder   — compile native deps (TA-Lib, Rust/PyO3)
# Stage 2: runtime   — slim image with only what's needed to run
# =============================================================================

# --------------- Stage 1: Build Rust core (optional) ------------------------
FROM python:3.12-slim AS rust-builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl pkg-config libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Rust toolchain
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

RUN pip install --no-cache-dir "maturin>=1.4.0"

# Copy Rust source and build PyO3 wheel (skip if src/rust_core doesn't exist)
COPY src/rust_core/ src/rust_core/
WORKDIR /build/src/rust_core
RUN if [ -f Cargo.toml ]; then \
        maturin build --release --out /build/wheels; \
    else \
        mkdir -p /build/wheels; \
    fi
WORKDIR /build


# --------------- Stage 2: Build Python dependencies -------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# System deps for TA-Lib C library, psycopg2, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential wget libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install TA-Lib C library (v0.6.4)
RUN wget -q https://github.com/TA-Lib/ta-lib/releases/download/v0.6.4/ta-lib-0.6.4-src.tar.gz \
    && tar -xzf ta-lib-0.6.4-src.tar.gz \
    && cd ta-lib-0.6.4 \
    && ./configure --prefix=/usr/local \
    && make -j"$(nproc)" && make install \
    && cd .. && rm -rf ta-lib-0.6.4 ta-lib-0.6.4-src.tar.gz

# Copy Rust wheels from stage 1 (may be empty)
COPY --from=rust-builder /build/wheels/ /build/wheels/

# Install Python dependencies
# Strategy: install Rust wheels first (ignore if none), then full project
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir /build/wheels/*.whl 2>/dev/null || true \
    && pip install --no-cache-dir .


# --------------- Stage 3: Runtime -------------------------------------------
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.source="https://github.com/alphastack/alphastack"
LABEL org.opencontainers.image.description="AlphaStack — Multi-Agent AI Trading System"
LABEL org.opencontainers.image.licenses="Proprietary"

WORKDIR /app

# Runtime system libs only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl tini \
    && rm -rf /var/lib/apt/lists/*

# Copy TA-Lib shared libraries from builder
COPY --from=builder /usr/local/lib/libta_lib* /usr/local/lib/
RUN ldconfig

# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source and config
COPY start.py .
COPY src/ src/
COPY config/ config/

# Create non-root user
RUN useradd --create-home --shell /bin/bash alphastack \
    && mkdir -p /app/logs /app/data \
    && chown -R alphastack:alphastack /app

# Prometheus metrics port
EXPOSE 8000

USER alphastack

# Healthcheck — hits the FastAPI /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

# Use tini as PID 1 for proper signal handling
ENTRYPOINT ["tini", "--"]

# Default: run API server via start.py (wires up all subsystems)
# Override CMD in docker-compose for engine worker
CMD ["python", "start.py"]
