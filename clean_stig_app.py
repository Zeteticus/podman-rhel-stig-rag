#!/usr/bin/env python3
"""
Clean STIG RAG Application with View Full Details
"""
import uvicorn
from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, Dict, List, Any
import json
import os
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RHEL STIG RAG Assistant")
os.makedirs("templates", exist_ok=True)
os.makedirs("stig_data", exist_ok=True)

# [Include your XCCDF parser functions here - I'll add them after we confirm this works]

class STIGDataLoader:
    def __init__(self):
        self.data_loaded = False
        self.stig_data = {}
        self.search_index = {}
        logger.info("STIG Data Loader initialized")
    
    def load_stig_json(self, json_file_path: str) -> Dict[str, Any]:
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Simple parser for now - replace with your XCCDF parser
            if isinstance(data, dict):
                return data
            return {}
        except Exception as e:
            logger.error(f"Error loading STIG JSON: {e}")
            raise HTTPException(status_code=400, detail=f"Failed to load STIG data: {e}")
    
    def index_stig_data(self, stig_data):
        self.stig_data = stig_data
        self.search_index = {}
        
        for control_id, control_data in stig_data.items():
            searchable_text = self._create_searchable_text(control_id, control_data).lower()
            words = re.findall(r'\b\w+\b', searchable_text)
            for word in words:
                if word not in self.search_index:
                    self.search_index[word] = []
                if control_id not in self.search_index[word]:
                    self.search_index[word].append(control_id)
        
        self.data_loaded = True
        logger.info(f"Indexed {len(stig_data)} STIG controls")
    
    def _create_searchable_text(self, control_id, control_data):
        text_parts = [control_id]
        for field in ['title', 'description', 'check', 'fix']:
            if field in control_data and control_data[field]:
                text_parts.append(str(control_data[field]))
        return " ".join(text_parts)
    
    def search_controls(self, query: str, n_results: int = 5):
        if not self.data_loaded:
            return []
        
        query_lower = query.lower()
        query_words = re.findall(r'\b\w+\b', query_lower)
        control_scores = {}
        
        for word in query_words:
            if word in self.search_index:
                for control_id in self.search_index[word]:
                    control_scores[control_id] = control_scores.get(control_id, 0) + 2
        
        for control_id, control_data in self.stig_data.items():
            searchable_text = self._create_searchable_text(control_id, control_data).lower()
            if query_lower in searchable_text:
                control_scores[control_id] = control_scores.get(control_id, 0) + 3
        
        sorted_controls = sorted(control_scores.items(), key=lambda x: x[1], reverse=True)
        
        results = []
        for control_id, score in sorted_controls[:n_results]:
            results.append({
                'control_id': control_id,
                'control_data': self.stig_data.get(control_id, {}),
                'score': score
            })
        return results
    
    def get_control_by_id(self, control_id):
        return self.stig_data.get(control_id)
    
    def get_stats(self):
        if not self.data_loaded:
            return {"status": "no_data", "count": 0}
        return {
            "status": "loaded",
            "total_controls": len(self.stig_data),
            "search_method": "text_search"
        }

stig_loader = STIGDataLoader()

# Simple HTML template
html_template = '''
<!DOCTYPE html>
<html>
<head>
    <title>RHEL STIG RAG</title>
    <style>
        body { font-family: Arial; margin: 40px; background: #f5f5f5; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
        .form-section { background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }
        input, textarea, select { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
        button { background: #e53e3e; color: white; padding: 12px 24px; border: none; border-radius: 4px; cursor: pointer; }
        .result { background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 15px 0; border-left: 3px solid #e53e3e; }
        .details-link { display: block; margin-top: 15px; padding: 12px; background: #e3f2fd; border-radius: 5px; text-align: center; border: 2px solid #1976d2; }
        .details-link a { color: #1976d2; text-decoration: none; font-weight: bold; font-size: 16px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ RHEL STIG RAG Assistant</h1>
        
        <div class="form-section">
            <h3>📁 Upload STIG Data</h3>
            <form action="/upload-stig" method="post" enctype="multipart/form-data">
                <input type="file" name="stig_file" accept=".json" required>
                <button type="submit">🚀 Load STIG Data</button>
            </form>
        </div>
        
        <div class="form-section">
            <h3>🔍 Search STIG Controls</h3>
            <form action="/query" method="post">
                <textarea name="question" rows="3" placeholder="Enter your STIG question..." required></textarea>
                <input type="text" name="stig_id" placeholder="Specific STIG ID (optional)">
                <button type="submit">🔍 Search</button>
            </form>
        </div>
        
        <div id="status">Status: Loading...</div>
    </div>

    <script>
        fetch('/api/stats')
            .then(r => r.json())
            .then(data => {
                document.getElementById('status').innerHTML = 
                    data.status === 'loaded' ? 
                    `✅ ${data.total_controls} STIG controls loaded` : 
                    '⚠️ No STIG data loaded';
            });
    </script>
</body>
</html>
'''

