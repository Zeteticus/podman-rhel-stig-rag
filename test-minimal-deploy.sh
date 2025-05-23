#!/bin/bash
# test-minimal-deploy.sh - Deploy with minimal requirements to isolate issues

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo_status() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo_status "🧪 Testing minimal STIG RAG deployment..."

# Create minimal requirements for testing
cat > requirements-minimal.txt << 'EOF'
fastapi==0.104.0
uvicorn==0.24.0
pydantic==2.4.2
jinja2==3.1.2
python-multipart==0.0.6
EOF

# Create minimal app for testing
cat > test_app.py << 'EOF'
#!/usr/bin/env python3
import uvicorn
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RHEL STIG RAG Test", description="Minimal test version")

# Create templates directory
os.makedirs("templates", exist_ok=True)

# Minimal HTML template
with open("templates/test.html", "w") as f:
    f.write('''
<!DOCTYPE html>
<html>
<head><title>STIG RAG Test</title></head>
<body>
    <h1>🛡️ RHEL STIG RAG Test</h1>
    <p>This is a minimal test version to verify container functionality.</p>
    <form action="/test" method="post">
        <input type="text" name="test_input" placeholder="Enter test message">
        <button type="submit">Test</button>
    </form>
    {% if message %}
    <div style="background: #e8f5e8; padding: 10px; margin: 10px 0;">
        <h3>Test Result:</h3>
        <p>{{ message }}</p>
    </div>
    {% endif %}
</body>
</html>
    ''')

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("test.html", {"request": request})

@app.post("/test", response_class=HTMLResponse)
def test_form(request: Request, test_input: str = Form(...)):
    message = f"✅ Test successful! Your input: {test_input}"
    return templates.TemplateResponse("test.html", {"request": request, "message": message})

@app.get("/health")
def health():
    return {
        "status": "healthy", 
        "message": "Minimal STIG RAG test system operational",
        "version": "test"
    }

@app.get("/api/test")
def api_test():
    return {"message": "API test successful", "status": "ok"}

if __name__ == "__main__":
    logger.info("🚀 Starting minimal RHEL STIG RAG test system...")
    logger.info("🌐 Web Interface: http://localhost:8000")
    logger.info("🔍 Health Check: http://localhost:8000/health")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
EOF

# Create minimal Containerfile
cat > Containerfile.test << 'EOF'
FROM registry.access.redhat.com/ubi9/ubi:latest

WORKDIR /app

# Install basic dependencies
RUN dnf update -y && \
    dnf install -y python3 python3-pip && \
    dnf clean all

# Create user
RUN useradd -r -u 1001 -g 0 -m -d /app -s /bin/bash testuser && \
    chown -R testuser:0 /app && \
    chmod -R g=u /app

# Copy files
COPY --chown=testuser:0 requirements-minimal.txt /app/requirements.txt
COPY --chown=testuser:0 test_app.py /app/

# Install Python packages with ignore-installed to avoid RPM conflicts
RUN python3 -m pip install --no-cache-dir --ignore-installed -r requirements.txt

# Create directories
RUN mkdir -p /app/templates && chown -R testuser:0 /app

USER testuser

ENV PYTHONUNBUFFERED=1 PORT=8000

EXPOSE 8000

CMD ["python3", "/app/test_app.py"]
EOF

# Build and run test container
CONTAINER_NAME="stig-rag-test"
IMAGE_NAME="localhost/rhel-stig-rag:test"

echo_status "Building test container..."
podman build -t "$IMAGE_NAME" -f Containerfile.test .

echo_status "Stopping any existing test containers..."
podman stop "$CONTAINER_NAME" 2>/dev/null || true
podman rm "$CONTAINER_NAME" 2>/dev/null || true

echo_status "Starting test container..."
podman run -d \
    --name "$CONTAINER_NAME" \
    -p 8001:8000 \
    "$IMAGE_NAME"

echo_status "Waiting for test service..."
for i in {1..30}; do
    if curl -s -f "http://localhost:8001/health" >/dev/null 2>&1; then
        echo_status "✅ Test container is working!"
        echo ""
        echo_status "🌐 Test Interface: http://localhost:8001"
        echo_status "🔍 Health Check: http://localhost:8001/health"
        echo_status "📡 API Test: http://localhost:8001/api/test"
        echo ""
        
        # Test the health endpoint
        echo_status "Testing health endpoint:"
        curl -s "http://localhost:8001/health" | python3 -m json.tool
        
        echo ""
        echo_status "✅ Minimal deployment successful!"
        echo_warn "Now we know the basic container setup works."
        echo_warn "The issue is likely with ChromaDB or the enhanced application."
        break
    fi
    echo -n "."
    sleep 2
done

if [ $i -eq 30 ]; then
    echo_error "Test container also failed. Checking logs..."
    podman logs --tail 20 "$CONTAINER_NAME"
    echo_error "Even minimal container failed - there's a fundamental issue."
else
    echo ""
    echo_status "🔧 Next steps to fix the main deployment:"
    echo "1. The basic container works, so the issue is with dependencies"
    echo "2. Try deploying without ChromaDB first"
    echo "3. Add dependencies incrementally to isolate the problem"
    echo "4. Check if it's a ChromaDB/SQLite compatibility issue"
fi

echo ""
echo_status "Test container logs:"
podman logs --tail 10 "$CONTAINER_NAME"
