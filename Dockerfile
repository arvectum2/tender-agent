# syntax=docker/dockerfile:1.7
# Tender Agent Python 3.15.2 production candidate; release remains gated.
# Rust toolchain is present only in the builder, never in runtime.
FROM rust:1.100-slim-trixie AS rust-toolchain

FROM python:3.15.2-slim-trixie AS wheel-builder
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CARGO_HOME=/usr/local/cargo \
    RUSTUP_HOME=/usr/local/rustup \
    PATH="/usr/local/cargo/bin:/opt/venv/bin:/usr/local/bin:/usr/bin:/bin" \
    CARGO_BUILD_JOBS=2
COPY --from=rust-toolchain /usr/local/cargo /usr/local/cargo
COPY --from=rust-toolchain /usr/local/rustup /usr/local/rustup
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential pkg-config ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
COPY requirements-runtime.lock /tmp/requirements.lock
RUN python -m pip install --no-cache-dir "pip==26.3" \
    && python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock
WORKDIR /app
COPY pyproject.toml README.md ./
COPY alembic.ini ./
COPY src ./src
COPY config/daily_tender_profiles ./config/daily_tender_profiles
COPY scripts ./scripts
COPY docs ./docs
COPY demo_data ./demo_data
COPY migrations ./migrations
RUN python -m pip install --no-cache-dir setuptools wheel \
    && python -m pip install --no-cache-dir --no-build-isolation --no-deps . \
    && python -m pip check \
    && python -c "import fastapi,pydantic_core,sqlalchemy,redis;print('PY315_IMPORTS_OK')"

FROM python:3.15.2-slim-trixie AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:/usr/local/bin:/usr/bin:/bin"
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    wv libarchive-tools \
    && rm -rf /var/lib/apt/lists/*
COPY --from=wheel-builder /opt/venv /opt/venv
COPY --from=wheel-builder /app /app
RUN python -m pip check && ! command -v gcc \
    && mkdir -p /app/data /app/artifacts /app/eis-archives /home/app \
    && chown -R 10001:10001 /app/data /app/artifacts /app/eis-archives /home/app
ENV HOME=/home/app
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn","src.main:app","--host","0.0.0.0","--port","8000","--proxy-headers"]
