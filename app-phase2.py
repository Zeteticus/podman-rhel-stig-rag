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
