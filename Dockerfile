# =============================================================================
# Frontend builder stage
# -----------------------------------------------------------------------------
# Next.js 16 requires Node.js >= 20.9.0. Debian bookworm's apt ships Node 18,
# so the frontend is built in a dedicated node:20 stage. The bookworm tag is
# chosen so the glibc matches the Python runtime stage below.
# =============================================================================
# pinned — update periodically
FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /app/frontend

ARG NPM_REGISTRY=https://registry.npmjs.org/

# Copy dependency manifests first so npm ci is cached unless they change
COPY frontend/package.json frontend/package-lock.json ./
RUN npm config set registry ${NPM_REGISTRY} && npm ci

# Copy the rest of the frontend source and build
COPY frontend/ ./
RUN npm run build


# =============================================================================
# Python backend builder stage
# -----------------------------------------------------------------------------
# Node.js/NPM are intentionally NOT installed here anymore: the frontend is
# built in the dedicated node:20-bookworm-slim stage above.
# =============================================================================
# pinned — update periodically
FROM python:3.12.13-slim-bookworm AS builder

# Install uv — pinned to specific version to prevent supply-chain drift
COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /uvx /bin/

# System build dependencies for Python wheels that compile C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Build optimization environment variables
ENV MAKEFLAGS="-j$(nproc)"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

WORKDIR /app

# Copy dependency files and minimal package structure first for better layer caching
COPY pyproject.toml uv.lock ./
COPY open_notebook/__init__.py ./open_notebook/__init__.py

# Install Python dependencies (this layer is cached unless the lockfile changes)
RUN uv sync --frozen --no-dev

# Pre-download tiktoken encoding so the app works offline (issue #264).
# /app/tiktoken-cache is intentionally outside /app/data/ so that volume mounts
# of /app/data (for user data persistence) do not hide the pre-baked encoding.
# config.py reads TIKTOKEN_CACHE_DIR from the environment to pick up this path.
ENV TIKTOKEN_CACHE_DIR=/app/tiktoken-cache
RUN mkdir -p /app/tiktoken-cache && \
    .venv/bin/python -c "import tiktoken; tiktoken.get_encoding('o200k_base')"


# =============================================================================
# Runtime stage
# -----------------------------------------------------------------------------
# Node.js 20 is pulled from the official node image rather than apt because
# Debian bookworm's apt ships Node 18 and Next.js 16's standalone server.js
# requires Node >= 20.9.0. The node:20-bookworm-slim base gives us the same
# glibc/Debian release as python:3.12.13-slim-bookworm, so the binary is
# drop-in compatible without needing a curl|bash installer.
# =============================================================================
# pinned — update periodically
FROM python:3.12.13-slim-bookworm AS runtime

# Runtime system dependencies (no Node from apt — see note above)
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    ffmpeg \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install uv — pinned to same version as builder stage
COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /uvx /bin/

# Node.js 20 runtime (binary copy from the official slim image)
COPY --from=node:20-bookworm-slim /usr/local/bin/node /usr/local/bin/node

WORKDIR /app

# Copy the Python virtual environment from the backend builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy the source code
COPY . /app

# Copy pre-downloaded tiktoken encoding from builder (outside /app/data — volume-mount safe)
COPY --from=builder /app/tiktoken-cache /app/tiktoken-cache

# Ensure uv uses the existing venv without attempting network operations
ENV UV_NO_SYNC=1
ENV VIRTUAL_ENV=/app/.venv
# Point the app at the pre-baked tiktoken encoding (see open_notebook/config.py)
ENV TIKTOKEN_CACHE_DIR=/app/tiktoken-cache

# Bind Next.js to all interfaces (required for Docker networking and reverse proxies)
ENV HOSTNAME=0.0.0.0

# Copy the built frontend from the Node 20 builder stage
COPY --from=frontend-builder /app/frontend/.next/standalone /app/frontend/
COPY --from=frontend-builder /app/frontend/.next/static /app/frontend/.next/static
COPY --from=frontend-builder /app/frontend/public /app/frontend/public
COPY --from=frontend-builder /app/frontend/start-server.js /app/frontend/start-server.js

# Expose ports for Frontend and API
EXPOSE 8502 5055

# Copy and normalize the wait-for-api script
COPY scripts/wait-for-api.sh /app/scripts/wait-for-api.sh
RUN sed -i 's/\r$//' /app/scripts/wait-for-api.sh && chmod +x /app/scripts/wait-for-api.sh

# Copy supervisord configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create runtime directories and a non-root user
RUN mkdir -p /app/data /var/log/supervisor /tmp \
    && groupadd --system notebook \
    && useradd --system --gid notebook --home-dir /app --shell /usr/sbin/nologin notebook \
    && chown -R notebook:notebook /app/data /var/log/supervisor /tmp

# Runtime API URL configuration
# The API_URL environment variable can be set at container runtime to configure
# where the frontend should connect to the API. This allows the same Docker image
# to work in different deployment scenarios without rebuilding.
#
# If not set, the system will auto-detect based on incoming requests.
# Set API_URL when using reverse proxies or custom domains.
#
# Example: docker run -e API_URL=https://your-domain.com/api ...

USER notebook

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
