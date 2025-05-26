#!/bin/bash
# deploy-text-search.sh - Deploy STIG RAG with Llama 3.2 Integration

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

# Parse command line arguments
STIG_FILE_PATH=""
SHOW_HELP=false

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -f, --stig-file PATH    Auto-load STIG JSON file from PATH"
    echo "  -h, --help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Deploy without auto-loading"
    echo "  $0 -f /path/to/rhel8-stig.json      # Auto-load STIG file on startup"
    echo "  $0 --stig-file ./stig-data.json     # Auto-load local STIG file"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--stig-file)
            STIG_FILE_PATH="$2"
            shift 2
            ;;
        -h|--help)
            SHOW_HELP=true
            shift
            ;;
        *)
            echo_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

if [ "$SHOW_HELP" = true ]; then
    usage
    exit 0
fi

echo_status "🚀 Deploying RHEL STIG RAG with Llama 3.2 Integration..."

# Validate STIG file if provided
VOLUME_ARGS=""
ENV_STIG_ARGS=""
if [ -n "$STIG_FILE_PATH" ]; then
    if [ ! -f "$STIG_FILE_PATH" ]; then
        echo_error "STIG file not found: $STIG_FILE_PATH"
        exit 1
    fi
    
    # Convert to absolute path
    STIG_FILE_PATH=$(realpath "$STIG_FILE_PATH")
    echo_status "📁 Auto-load STIG file: $STIG_FILE_PATH"
    
    # Validate it's a JSON file
    if ! python3 -c "import json; json.load(open('$STIG_FILE_PATH'))" 2>/dev/null; then
        echo_error "Invalid JSON file: $STIG_FILE_PATH"
        exit 1
    fi
    
    echo_status "✅ STIG JSON file validated"
    VOLUME_ARGS="-v $STIG_FILE_PATH:/app/auto-load-stig.json:ro,Z"
    ENV_STIG_ARGS="-e AUTO_LOAD_STIG_PATH=/app/auto-load-stig.json"
fi

# Check if Ollama is running
echo_status "Checking Ollama availability..."
if curl -s -f "http://localhost:11434/api/tags" >/dev/null 2>&1; then
    echo_status "✅ Ollama is running and accessible"
    
    # Check if llama3.2:3b model is available
    if curl -s "http://localhost:11434/api/tags" | grep -q "llama3.2:3b\|llama3.2:latest"; then
        echo_status "✅ Llama 3.2 model found"
    else
        echo_warn "⚠️  Llama 3.2 model not found. Consider running: ollama pull llama3.2:3b"
    fi
else
    echo_warn "⚠️  Ollama not accessible at localhost:11434"
    echo_warn "    Install Ollama and run: ollama serve"
    echo_warn "    Then: ollama pull llama3.2:3b"
    echo_warn "    The application will still work but without AI features"
fi

# 1. Create requirements with necessary dependencies
cat > requirements-textsearch.txt << 'EOFR'
fastapi==0.104.0
uvicorn==0.24.0
pydantic==2.4.2
jinja2==3.1.2
python-multipart==0.0.6
requests==2.31.0
EOFR

# 2. Copy the text search app
echo_status "Setting up Llama-integrated application..."
# Using existing rhel_stig_rag.py with Llama integration

# 3. Create enhanced Containerfile
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

ENV PYTHONUNBUFFERED=1 
ENV PORT=8000
ENV OLLAMA_BASE_URL=http://host.containers.internal:11434
ENV LLAMA_MODEL=llama3.2:3b
ENV AUTO_LOAD_STIG_PATH=""

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
echo_status "Building Llama-integrated container..."
podman build -t "$IMAGE_NAME" -f Containerfile.textsearch --no-cache .

# 6. Create persistent volumes
echo_status "Creating persistent storage..."
podman volume create stig-data-vol 2>/dev/null || echo_warn "Volume already exists"

# 7. Determine networking approach
echo_status "Configuring container networking for Ollama access..."

# Check if host.containers.internal works
if podman run --rm alpine nslookup host.containers.internal >/dev/null 2>&1; then
    echo_status "Using host.containers.internal for Ollama connectivity"
    NETWORK_ARGS="-p $HOST_PORT:8000"
    ENV_ARGS="-e OLLAMA_BASE_URL=http://host.containers.internal:11434"
else
    echo_status "Using host networking for Ollama connectivity"
    NETWORK_ARGS="--network host"
    ENV_ARGS="-e OLLAMA_BASE_URL=http://localhost:11434"
fi

# 8. Start the container
echo_status "Starting Llama-integrated STIG RAG container..."
podman run -d \
    --name "$CONTAINER_NAME" \
    $NETWORK_ARGS \
    $ENV_ARGS \
    $ENV_STIG_ARGS \
    -e LLAMA_MODEL=llama3.2:3b \
    -v stig-data-vol:/app/stig_data:Z \
    $VOLUME_ARGS \
    --restart unless-stopped \
    "$IMAGE_NAME"

