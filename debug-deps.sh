#!/bin/bash
# debug-dependencies.sh - Test dependencies incrementally to find the culprit

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo_status() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }
echo_info() { echo -e "${BLUE}[DEBUG]${NC} $1"; }

echo_status "🔍 Testing dependencies incrementally..."

# Test phases with increasing complexity
declare -a PHASES=(
    "phase1:Basic FastAPI"
    "phase2:Add data processing"
    "phase3:Add ChromaDB"
    "phase4:Full enhanced app"
)

for phase_info in "${PHASES[@]}"; do
    IFS=':' read -r phase_name phase_desc <<< "$phase_info"
    
    echo ""
    echo_status "🧪 Testing $phase_desc ($phase_name)..."
    
    # Create requirements for this phase
    case $phase_name in
        "phase1")
            cat > requirements-${phase_name}.txt << 'EOF'
fastapi==0.104.0
uvicorn==0.24.0
pydantic==2.4.2
jinja2==3.1.2
python-multipart==0.0.6
EOF
            ;;
        "phase2")
            cat > requirements-${phase_name}.txt << 'EOF'
fastapi==0.104.0
uvicorn==0.24.0
pydantic==2.4.2
jinja2==3.1.2
python-multipart==0.0.6
pandas==2.1.3
numpy==1.24.3
python-json-logger==2.0.7
EOF
            ;;
        "phase3")
            cat > requirements-${phase_name}.txt << 'EOF'
fastapi==0.104.0
uvicorn==0.24.0
pydantic==2.4.2
jinja2==3.1.2
python-multipart==0.0.6
pandas==2.1.3
numpy==1.24.3
python-json-logger==2.0.7
chromadb==0.4.15
EOF
            ;;
        "phase4")
            # Use the full requirements
            cp requirements.txt requirements-${phase_name}.txt
            ;;
    esac
    
    # Create test app for this phase
    case $phase_name in
        "phase1")
            cat > app-${phase_name}.py << 'EOF'
#!/usr/bin/env python3
import uvicorn
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, Dict, List
import json
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RHEL STIG RAG - Phase 1", description="Basic FastAPI test")

os.makedirs("templates", exist_ok=True)

with open("templates/index.html", "w") as f:
    f.write('<html><body><h1>Phase 1: Basic FastAPI Works!</h1><p>Upload and data processing not yet enabled.</p></body></html>')

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
def health():
    return {"status": "healthy", "phase": "1", "message": "Basic FastAPI operational"}

if __name__ == "__main__":
    logger.info("🚀 Starting Phase 1 - Basic FastAPI...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
EOF
            ;;
        "phase2")
            cat > app-${phase_name}.py << 'EOF'
#!/usr/bin/env python3
import uvicorn
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, Dict, List
import json
import os
import logging
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RHEL STIG RAG - Phase 2", description="With data processing libs")

os.makedirs("templates", exist_ok=True)

with open("templates/index.html", "w") as f:
    f.write('<html><body><h1>Phase 2: FastAPI + Data Processing!</h1><p>Pandas and NumPy loaded successfully. ChromaDB not yet enabled.</p></body></html>')

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
def health():
    # Test that pandas/numpy work
    test_df = pd.DataFrame({'test': [1, 2, 3]})
    test_array = np.array([1, 2, 3])
    return {
        "status": "healthy", 
        "phase": "2", 
        "message": "Data processing libraries operational",
        "pandas_version": pd.__version__,
        "numpy_version": np.__version__
    }

if __name__ == "__main__":
    logger.info("🚀 Starting Phase 2 - FastAPI + Data Processing...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
EOF
            ;;
        "phase3")
            cat > app-${phase_name}.py << 'EOF'
#!/usr/bin/env python3
import uvicorn
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, Dict, List
import json
import os
import logging
import pandas as pd
import numpy as np
import chromadb

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RHEL STIG RAG - Phase 3", description="With ChromaDB")

os.makedirs("templates", exist_ok=True)
os.makedirs("test_chroma_db", exist_ok=True)

