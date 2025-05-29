# Optimized Containerfile for RHEL STIG RAG System
# This builds a container with:
# - Pre-loaded STIG data and embeddings
# - Semantic search capabilities
# - Redis caching support
# - Performance optimizations

FROM registry.access.redhat.com/ubi9/ubi-minimal:latest

# Metadata
LABEL maintainer="STIG RAG Team" \
      description="RHEL STIG RAG System with Semantic Search" \
      version="2.0"

# Install system dependencies
RUN microdnf install -y \
    python3.11 \
    python3.11-pip \
    python3.11-devel \
    gcc \
    g++ \
    make \
    shadow-utils \
    && microdnf clean all

# Create non-root user for security
RUN useradd -m -u 1001 -s /bin/bash stigrag

# Set working directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY --chown=stigrag:stigrag requirements.txt .

# Install Python dependencies as root (for system-wide access)
RUN pip3.11 install --no-cache-dir --upgrade pip && \
    pip3.11 install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p /app/data /app/cache /app/logs /app/static && \
    chown -R stigrag:stigrag /app

# Switch to non-root user
USER stigrag

# Copy application files
COPY --chown=stigrag:stigrag load_stig_data.py .
COPY --chown=stigrag:stigrag app.py .
COPY --chown=stigrag:stigrag startup.sh .

# Make scripts executable
RUN chmod +x startup.sh load_stig_data.py

# Copy static files for web interface
COPY --chown=stigrag:stigrag static/ ./static/

# Copy STIG data file if it exists at build time
# This is optional - can also be mounted at runtime
COPY --chown=stigrag:stigrag stig_data.json* /app/data/

# Pre-build the embeddings cache during image build
# This significantly speeds up container startup
RUN if [ -f /app/data/stig_data.json ]; then \
        echo "Pre-building STIG embeddings cache..." && \
        python3.11 load_stig_data.py || echo "Cache pre-build failed, will build at runtime"; \
    else \
        echo "No STIG data file found, skipping cache pre-build"; \
    fi

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_PORT=8000 \
    REDIS_HOST=localhost \
    REDIS_PORT=6379 \
    LOG_LEVEL=INFO \
    WORKERS=4 \
    CACHE_DIR=/app/cache \
    DATA_DIR=/app/data

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Volume mount points
# These allow data persistence and can be overridden at runtime
VOLUME ["/app/data", "/app/cache", "/app/logs"]

# Set the entrypoint to our startup script
ENTRYPOINT ["/app/startup.sh"]

# Alternative: Direct command (if not using startup.sh)
# CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--loop", "uvloop"]
