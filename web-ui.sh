#!/bin/bash

# Script to add web UI to the working STIG RAG container
set -e

echo "=== Adding Web Interface to STIG RAG ==="

# 1. Create static directory
mkdir -p static

# 2. Create the web interface HTML
cat > static/index.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RHEL STIG RAG Assistant</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            min-height: 100vh;
            color: #333;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            text-align: center;
            color: white;
            padding: 40px 0;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .main-card {
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            padding: 30px;
            margin-bottom: 20px;
        }
        
        .query-form {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        
        textarea {
            width: 100%;
            min-height: 100px;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 6px;
            font-size: 16px;
            resize: vertical;
        }
        
        .controls {
            display: flex;
            gap: 20px;
            align-items: center;
            flex-wrap: wrap;
        }
        
        select, button {
            padding: 10px 20px;
            border-radius: 6px;
            font-size: 16px;
        }
        
        button {
            background: #3498db;
            color: white;
            border: none;
            cursor: pointer;
            font-weight: 600;
        }
        
        button:hover {
            background: #2980b9;
        }
        
        .results {
            margin-top: 30px;
        }
        
        .result-item {
            background: #f8f9fa;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 15px;
        }
        
        .stig-id {
            display: inline-block;
            background: #3498db;
            color: white;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 10px;
        }
        
        .severity-high { background: #e74c3c; }
        .severity-medium { background: #f39c12; }
        .severity-low { background: #27ae60; }
        
        pre {
            background: #2c3e50;
            color: #ecf0f1;
            padding: 15px;
            border-radius: 6px;
            overflow-x: auto;
            margin: 10px 0;
        }
        
        .loading {
            display: none;
            text-align: center;
            padding: 40px;
        }
        
        .spinner {
            display: inline-block;
            width: 40px;
            height: 40px;
            border: 4px solid #f3f3f3;
            border-top: 4px solid #3498db;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🛡️ RHEL STIG RAG Assistant</h1>
            <p>Security Technical Implementation Guide Search</p>
        </div>
        
        <div class="main-card">
            <form class="query-form" id="queryForm">
                <div>
                    <label for="question">Ask a STIG Compliance Question:</label>
                    <textarea id="question" placeholder="Example: How do I configure SELinux for STIG compliance?" required></textarea>
                </div>
                
                <div class="controls">
                    <select id="rhel_version">
                        <option value="9">RHEL 9</option>
                        <option value="8">RHEL 8</option>
                        <option value="all">All Versions</option>
                    </select>
                    
                    <button type="submit">Search STIGs</button>
                </div>
            </form>
            
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <p>Searching STIG database...</p>
            </div>
            
            <div class="results" id="results"></div>
        </div>
    </div>
    
    <script>
        document.getElementById('queryForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const loading = document.getElementById('loading');
            const results = document.getElementById('results');
            
            loading.style.display = 'block';
            results.innerHTML = '';
            
            try {
                const response = await fetch('/api/query', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        question: document.getElementById('question').value,
                        rhel_version: document.getElementById('rhel_version').value,
                        top_k: 5
                    })
                });
                
                const data = await response.json();
                
                if (data.results && data.results.length > 0) {
                    results.innerHTML = '<h2>Found ' + data.count + ' STIGs</h2>';
                    
                    data.results.forEach(result => {
                        const severity = result.severity || 'medium';
                        results.innerHTML += `
                            <div class="result-item">
                                <span class="stig-id">${result.stig_id}</span>
                                <span class="stig-id severity-${severity}">${severity.toUpperCase()}</span>
                                <h3>${result.title}</h3>
                                <p>${result.description}</p>
                                ${result.check ? '<h4>How to Check:</h4><pre>' + result.check + '</pre>' : ''}
                                ${result.fix ? '<h4>How to Fix:</h4><pre>' + result.fix + '</pre>' : ''}
                            </div>
                        `;
                    });
                } else {
                    results.innerHTML = '<p>No matching STIGs found.</p>';
                }
            } catch (error) {
                results.innerHTML = '<p>Error: ' + error.message + '</p>';
            } finally {
                loading.style.display = 'none';
            }
        });
    </script>
</body>
</html>
EOF

# 3. Update app.py to serve the web interface
cat > app_with_ui.py << 'EOF'
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import json
import os
from pathlib import Path

app = FastAPI(title="RHEL STIG RAG API", version="1.1")

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
async def read_index():
    """Serve the web interface"""
    static_file = Path("/app/static/index.html")
    if static_file.exists():
        return FileResponse(static_file)
    return {"message": "Web UI not found. API is running at /docs"}

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

# Mount static files
if Path("/app/static").exists():
    app.mount("/static", StaticFiles(directory="/app/static"), name="static")
EOF

# 4. Create updated Containerfile
cat > Containerfile.with-ui << 'EOF'
FROM registry.access.redhat.com/ubi9/ubi-minimal:latest

RUN microdnf install -y python3 python3-pip && microdnf clean all

WORKDIR /app
RUN mkdir -p /app/data /app/cache /app/static

RUN python3.9 -m pip install fastapi uvicorn python-multipart aiofiles

COPY app_with_ui.py app.py
COPY static/ /app/static/
COPY stig_data.json /app/data/

ENV DATA_DIR=/app/data
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python3.9", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

# 5. Build and deploy
echo "Building container with web UI..."
podman build -f Containerfile.with-ui -t rhel-stig-rag:with-ui .

echo "Stopping old container..."
podman stop stig-rag 2>/dev/null || true
podman rm stig-rag 2>/dev/null || true

echo "Starting new container with web UI..."
podman run -d \
    --name stig-rag \
    -p 8000:8000 \
    -v ~/stig-rag-data:/app/data:ro,Z \
    rhel-stig-rag:with-ui

echo "Waiting for startup..."
sleep 5

echo "✓ Web UI should now be available at http://localhost:8000"
echo "✓ API docs at http://localhost:8000/docs"
