#!/bin/bash

# Working deployment script - No Redis, No ML, Just Works™
set -e

echo "=== Simple STIG RAG Deployment ==="

# Configuration
APP_NAME="stig-rag"
IMAGE_NAME="rhel-stig-rag:simple"
PORT="${PORT:-8000}"
DATA_DIR="${HOME}/stig-rag-data"
CACHE_DIR="${HOME}/stig-rag-cache"

# 1. Clean up everything
echo "Cleaning up..."
podman stop $(podman ps -aq) 2>/dev/null || true
podman rm -f $(podman ps -aq) 2>/dev/null || true
podman pod rm -f --all 2>/dev/null || true

# 2. Create directories
echo "Creating directories..."
mkdir -p "$DATA_DIR" "$CACHE_DIR"

# 3. Check for STIG data
if [ ! -f "stig_data.json" ]; then
    echo "ERROR: stig_data.json not found!"
    exit 1
fi
cp -f stig_data.json "$DATA_DIR/"

# 4. Create minimal app.py
echo "Creating minimal app.py..."
cat > app.py << 'EOF'
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import json
import os
from pathlib import Path

app = FastAPI(title="RHEL STIG RAG API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load STIG data
STIG_DATA = {}
data_file = Path(os.environ.get('DATA_DIR', '/app/data')) / "stig_data.json"
if data_file.exists():
    with open(data_file, 'r') as f:
        STIG_DATA = json.load(f)
    print(f"Loaded {len(STIG_DATA)} STIGs")

class QueryRequest(BaseModel):
    question: str
    rhel_version: Optional[str] = "9"
    top_k: Optional[int] = 5

@app.get("/")
async def root():
    return {"message": "STIG RAG API Running", "stigs": len(STIG_DATA)}

@app.get("/health")
async def health():
    return {"status": "healthy", "stigs": len(STIG_DATA)}

@app.post("/api/query")
async def query(request: QueryRequest):
    results = []
    query = request.question.lower()
    
    for stig_id, info in STIG_DATA.items():
        text = f"{stig_id} {info.get('title','')} {info.get('description','')}".lower()
        if query in text or any(word in text for word in query.split()):
            if request.rhel_version == "all" or info.get('rhel_version', '9') == request.rhel_version:
                results.append({
                    'stig_id': stig_id,
                    'title': info.get('title', ''),
                    'description': info.get('description', ''),
                    'severity': info.get('severity', 'medium'),
                    'check': info.get('check', ''),
                    'fix': info.get('fix', '')
                })
    
    return {
        "results": results[:request.top_k],
        "count": len(results)
    }
EOF

# 5. Create minimal Containerfile
echo "Creating Containerfile..."
cat > Containerfile.minimal << 'EOF'
FROM registry.access.redhat.com/ubi9/ubi-minimal:latest

RUN microdnf install -y python3 python3-pip && microdnf clean all

WORKDIR /app
RUN mkdir -p /app/data /app/cache

RUN python3.9 -m pip install fastapi uvicorn

COPY app.py .
COPY stig_data.json /app/data/

ENV DATA_DIR=/app/data
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python3.9", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

# 6. Build
echo "Building container..."
podman build -f Containerfile.minimal -t "$IMAGE_NAME" .

# 7. Run
echo "Starting container..."
podman run -d \
    --name "$APP_NAME" \
    -p "${PORT}:8000" \
    -v "$DATA_DIR:/app/data:ro,Z" \
    "$IMAGE_NAME"

# 8. Test
echo "Waiting for startup..."
sleep 5

if curl -s http://localhost:${PORT}/health | grep -q "healthy"; then
    echo "✓ SUCCESS! Application is running"
    echo ""
    echo "Test with:"
    echo "  curl http://localhost:${PORT}/health"
    echo "  curl -X POST http://localhost:${PORT}/api/query \\"
    echo "    -H 'Content-Type: application/json' \\"
    echo "    -d '{\"question\": \"selinux\"}'"
else
    echo "✗ Failed to start. Logs:"
    podman logs "$APP_NAME"
fi
