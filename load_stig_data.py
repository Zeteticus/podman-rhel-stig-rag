# STIG Data Loading and Performance Optimization

## 1. Loading STIG JSON Data at Container Startup

### Step 1: Create a Data Loading Script

#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
import logging
from typing import Dict, List, Any
import pickle
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class STIGDataLoader:
    def __init__(self, json_path: str, cache_dir: str = "/app/cache"):
        self.json_path = json_path
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Initialize embedding model for semantic search
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.stig_data = {}
        self.embeddings = None
        self.index = None
        
    def load_json_data(self) -> Dict[str, Any]:
        """Load STIG data from JSON file"""
        try:
            with open(self.json_path, 'r') as f:
                data = json.load(f)
            logger.info(f"Loaded {len(data)} STIG entries from {self.json_path}")
            return data
        except Exception as e:
            logger.error(f"Failed to load JSON: {e}")
            sys.exit(1)
    
    def preprocess_stig_data(self, data: Dict[str, Any]) -> List[Dict]:
        """Preprocess STIG data for efficient searching"""
        processed_data = []
        
        for stig_id, stig_info in data.items():
            # Flatten and combine relevant fields for searching
            search_text = f"{stig_id} {stig_info.get('title', '')} {stig_info.get('description', '')} {stig_info.get('check', '')} {stig_info.get('fix', '')}"
            
            entry = {
                'stig_id': stig_id,
                'rhel_version': stig_info.get('rhel_version', '9'),
                'severity': stig_info.get('severity', 'medium'),
                'title': stig_info.get('title', ''),
                'description': stig_info.get('description', ''),
                'check': stig_info.get('check', ''),
                'fix': stig_info.get('fix', ''),
                'search_text': search_text
            }
            processed_data.append(entry)
            
        return processed_data
    
    def create_embeddings(self, processed_data: List[Dict]):
        """Create embeddings for semantic search"""
        texts = [entry['search_text'] for entry in processed_data]
        
        logger.info("Creating embeddings for STIG data...")
        embeddings = self.model.encode(texts, show_progress_bar=True)
        
        # Create FAISS index for fast similarity search
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings.astype('float32'))
        
        # Save to cache
        cache_file = self.cache_dir / "stig_embeddings.pkl"
        with open(cache_file, 'wb') as f:
            pickle.dump({
                'embeddings': embeddings,
                'processed_data': processed_data,
                'index': faiss.serialize_index(self.index)
            }, f)
        
        logger.info(f"Saved embeddings cache to {cache_file}")
        return embeddings
    
    def load_and_process(self):
        """Main loading function"""
        # Check for cache first
        cache_file = self.cache_dir / "stig_embeddings.pkl"
        if cache_file.exists():
            logger.info("Loading from cache...")
            with open(cache_file, 'rb') as f:
                cache_data = pickle.load(f)
                self.embeddings = cache_data['embeddings']
                self.stig_data = cache_data['processed_data']
                self.index = faiss.deserialize_index(cache_data['index'])
            return
        
        # Load fresh data
        raw_data = self.load_json_data()
        self.stig_data = self.preprocess_stig_data(raw_data)
        self.embeddings = self.create_embeddings(self.stig_data)
        
        logger.info("STIG data loading complete!")

if __name__ == "__main__":
    loader = STIGDataLoader("/app/data/stig_data.json")
    loader.load_and_process()
```

### Step 2: Modified Dockerfile

Create an enhanced `Dockerfile`:

```dockerfile
FROM registry.access.redhat.com/ubi9/ubi-minimal:latest

# Install Python and dependencies
RUN microdnf install -y python3 python3-pip && \
    microdnf clean all

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py load_stig_data.py ./
COPY stig_data.json /app/data/

# Create cache directory
RUN mkdir -p /app/cache

# Pre-load STIG data during build for faster startup
RUN python3 load_stig_data.py

# Copy startup script
COPY startup.sh .
RUN chmod +x startup.sh

EXPOSE 8000

# Use startup script
CMD ["./startup.sh"]
```

### Step 3: Startup Script

Create `startup.sh`:

```bash
#!/bin/bash

# Load/verify STIG data if not cached
if [ ! -f "/app/cache/stig_embeddings.pkl" ]; then
    echo "Loading STIG data..."
    python3 load_stig_data.py
