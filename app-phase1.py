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
