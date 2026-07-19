# =============================================================================
# AlphaStack — infra/docker/Dockerfile (used by docker-compose)
# =============================================================================
# Multi-stage build: compile native deps, then slim runtime.
# Build context is the repo root (../.. from infra/docker/).
# =============================================================================

# --------------- Stage 1: Build Rust core (optional) ------------------------
FROM python:3.12-slim AS rust-builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl pkg-config libssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

RUN pip install --no-cache-dir "maturin>=1.4.0"

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

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential wget libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# TA-Lib C library
RUN wget -q https://github.com/TA-Lib/ta-lib/releases/download/v0.6.4/ta-lib-0.6.4-src.tar.gz \
    && tar -xzf ta-lib-0.6.4-src.tar.gz \
    && cd ta-lib-0.6.4 \
    && ./configure --prefix=/usr/local \
    && make -j"$(nproc)" && make install \
    && cd .. && rm -rf ta-lib-0.6.4 ta-lib-0.6.4-src.tar.gz

COPY --from=rust-builder /build/wheels/ /build/wheels/

COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir /build/wheels/*.whl 2>/dev/null || true \
    && pip install --no-cache-dir .


# --------------- Stage 3: Runtime -------------------------------------------
FROM python:3.12-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl tini \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/libta_lib* /usr/local/lib/
RUN ldconfig

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY start.py .
COPY src/ src/
COPY config/ config/

RUN useradd --create-home --shell /bin/bash alphastack \
    && mkdir -p /app/logs /app/data \
    && chown -R alphastack:alphastack /app

EXPOSE 8000

USER alphastack

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

ENTRYPOINT ["tini", "--"]

# Default: API server.  docker-compose overrides CMD for engine worker.
CMD ["python", "start.py"]
