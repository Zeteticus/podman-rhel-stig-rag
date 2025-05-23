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