# 9. Wait for startup and test
echo_status "Waiting for service to start..."
for i in {1..30}; do
    if curl -s -f "http://localhost:$HOST_PORT/health" >/dev/null 2>&1; then
        echo_status "✅ RHEL STIG RAG with Llama 3.2 is ready!"
        echo ""
        echo_info "🌐 Web Interface: http://localhost:$HOST_PORT"
        echo_info "📚 API Documentation: http://localhost:$HOST_PORT/docs"
        echo_info "📊 Data Statistics: http://localhost:$HOST_PORT/api/stats"
        echo_info "🔍 Health Check: http://localhost:$HOST_PORT/health"
        echo ""
        echo_status "🚀 Features Available:"
        echo "   ✓ Web-based STIG JSON file upload"
        echo "   ✓ AI-powered STIG question answering (Llama 3.2)"
        echo "   ✓ Fast text search for STIG controls"
        echo "   ✓ Real STIG data integration"
        echo "   ✓ Intelligent contextual responses"
        echo "   ✓ API endpoints for programmatic access"
        echo "   ✓ Persistent data storage"
        echo ""
        echo_status "📁 To use your STIG data:"
        if [ -n "$STIG_FILE_PATH" ]; then
            echo "   ✅ STIG data auto-loaded from: $(basename "$STIG_FILE_PATH")"
            echo "   1. Open http://localhost:$HOST_PORT in your browser"
            echo "   2. Start asking STIG compliance questions immediately!"
            echo "   3. Get AI-powered implementation guidance!"
        else
            echo "   1. Open http://localhost:$HOST_PORT in your browser"
            echo "   2. Upload your STIG JSON file"
            echo "   3. Start asking STIG compliance questions!"
            echo "   4. Get AI-powered implementation guidance!"
        fi

        # Test the health endpoint and show Llama status
        echo ""
        echo_info "Testing system health:"
        HEALTH_RESPONSE=$(curl -s "http://localhost:$HOST_PORT/health")
        echo "$HEALTH_RESPONSE" | python3 -m json.tool
        
        # Check if Llama is working
        if echo "$HEALTH_RESPONSE" | grep -q '"llama_available": true'; then
            echo_status "🦙 Llama 3.2 AI integration: ONLINE"
        else
            echo_warn "🦙 Llama 3.2 AI integration: OFFLINE (text search still works)"
        fi

        # Check STIG data status
        echo ""
        echo_info "Checking STIG data status:"
        STATS_RESPONSE=$(curl -s "http://localhost:$HOST_PORT/api/stats")
        echo "$STATS_RESPONSE" | python3 -m json.tool
        
        if echo "$STATS_RESPONSE" | grep -q '"status": "loaded"'; then
            CONTROL_COUNT=$(echo "$STATS_RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin).get('total_controls', 0))")
            if [ -n "$STIG_FILE_PATH" ]; then
                echo_status "📁 Auto-loaded STIG data: $CONTROL_COUNT controls"
            else
                echo_status "📁 STIG data loaded: $CONTROL_COUNT controls"
            fi
        else
            if [ -n "$STIG_FILE_PATH" ]; then
                echo_warn "⚠️  STIG auto-load may have failed - check container logs"
            else
                echo_info "📁 No STIG data loaded - upload required via web interface"
            fi
        fi

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
    echo ""
    echo_error "Troubleshooting tips:"
    echo "   • Ensure Ollama is running: ollama serve"
    echo "   • Check if model exists: ollama list"
    echo "   • Pull model if needed: ollama pull llama3.2:3b"
    echo "   • Check container networking: podman network ls"
else
    echo ""
    echo_status "🎉 Llama-integrated STIG RAG deployment complete!"
    echo_status "System is ready for intelligent STIG data analysis!"
fi

# Show container logs for verification
echo ""
echo_info "Recent container logs:"
podman logs --tail 10 "$CONTAINER_NAME"

# Show next steps
echo ""
echo_status "🔧 Next Steps:"
if [ -n "$STIG_FILE_PATH" ]; then
    echo "   ✅ STIG data ready - start asking questions immediately!"
    echo "   🌐 Open: http://localhost:$HOST_PORT"
else
    echo "   1. Upload your STIG JSON file via the web interface"
    echo "   🌐 Open: http://localhost:$HOST_PORT"
fi
echo "   2. Ask natural language questions like:"
echo "      • 'How do I configure SSH security?'"
echo "      • 'What are the firewall requirements?'"
echo "      • 'Show me SELinux configuration steps'"
echo "   3. Get AI-powered implementation guidance!"
echo ""
echo_status "🦙 Ollama Integration:"
echo "   • Model: llama3.2:3b"
echo "   • Provides intelligent, contextual responses"
echo "   • Explains STIG controls in practical terms"
echo "   • Offers step-by-step implementation guidance"
echo ""
if [ -n "$STIG_FILE_PATH" ]; then
    echo_status "📁 Auto-loaded STIG file: $(basename "$STIG_FILE_PATH")"
    echo_status "🎉 Ready to use immediately - no upload required!"
else
    echo_info "💡 Tip: Use -f flag to auto-load STIG file on future deployments"
    echo "   Example: $0 -f /path/to/your-stig.json"
fi
