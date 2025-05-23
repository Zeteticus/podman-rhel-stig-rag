#!/bin/bash
# deploy-enhanced-rag.sh - Deploy STIG RAG with real data loading capability

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

CONTAINER_NAME="stig-rag-enhanced"
IMAGE_NAME="localhost/rhel-stig-rag:enhanced"
HOST_PORT="8000"

echo_status "🚀 Deploying Enhanced RHEL STIG RAG with Data Loading..."

# 1. Copy the enhanced application
echo_status "Setting up enhanced application..."
cp enhanced_app.py rhel_stig_rag.py

# 2. Stop current container if running
echo_status "Stopping existing containers..."
podman stop "$CONTAINER_NAME" 2>/dev/null || true
podman rm "$CONTAINER_NAME" 2>/dev/null || true

# 3. Build the enhanced container
echo_status "Building enhanced container image..."
podman build -t "$IMAGE_NAME" -f Containerfile.selinux --no-cache .

# 4. Create persistent volume for STIG data
echo_status "Creating persistent storage for STIG data..."
podman volume create stig-data-vol 2>/dev/null || echo_warn "Volume already exists"
podman volume create stig-chroma-vol 2>/dev/null || echo_warn "Volume already exists"

# 5. Start the enhanced container
echo_status "Starting enhanced STIG RAG container..."
podman run -d \
    --name "$CONTAINER_NAME" \
    -p "$HOST_PORT:8000" \
    -v stig-data-vol:/app/stig_data:Z \
    -v stig-chroma-vol:/app/stig_chroma_db:Z \
    --security-opt label=disable \
    --shm-size=256m \
    --memory=2g \
    --restart unless-stopped \
    "$IMAGE_NAME"

# 6. Wait for startup and test
echo_status "Waiting for enhanced service to start..."
for i in {1..60}; do
    if curl -s -f "http://localhost:$HOST_PORT/health" >/dev/null 2>&1; then
        echo_status "✅ Enhanced RHEL STIG RAG is ready!"
        echo ""
        echo_info "🌐 Web Interface: http://localhost:$HOST_PORT"
        echo_info "📚 API Documentation: http://localhost:$HOST_PORT/docs"
        echo_info "📊 Data Statistics: http://localhost:$HOST_PORT/api/stats"
        echo_info "🔍 Health Check: http://localhost:$HOST_PORT/health"
        echo ""
        echo_status "🚀 Enhanced Features Available:"
        echo "   ✓ Web-based STIG JSON file upload"
        echo "   ✓ ChromaDB vector search for semantic matching"
        echo "   ✓ Real STIG data integration"
        echo "   ✓ Intelligent control search and retrieval"
        echo "   ✓ API endpoints for programmatic access"
        echo "   ✓ Persistent data storage across container restarts"
        echo ""
        echo_status "📁 To load your STIG data:"
        echo "   1. Open http://localhost:$HOST_PORT in your browser"
        echo "   2. Use the 'Load STIG Data' section to upload your JSON file"
        echo "   3. Wait for processing to complete"
        echo "   4. Start asking STIG compliance questions!"
        echo ""
        echo_status "💡 Example API usage:"
        echo "   # Upload via API"
        echo "   curl -X POST http://localhost:$HOST_PORT/upload-stig \\"
        echo "        -F 'stig_file=@/path/to/your/stig-data.json'"
        echo ""
        echo "   # Query via API"
        echo "   curl -X POST http://localhost:$HOST_PORT/api/query \\"
        echo "        -H 'Content-Type: application/json' \\"
        echo "        -d '{\"question\": \"How do I configure SELinux?\", \"rhel_version\": \"9\"}'"
        break
    fi
    echo -n "."
    sleep 2
done

if [ $i -eq 60 ]; then
    echo_error "Service failed to start within 2 minutes. Checking logs..."
    podman logs "$CONTAINER_NAME" --tail 50
    echo ""
    echo_error "Container status:"
    podman ps -a --filter name="$CONTAINER_NAME"
else
    echo ""
    echo_status "🎉 Enhanced STIG RAG deployment complete!"
    echo_status "Ready to load STIG data and process compliance queries!"
fi