fi

# Start the FastAPI application with optimizations
exec uvicorn app:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4 \
    --loop uvloop \
    --access-log \
    --use-colors
```

## 2. FastAPI Application with Optimizations

Create an optimized `app.py`:

```python
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import pickle
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from functools import lru_cache
import asyncio
from concurrent.futures import ThreadPoolExecutor
import redis
import json
import hashlib

app = FastAPI(title="RHEL STIG RAG API", version="2.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thread pool for CPU-bound operations
executor = ThreadPoolExecutor(max_workers=4)

# Initialize Redis for caching (optional but recommended)
try:
    redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
    redis_available = redis_client.ping()
except:
    redis_client = None
    redis_available = False

class QueryRequest(BaseModel):
    question: str
    rhel_version: Optional[str] = "9"
    stig_id: Optional[str] = None
    top_k: Optional[int] = 5

class STIGSearchEngine:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.load_data()
    
    def load_data(self):
        """Load preprocessed STIG data and embeddings"""
        with open('/app/cache/stig_embeddings.pkl', 'rb') as f:
            cache_data = pickle.load(f)
            self.embeddings = cache_data['embeddings']
            self.stig_data = cache_data['processed_data']
            self.index = faiss.deserialize_index(cache_data['index'])
    
    @lru_cache(maxsize=1000)
    def get_query_embedding(self, query: str) -> np.ndarray:
        """Cache query embeddings for repeated queries"""
        return self.model.encode([query])[0]
    
    def search(self, query: str, rhel_version: str = "9", top_k: int = 5) -> List[Dict]:
        """Perform semantic search on STIG data"""
        # Check Redis cache first
        cache_key = hashlib.md5(f"{query}:{rhel_version}:{top_k}".encode()).hexdigest()
        
        if redis_available:
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        
        # Get query embedding
        query_embedding = self.get_query_embedding(query)
        
        # Search in FAISS index
        D, I = self.index.search(query_embedding.reshape(1, -1).astype('float32'), top_k * 2)
        
        # Filter by RHEL version and prepare results
        results = []
        for idx in I[0]:
            if idx < len(self.stig_data):
                entry = self.stig_data[idx]
                if entry['rhel_version'] == rhel_version or rhel_version == "all":
                    results.append({
                        'stig_id': entry['stig_id'],
                        'title': entry['title'],
                        'description': entry['description'],
                        'severity': entry['severity'],
                        'check': entry['check'],
                        'fix': entry['fix'],
                        'relevance_score': float(1 / (1 + D[0][len(results)]))
                    })
                    if len(results) >= top_k:
                        break
        
        # Cache results
        if redis_available:
            redis_client.setex(cache_key, 3600, json.dumps(results))
        
        return results

# Initialize search engine
search_engine = STIGSearchEngine()

@app.on_event("startup")
async def startup_event():
    """Warm up the model and cache"""
    # Pre-compute embeddings for common queries
    common_queries = [
        "selinux configuration",
        "password policy",
        "firewall rules",
        "audit logging",
        "user permissions",
        "gpg signature",
        "secure boot"
    ]
    
    for query in common_queries:
        search_engine.get_query_embedding(query)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "redis": redis_available}

