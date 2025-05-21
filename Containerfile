# Use Red Hat UBI as base for better RHEL compatibility
FROM registry.access.redhat.com/ubi9/ubi:latest

# Add environment variable for container namespaces
ENV _CONTAINERS_USERNS_CONFIGURED=1

# Metadata
LABEL name="rhel-stig-rag" \
      version="1.0.0" \
      description="RHEL STIG RAG System - Podman Container" \
      maintainer="stig-rag-team" \
      io.opencontainers.image.title="RHEL STIG RAG System" \
      io.opencontainers.image.description="AI-powered RHEL STIG compliance assistant" \
      io.opencontainers.image.version="1.0.0"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN dnf update -y && \
    dnf install -y \
        python3 \
        python3-pip \
        python3-devel \
        gcc \
        gcc-c++ \
        git \
        curl \
        unzip \
        procps-ng \
        shadow-utils \
        && dnf clean all \
        && rm -rf /var/cache/dnf

# Create non-root user for security with specific UID/GID for better compatibility
RUN useradd -r -u 1001 -g 0 -m -d /app -s /bin/bash stigrag && \
    chown -R stigrag:0 /app && \
    chmod -R g=u /app

# Copy requirements first for better layer caching
COPY --chown=stigrag:0 requirements.txt /app/

# Install Python dependencies with optimizations and relaxed cgroup constraints
RUN PYTHONUNBUFFERED=1 \
    python3 -m pip install --no-cache-dir --upgrade pip setuptools wheel && \
    # Skip cgroups checks on pip install 
    MALLOC_ARENA_MAX=1 \
    python3 -m pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=stigrag:0 rhel_stig_rag.py /app/
COPY --chown=stigrag:0 stig_client.py /app/
COPY --chown=stigrag:0 stig_data_collector.py /app/

# Create necessary directories with proper permissions
RUN mkdir -p /app/stig_data /app/stig_chroma_db /app/logs /app/tmp && \
    chown -R stigrag:0 /app && \
    chmod -R g+w /app

# Create runtime script for better cgroups compatibility
RUN echo '#!/bin/bash\n\
# Startup wrapper with cgroups error handling\n\
echo "Starting RHEL STIG RAG system..."\n\
if [ -f "/proc/1/cgroup" ]; then\n\
  echo "Container cgroups configuration:"\n\
  grep -v "^\#" /proc/1/cgroup | sort\n\
fi\n\
# Run the application\n\
exec python3 /app/rhel_stig_rag.py\n\
' > /app/start.sh && \
    chmod +x /app/start.sh

# Switch to non-root user
USER stigrag

# Set environment variables
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    HOME=/app \
    PORT=8000 \
    MALLOC_ARENA_MAX=2 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    ENABLE_CGROUPS_COMPAT=1

# Expose port
EXPOSE 8000

# Health check with retry logic and timeout adjustments
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command using the wrapper script
CMD ["/app/start.sh"]
