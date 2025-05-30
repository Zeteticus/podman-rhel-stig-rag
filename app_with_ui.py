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