@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(content=html_template)

@app.post("/upload-stig")
async def upload_stig_file(stig_file: UploadFile = File(...)):
    try:
        file_path = f"stig_data/{stig_file.filename}"
        with open(file_path, "wb") as f:
            content = await stig_file.read()
            f.write(content)
        
        stig_data = stig_loader.load_stig_json(file_path)
        stig_loader.index_stig_data(stig_data)
        stats = stig_loader.get_stats()
        
        return JSONResponse({
            "message": f"Successfully loaded {stats['total_controls']} STIG controls",
            "stats": stats,
            "status": "success"
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/query", response_class=HTMLResponse)
def query_form(question: str = Form(...), stig_id: Optional[str] = Form(None)):
    if not stig_loader.data_loaded:
        return HTMLResponse(content=html_template.replace('Status: Loading...', '⚠️ No STIG data loaded'))
    
    if stig_id:
        control_data = stig_loader.get_control_by_id(stig_id)
        if control_data:
            result_html = f"<h3>Found: {stig_id}</h3><p>{control_data.get('title', 'No title')}</p>"
        else:
            result_html = f"<h3>❌ Control {stig_id} not found</h3>"
    else:
        results = stig_loader.search_controls(question, n_results=3)
        if results:
            result_html = f"<h3>🔍 Found {len(results)} matching controls:</h3>"
            for i, result in enumerate(results, 1):
                control_id = result['control_id']
                control_data = result['control_data']
                title = control_data.get('title', 'No title')
                score = result['score']
                
                result_html += f'''
                <div class="result">
                    <h4>#{i} {control_id}: {title} (Score: {score})</h4>
                    <p>{control_data.get('description', 'No description')[:200]}...</p>
                    <div class="details-link">
                        <a href="/control/{control_id}">📋 View Full Details & Implementation Steps →</a>
                    </div>
                </div>
                '''
        else:
            result_html = "<h3>🔍 No matching controls found</h3>"
    
    return HTMLResponse(content=html_template.replace('Status: Loading...', result_html))

@app.get("/control/{stig_id}", response_class=HTMLResponse)
def view_control_details(stig_id: str):
    control_data = stig_loader.get_control_by_id(stig_id)
    
    if not control_data:
        return HTMLResponse(content=f'''
        <html><body style="font-family: Arial; margin: 50px;">
            <h1>❌ Control {stig_id} not found</h1>
            <a href="/">← Back to Search</a>
        </body></html>
        ''')
    
    title = control_data.get('title', 'No title')
    description = control_data.get('description', 'No description')
    check = control_data.get('check', 'No check procedure')
    fix = control_data.get('fix', 'No fix procedure')
    severity = control_data.get('severity', 'Unknown')
    
    return HTMLResponse(content=f'''
    <html>
    <head><title>{stig_id} - Full Details</title>
    <style>
        body {{ font-family: Arial; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }}
        .section {{ background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 8px; border-left: 5px solid #007bff; }}
        .back-link {{ display: inline-block; background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-bottom: 20px; }}
    </style>
    </head>
    <body>
        <div class="container">
            <a href="/" class="back-link">← Back to Search</a>
            
            <h1>🛡️ {stig_id}</h1>
            <h2>{title}</h2>
            <p><strong>Severity:</strong> {severity}</p>
            
            <div class="section">
                <h3>📋 Description</h3>
                <p>{description}</p>
            </div>
            
            <div class="section">
                <h3>🔍 Check Procedure</h3>
                <p>{check}</p>
            </div>
            
            <div class="section">
                <h3>🔧 Fix Implementation</h3>
                <p>{fix}</p>
            </div>
        </div>
    </body>
    </html>
    ''')

@app.get("/api/stats")
def get_stats():
    return stig_loader.get_stats()

@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "STIG RAG operational"}

if __name__ == "__main__":
    print("🚀 Starting Clean RHEL STIG RAG...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