with open("templates/index.html", "w") as f:
    f.write('<html><body><h1>Phase 3: FastAPI + ChromaDB!</h1><p>All dependencies loaded successfully.</p></body></html>')

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
def health():
    try:
        # Test ChromaDB initialization
        client = chromadb.PersistentClient(path="./test_chroma_db")
        collection = client.get_or_create_collection(name="test")
        
        # Test basic operation
        collection.add(
            documents=["test document"],
            metadatas=[{"source": "test"}],
            ids=["test1"]
        )
        
        # Test query
        results = collection.query(query_texts=["test"], n_results=1)
        
        return {
            "status": "healthy", 
            "phase": "3", 
            "message": "ChromaDB operational",
            "chromadb_version": chromadb.__version__,
            "test_query_results": len(results['ids'][0]) if results['ids'] else 0
        }
    except Exception as e:
        return {
            "status": "error",
            "phase": "3",
            "message": f"ChromaDB error: {str(e)}",
            "error_type": type(e).__name__
        }

if __name__ == "__main__":
    logger.info("🚀 Starting Phase 3 - FastAPI + ChromaDB...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
EOF
            ;;
        "phase4")
            # Use the enhanced app
            if [ -f "enhanced_app.py" ]; then
                cp enhanced_app.py app-${phase_name}.py
            else
                echo_error "enhanced_app.py not found for phase 4!"
                continue
            fi
            ;;
    esac
    
    # Create Containerfile for this phase
    cat > Containerfile.${phase_name} << EOF
FROM registry.access.redhat.com/ubi9/ubi:latest

WORKDIR /app

RUN dnf update -y && \\
    dnf install -y python3 python3-pip python3-devel gcc gcc-c++ sqlite && \\
    dnf clean all

RUN useradd -r -u 1001 -g 0 -m -d /app -s /bin/bash testuser && \\
    chown -R testuser:0 /app && \\
    chmod -R g=u /app

COPY --chown=testuser:0 requirements-${phase_name}.txt /app/requirements.txt
COPY --chown=testuser:0 app-${phase_name}.py /app/app.py

RUN python3 -m pip install --no-cache-dir --ignore-installed -r requirements.txt

RUN mkdir -p /app/templates /app/test_chroma_db && chown -R testuser:0 /app

USER testuser

ENV PYTHONUNBUFFERED=1 PORT=8000

EXPOSE 8000

CMD ["python3", "/app/app.py"]
EOF
    
    # Build and test this phase
    CONTAINER_NAME="stig-test-${phase_name}"
    IMAGE_NAME="localhost/rhel-stig-rag:${phase_name}"
    PORT=$((8000 + ${phase_name#phase}))
    
    echo_info "Building $phase_name container..."
    if podman build -t "$IMAGE_NAME" -f Containerfile.${phase_name} . 2>&1; then
        echo_status "✅ Build successful for $phase_name"
        
        # Stop previous test
        podman stop "$CONTAINER_NAME" 2>/dev/null || true
        podman rm "$CONTAINER_NAME" 2>/dev/null || true
        
        echo_info "Testing $phase_name runtime..."
        podman run -d --name "$CONTAINER_NAME" -p ${PORT}:8000 "$IMAGE_NAME"
        
        # Wait for startup
        for i in {1..20}; do
            if curl -s -f "http://localhost:${PORT}/health" >/dev/null 2>&1; then
                echo_status "✅ $phase_desc works! (Port $PORT)"
                
                # Show health status
                echo_info "Health check response:"
                curl -s "http://localhost:${PORT}/health" | python3 -m json.tool 2>/dev/null || curl -s "http://localhost:${PORT}/health"
                
                # Clean up this test
                podman stop "$CONTAINER_NAME" 2>/dev/null || true
                podman rm "$CONTAINER_NAME" 2>/dev/null || true
                break
            fi
            sleep 1
        done
        
        if [ $i -eq 20 ]; then
            echo_error "❌ $phase_desc failed at runtime!"
            echo_info "Container logs:"
            podman logs --tail 20 "$CONTAINER_NAME" 2>/dev/null || echo "No logs available"
            
            # Clean up failed test
            podman stop "$CONTAINER_NAME" 2>/dev/null || true
            podman rm "$CONTAINER_NAME" 2>/dev/null || true
            
            echo_error "🛑 Found the problem! $phase_desc is where it breaks."
            echo_info "Issue is likely with dependencies introduced in this phase."
            
            if [ "$phase_name" = "phase3" ]; then
                echo_warn "ChromaDB is the culprit! Try alternative vector databases or disable vector search."
            elif [ "$phase_name" = "phase2" ]; then
                echo_warn "Data processing libraries (pandas/numpy) are causing issues."
            fi
            
            break
        fi
    else
        echo_error "❌ Build failed for $phase_name!"
        echo_info "Build error is likely with dependencies in this phase."
        break
    fi
done

echo ""
echo_status "🎯 Debugging complete!"
echo_info "Check the output above to see where the failure occurred."
