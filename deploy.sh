#!/bin/bash
# deploy-text-search.sh - Deploy STIG RAG with text search (no ChromaDB)

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo_status() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }
echo_info() { echo -e "${BLUE}[INFO]${NC} $1"; }

CONTAINER_NAME="stig-rag-textsearch"
IMAGE_NAME="localhost/rhel-stig-rag:textsearch"
HOST_PORT="8000"

echo_status "🚀 Deploying RHEL STIG RAG with Text Search (ChromaDB-free)..."

# 1. Create requirements without ChromaDB
cat > requirements-textsearch.txt << 'EOFR'
fastapi==0.104.0
uvicorn==0.24.0
pydantic==2.4.2
jinja2==3.1.2
python-multipart==0.0.6
EOFR

# 2. Copy the text search app
echo_status "Setting up text search application..."
# Using existing rhel_stig_rag.py

# 3. Create simple Containerfile
cat > Containerfile.textsearch << 'EOFC'
FROM registry.access.redhat.com/ubi9/ubi:latest

WORKDIR /app

# Install minimal dependencies
RUN dnf update -y && \
    dnf install -y python3 python3-pip && \
    dnf clean all

# Create user
RUN useradd -r -u 1001 -g 0 -m -d /app -s /bin/bash stigrag && \
    chown -R stigrag:0 /app && \
    chmod -R g=u /app

# Copy requirements and install
COPY --chown=stigrag:0 requirements-textsearch.txt /app/requirements.txt
RUN python3 -m pip install --no-cache-dir --ignore-installed -r requirements.txt

# Copy application
COPY --chown=stigrag:0 rhel_stig_rag.py /app/

# Create directories
RUN mkdir -p /app/stig_data /app/templates && \
    chown -R stigrag:0 /app

USER stigrag

ENV PYTHONUNBUFFERED=1 PORT=8000

EXPOSE 8000

CMD ["python3", "/app/rhel_stig_rag.py"]
EOFC

# 4. Stop existing containers
echo_status "Stopping existing containers..."
podman stop "$CONTAINER_NAME" 2>/dev/null || true
podman rm "$CONTAINER_NAME" 2>/dev/null || true
podman stop "stig-rag-enhanced" 2>/dev/null || true
podman rm "stig-rag-enhanced" 2>/dev/null || true
podman stop "stig-rag" 2>/dev/null || true
podman rm "stig-rag" 2>/dev/null || true

# 5. Build the container
echo_status "Building text search container..."
podman build -t "$IMAGE_NAME" -f Containerfile.textsearch --no-cache .

# 6. Create persistent volumes
echo_status "Creating persistent storage..."
podman volume create stig-data-vol 2>/dev/null || echo_warn "Volume already exists"

# 7. Start the container
echo_status "Starting text search STIG RAG container..."
podman run -d \
    --name "$CONTAINER_NAME" \
    -p "$HOST_PORT:8000" \
    -v stig-data-vol:/app/stig_data:Z \
    --restart unless-stopped \
    "$IMAGE_NAME"

# 8. Wait for startup and test
echo_status "Waiting for service to start..."
for i in {1..30}; do
    if curl -s -f "http://localhost:$HOST_PORT/health" >/dev/null 2>&1; then
        echo_status "✅ RHEL STIG RAG with Text Search is ready!"
        echo ""
        echo_info "🌐 Web Interface: http://localhost:$HOST_PORT"
        echo_info "📚 API Documentation: http://localhost:$HOST_PORT/docs"
        echo_info "📊 Data Statistics: http://localhost:$HOST_PORT/api/stats"
        echo_info "🔍 Health Check: http://localhost:$HOST_PORT/health"
        echo ""
        echo_status "🚀 Features Available:"
        echo "   ✓ Web-based STIG JSON file upload"
        echo "   ✓ Fast text search for STIG controls"
        echo "   ✓ Real STIG data integration"
        echo "   ✓ No complex dependencies (ChromaDB-free)"
        echo "   ✓ API endpoints for programmatic access"
        echo "   ✓ Persistent data storage"
        echo ""
        echo_status "📁 To load your STIG data:"
        echo "   1. Open http://localhost:$HOST_PORT in your browser"
        echo "   2. Upload your STIG JSON file"
        echo "   3. Start asking STIG compliance questions!"
        
        # Test the health endpoint
        echo ""
        echo_info "Testing system health:"
        curl -s "http://localhost:$HOST_PORT/health" | python3 -m json.tool
        
        break
    fi
    echo -n "."
    sleep 2
done

if [ $i -eq 30 ]; then
    echo_error "Service failed to start. Checking logs..."
    podman logs --tail 30 "$CONTAINER_NAME"
    echo ""
    echo_error "Container status:"
    podman ps -a --filter name="$CONTAINER_NAME"
else
    echo ""
    echo_status "🎉 Text Search STIG RAG deployment complete!"
    echo_status "System is ready for STIG data upload and queries!"
fi

# Show container logs for verification
echo ""
echo_info "Recent container logs:"
podman logs --tail 5 "$CONTAINER_NAME"