@app.post("/api/query")
async def query_stig(request: QueryRequest):
    """Query STIG information with semantic search"""
    try:
        # Run search in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            executor,
            search_engine.search,
            request.question,
            request.rhel_version,
            request.top_k
        )
        
        # If specific STIG ID requested, filter results
        if request.stig_id:
            results = [r for r in results if r['stig_id'] == request.stig_id]
        
        return {
            "question": request.question,
            "rhel_version": request.rhel_version,
            "results": results,
            "count": len(results)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stig/{stig_id}")
async def get_stig_by_id(stig_id: str):
    """Get specific STIG by ID"""
    for entry in search_engine.stig_data:
        if entry['stig_id'] == stig_id:
            return entry
    
    raise HTTPException(status_code=404, detail=f"STIG {stig_id} not found")

@app.get("/api/search/similar/{stig_id}")
async def find_similar_stigs(stig_id: str, top_k: int = 5):
    """Find similar STIGs to a given STIG ID"""
    # Find the STIG entry
    target_entry = None
    target_idx = None
    
    for idx, entry in enumerate(search_engine.stig_data):
        if entry['stig_id'] == stig_id:
            target_entry = entry
            target_idx = idx
            break
    
    if not target_entry:
        raise HTTPException(status_code=404, detail=f"STIG {stig_id} not found")
    
    # Use the embedding of the target STIG
    target_embedding = search_engine.embeddings[target_idx]
    
    # Search for similar
    D, I = search_engine.index.search(
        target_embedding.reshape(1, -1).astype('float32'), 
        top_k + 1
    )
    
    # Exclude the target itself
    results = []
    for i, idx in enumerate(I[0]):
        if idx != target_idx and idx < len(search_engine.stig_data):
            entry = search_engine.stig_data[idx]
            results.append({
                **entry,
                'similarity_score': float(1 / (1 + D[0][i]))
            })
    
    return results[:top_k]
```

## 3. Requirements File

Create `requirements.txt`:

```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
sentence-transformers==2.2.2
faiss-cpu==1.7.4
numpy==1.24.3
redis==5.0.1
pydantic==2.4.2
uvloop==0.19.0
httptools==0.6.1
python-multipart==0.0.6
```

## 4. Docker Compose with Redis Cache

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    container_name: stig-rag-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    
  stig-rag:
    build: .
    container_name: stig-rag-app
    ports:
      - "8000:8000"
    volumes:
      - ./stig_data.json:/app/data/stig_data.json:ro
      - stig_cache:/app/cache
    environment:
      - REDIS_HOST=redis
      - LOG_LEVEL=INFO
    depends_on:
      - redis
    restart: unless-stopped

volumes:
  redis_data:
  stig_cache:
```

## 5. Deployment Script

Create `deploy_optimized.sh`:

```bash
#!/bin/bash

# Build and deploy with optimizations
echo "Building optimized STIG RAG container..."

# Stop existing containers
podman stop stig-rag stig-rag-redis 2>/dev/null
podman rm stig-rag stig-rag-redis 2>/dev/null

# Create pod for networking
podman pod create --name stig-rag-pod -p 8000:8000 -p 6379:6379

# Run Redis
podman run -d \
  --pod stig-rag-pod \
  --name stig-rag-redis \
  -v redis_data:/data:Z \
  docker.io/redis:7-alpine \
  redis-server --appendonly yes

# Build application image
podman build -t rhel-stig-rag:optimized .

# Run application
podman run -d \
  --pod stig-rag-pod \
  --name stig-rag \
  -v ./stig_data.json:/app/data/stig_data.json:ro,Z \
  -v stig_cache:/app/cache:Z \
  -e REDIS_HOST=localhost \
  --restart unless-stopped \
  rhel-stig-rag:optimized

echo "Deployment complete! Access at http://localhost:8000"
echo "API docs at http://localhost:8000/docs"
```

## 6. Performance Optimization Tips

### a. JSON Data Structure
Ensure your `stig_data.json` follows this optimized structure:

```json
{
  "RHEL-09-211010": {
    "rhel_version": "9",
    "severity": "high",
    "title": "RHEL 9 must be configured to use the shadow file...",
    "description": "Detailed description of the STIG requirement...",
    "check": "Verify the system is configured correctly by running...",
    "fix": "Configure the system by executing the following commands...",
    "references": ["NIST SP 800-53 :: AC-2", "CCI-000015"],
    "tags": ["authentication", "shadow", "password"]
  }
}
```

### b. Additional Optimizations

1. **Batch Processing**: Process multiple queries in batches
2. **Compression**: Use compression for large JSON files
3. **Index Optimization**: Use IVF indexes for very large datasets
4. **Model Selection**: Consider using smaller, faster models for specific use cases

### c. Monitoring Performance

Add this endpoint to track performance:

```python
@app.get("/api/metrics")
async def get_metrics():
    return {
        "total_stigs": len(search_engine.stig_data),
        "cache_info": search_engine.get_query_embedding.cache_info()._asdict(),
        "redis_available": redis_available
    }
```

## Usage Examples

### Query with cURL:
```bash
# Basic query
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How to configure SELinux for STIG compliance?"}'

# Specific RHEL version
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "password policy requirements",
    "rhel_version": "9", "top_k": 10 }'

# Find similar STIGs
curl http://localhost:8000/api/search/similar/RHEL-09-211010
