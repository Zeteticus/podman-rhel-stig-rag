#!/bin/bash

# Script to add RAG functionality with FAISS
set -e

echo "=== Adding RAG Functionality to STIG RAG ==="

# 1. Create full requirements.txt with ML dependencies
cat > requirements-full.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6
aiofiles==23.2.1
pydantic==2.4.2
sentence-transformers==2.2.2
faiss-cpu==1.7.4
numpy==1.24.3
torch==2.0.1
transformers==4.30.2
EOF

# 2. Create the full app.py with RAG
cat > app_with_rag.py << 'EOF'
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
import json
import os
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
import pickle
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RHEL STIG RAG API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    question: str
    rhel_version: Optional[str] = "9"
    top_k: Optional[int] = 5

class STIGSearchEngine:
    def __init__(self):
        self.model = None
        self.index = None
        self.stig_data = []
        self.embeddings = None
        self.load_data()
    
    def load_data(self):
        """Load STIG data and create/load embeddings"""
        data_dir = Path(os.environ.get('DATA_DIR', '/app/data'))
        cache_dir = Path(os.environ.get('CACHE_DIR', '/app/cache'))
        cache_dir.mkdir(exist_ok=True)
        
        # Check for cached embeddings
        cache_file = cache_dir / "stig_embeddings.pkl"
        
        if cache_file.exists():
            logger.info("Loading cached embeddings...")
            try:
                with open(cache_file, 'rb') as f:
                    cache_data = pickle.load(f)
                self.embeddings = cache_data['embeddings']
                self.stig_data = cache_data['processed_data']
                self.index = faiss.deserialize_index(cache_data['index'])
                logger.info(f"Loaded {len(self.stig_data)} STIGs from cache")
                return
            except Exception as e:
                logger.error(f"Failed to load cache: {e}")
        
        # Load fresh data
        data_file = data_dir / "stig_data.json"
        if not data_file.exists():
            logger.error("No STIG data file found!")
            return
        
        logger.info("Loading STIG data and creating embeddings...")
        with open(data_file, 'r') as f:
            raw_data = json.load(f)
        
        # Initialize model
        logger.info("Loading sentence transformer model...")
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Process data
        self.stig_data = []
        texts = []
        
        for stig_id, info in raw_data.items():
            search_text = f"{stig_id} {info.get('title', '')} {info.get('description', '')}"
            texts.append(search_text)
            
            self.stig_data.append({
                'stig_id': stig_id,
                'rhel_version': info.get('rhel_version', '9'),
                'severity': info.get('severity', 'medium'),
                'title': info.get('title', ''),
                'description': info.get('description', ''),
                'check': info.get('check', ''),
                'fix': info.get('fix', ''),
                'search_text': search_text
            })
        
        # Create embeddings
        logger.info("Creating embeddings...")
        self.embeddings = self.model.encode(texts)
        
        # Create FAISS index
        dimension = self.embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(self.embeddings.astype('float32'))
        
        # Save cache
        logger.info("Saving cache...")
        with open(cache_file, 'wb') as f:
            pickle.dump({
                'embeddings': self.embeddings,
                'processed_data': self.stig_data,
                'index': faiss.serialize_index(self.index)
            }, f)
        
        logger.info(f"Initialized with {len(self.stig_data)} STIGs")
    
    def search(self, query: str, rhel_version: str = "9", top_k: int = 5) -> List[Dict]:
        """Semantic search for STIGs"""
        if not self.model:
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Encode query
        query_embedding = self.model.encode([query])
        
        # Search
        D, I = self.index.search(query_embedding.astype('float32'), top_k * 2)
        
        # Filter results
        results = []
        for idx, distance in zip(I[0], D[0]):
            if idx < len(self.stig_data):
                entry = self.stig_data[idx]
                if rhel_version == "all" or entry['rhel_version'] == rhel_version:
                    results.append({
                        'stig_id': entry['stig_id'],
                        'title': entry['title'],
                        'description': entry['description'],
                        'severity': entry['severity'],
                        'check': entry['check'],
                        'fix': entry['fix'],
                        'relevance_score': float(1 / (1 + distance))
                    })
                    if len(results) >= top_k:
                        break
        
        return results

# Initialize search engine
search_engine = STIGSearchEngine()

@app.get("/")
async def read_index():
    """Serve the web interface"""
    static_file = Path("/app/static/index.html")
    if static_file.exists():
        return FileResponse(static_file)
    return {"message": "Web UI not found. API is running at /docs"}

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "stigs": len(search_engine.stig_data),
        "has_index": search_engine.index is not None
    }

@app.post("/api/query")
async def query(request: QueryRequest):
    """Semantic search for STIGs"""
    if not search_engine.index:
        raise HTTPException(status_code=503, detail="Search engine not initialized")
    
    results = search_engine.search(
        request.question,
        request.rhel_version,
        request.top_k
    )
    
    return {
        "question": request.question,
        "rhel_version": request.rhel_version,
        "results": results,
        "count": len(results)
    }

# Mount static files
if Path("/app/static").exists():
    app.mount("/static", StaticFiles(directory="/app/static"), name="static")
EOF

# 3. Create Containerfile with proper ML dependencies
cat > Containerfile.full << 'EOF'
FROM registry.access.redhat.com/ubi9/ubi:latest

# Install Python and system dependencies
RUN dnf install -y \
    python3 \
    python3-pip \
    python3-devel \
    gcc \
    gcc-c++ \
    make \
    && dnf clean all

WORKDIR /app

# Install Python dependencies in stages to avoid timeout
COPY requirements-full.txt .
RUN python3.9 -m pip install --upgrade pip setuptools wheel

# Install ML dependencies separately to handle large downloads
RUN python3.9 -m pip install --no-cache-dir torch==2.0.1 --index-url https://download.pytorch.org/whl/cpu
RUN python3.9 -m pip install --no-cache-dir transformers==4.30.2
RUN python3.9 -m pip install --no-cache-dir sentence-transformers==2.2.2
RUN python3.9 -m pip install --no-cache-dir faiss-cpu==1.7.4
RUN python3.9 -m pip install --no-cache-dir -r requirements-full.txt

# Create directories
RUN mkdir -p /app/data /app/cache /app/static

# Copy application files
COPY app_with_rag.py app.py
COPY static/ /app/static/
COPY stig_data.json /app/data/

# Pre-download the model
RUN python3.9 -c "from sentence_transformers import SentenceTransformer; model = SentenceTransformer('all-MiniLM-L6-v2'); print('Model downloaded')"

ENV DATA_DIR=/app/data
ENV CACHE_DIR=/app/cache
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python3.9", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

# 4. Build (this will take a while)
echo "Building container with full RAG functionality..."
echo "This will take 10-15 minutes due to ML dependencies..."
podman build -f Containerfile.full -t rhel-stig-rag:full .

# 5. Deploy
echo "Stopping old container..."
podman stop stig-rag 2>/dev/null || true
podman rm stig-rag 2>/dev/null || true

echo "Starting full RAG container..."
podman run -d \
    --name stig-rag \
    -p 8000:8000 \
    -v ~/stig-rag-data:/app/data:ro,Z \
    -v ~/stig-rag-cache:/app/cache:Z \
    rhel-stig-rag:full

echo "Waiting for initialization (this may take a minute)..."
sleep 10

# Check if it's working
if curl -s http://localhost:8000/health | grep -q "healthy"; then
    echo "✓ Full RAG system is running!"
    echo "✓ Web UI at http://localhost:8000"
    echo "✓ Semantic search is now enabled"
else
    echo "Checking logs..."
    podman logs stig-rag | tail -20
fi
