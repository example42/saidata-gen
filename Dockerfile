# Multi-stage build for saidata-gen Docker image
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY pyproject.toml README.md LICENSE ./
COPY saidata_gen/ ./saidata_gen/
COPY schemas/ ./schemas/
COPY examples/ ./examples/

# Install the package
RUN pip install --no-cache-dir -e .[rag,ml]

# Production stage
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SAIDATA_GEN_CACHE_DIR=/cache \
    SAIDATA_GEN_CONFIG_DIR=/config

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash saidata

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/saidata-gen /usr/local/bin/saidata-gen

# Create directories for cache and config
RUN mkdir -p /cache /config /workspace && \
    chown -R saidata:saidata /cache /config /workspace

# Switch to non-root user
USER saidata
WORKDIR /workspace

# Set up default configuration
RUN saidata-gen config init --config-dir /config

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD saidata-gen --version || exit 1

# Default command
ENTRYPOINT ["saidata-gen"]
CMD ["--help"]

# Labels
LABEL org.opencontainers.image.title="saidata-gen" \
      org.opencontainers.image.description="Standalone saidata YAML generator for software metadata" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.authors="SAI Team <team@sai.dev>" \
      org.opencontainers.image.url="https://github.com/sai/saidata-gen" \
      org.opencontainers.image.source="https://github.com/sai/saidata-gen" \
      org.opencontainers.image.licenses="MIT"