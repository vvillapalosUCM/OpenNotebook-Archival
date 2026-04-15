# Build stage
FROM python:3.12.13-slim-bookworm AS builder  # pinned — update periodically

# Install uv — pinned to specific version to prevent supply-chain drift
COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /uvx /bin/

# Install system dependencies required for building certain Python packages
# Use Debian packages for Node.js/NPM instead of curl|bash installer scripts.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Set build optimization environment variables
ENV MAKEFLAGS="-j$(nproc)"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Set the working directory in the container to /app
WORKDIR /app

# Copy dependency files and minimal package structure first for better layer caching
COPY pyproject.toml uv.lock ./
COPY open_notebook/__init__.py ./open_notebook/__init__.py

# Install dependencies with optimizations (this layer will be cached unless dependencies change)
RUN uv sync --frozen --no-dev

# Pre-download tiktoken encoding so the app works offline (issue #264).
# /app/tiktoken-cache is intentionally outside /app/data/ so that volume mounts
# of /app/data (for user data persistence) do not hide the pre-baked encoding.
# config.py reads TIKTOKEN_CACHE_DIR from the environment to pick up this path.
ENV TIKTOKEN_CACHE_DIR=/app/tiktoken-cache
RUN mkdir -p /app/tiktoken-cache && \
    .venv/bin/python -c "import tiktoken; tiktoken.get_encoding('o200k_base')"

# Copy the rest of the application code
COPY . /app

# Install frontend dependencies and build
WORKDIR /app/frontend
ARG NPM_REGISTRY=https://registry.npmjs.org/
COPY frontend/package.json frontend/package-lock.json ./
RUN npm config set registry ${NPM_REGISTRY}
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Return to app root
WORKDIR /app

# Runtime stage
FROM python:3.12.13-slim-bookworm AS runtime  # pinned — update periodically

# Install only runtime system dependencies (no build tools)
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install uv — pinned to same version as builder stage
COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /uvx /bin/

# Set the working directory in the container to /app
WORKDIR /app

# Copy the virtual environment from builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy the source code (the rest)
COPY . /app

# Copy pre-downloaded tiktoken encoding from builder (outside /data/ — volume-mount safe)
COPY --from=builder /app/tiktoken-cache /app/tiktoken-cache

# Ensure uv uses the existing venv without attempting network operations
ENV UV_NO_SYNC=1
ENV VIRTUAL_ENV=/app/.venv
# Point the app at the pre-baked tiktoken encoding (see open_notebook/config.py)
ENV TIKTOKEN_CACHE_DIR=/app/tiktoken-cache

# Bind Next.js to all interfaces (required for Docker networking and reverse proxies)
ENV HOSTNAME=0.0.0.0

# Copy built frontend from builder stage
COPY --from=builder /app/frontend/.next/standalone /app/frontend/
COPY --from=builder /app/frontend/.next/static /app/frontend/.next/static
COPY --from=builder /app/frontend/public /app/frontend/public
COPY --from=builder /app/frontend/start-server.js /app/frontend/start-server.js

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

# Runtime API URL Configuration
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
