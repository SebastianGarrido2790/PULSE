# syntax=docker/dockerfile:1

# ==============================================================================
# PULSE — Multi-Stage Production Dockerfile
#
# Stage 1 (builder): Clean dependency resolution and virtual environment creation via uv.
# Stage 2 (runtime): Hardened, non-root execution layer with baked model artifacts
#                    and embedded Tactical Cockpit UI.
#
# Authority: Phase 7 Decisions D-4, D-5, D-7, D-12.
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Builder
# ------------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:latest AS uv-binary
FROM python:3.11-slim AS builder

# Inherit uv binary from official distribution
COPY --from=uv-binary /uv /bin/uv

# Configure uv compilation and execution flags
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Copy locked dependency definitions
COPY pyproject.toml uv.lock ./

# Install locked production dependencies into /app/.venv
RUN uv sync --frozen --no-dev --no-install-project --no-editable


# ------------------------------------------------------------------------------
# Stage 2: Runtime
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# Security hardening: Create non-root system group and user (D-5)
RUN addgroup --system --gid 10001 pulsegroup && \
    adduser --system --uid 10001 --gid 10001 --home /app --no-create-home pulseuser

# Copy uv binary to support runtime CLI entrypoint overrides (D-4)
COPY --from=uv-binary /uv /bin/uv

# Copy standalone virtual environment from builder stage
COPY --from=builder /app/.venv /app/.venv

# Set runtime environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Package application source, configuration, and versioned model/data artifacts (D-4, D-7)
COPY --chown=pulseuser:pulsegroup src/ /app/src/
COPY --chown=pulseuser:pulsegroup artifacts/ /app/artifacts/
COPY --chown=pulseuser:pulsegroup params.yaml /app/params.yaml
COPY --chown=pulseuser:pulsegroup pyproject.toml /app/pyproject.toml
COPY --chown=pulseuser:pulsegroup uv.lock /app/uv.lock

# Prepare logs and artifacts directory with non-root ownership for file handlers & SQLite (D-6)
RUN mkdir -p /app/logs /app/artifacts && \
    chown -R pulseuser:pulsegroup /app/logs /app/artifacts

# Switch to unprivileged non-root user
USER pulseuser

# Expose FastAPI / Tactical Cockpit UI port
EXPOSE 8000

# Container healthcheck probing /health endpoint via Python standard library (D-12)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').getcode() == 200 else 1)"

# Default command: launch FastAPI server with Tactical Cockpit UI (D-4, D-12)
CMD ["python", "-m", "src.api.main"]
