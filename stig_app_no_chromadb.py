#!/usr/bin/env python3
"""
STIG Data Loader and RAG Application - Text Search Version
Fast, reliable STIG search without complex dependencies
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

app = FastAPI(title="RHEL STIG RAG Assistant", description="Text search STIG assistant")

os.makedirs("templates", exist_ok=True)
os.makedirs("stig_data", exist_ok=True)

class STIGDataLoader:
    def __init__(self):
        self.data_loaded = False
        self.stig_data = {}
        self.search_index = {}
        logger.info("STIG Data Loader initialized (text search mode)")
    
    def load_stig_json(self, json_file_path: str) -> Dict[str, Any]:
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Loaded STIG data from {json_file_path}")
            
            if isinstance(data, dict):
                if 'controls' in data:
                    return self._process_controls_format(data)
                elif 'stigs' in data:
                    return self._process_stigs_format(data)
                else:
                    return self._process_flat_format(data)
            elif isinstance(data, list):
                return self._process_list_format(data)
            return data
        except Exception as e:
            logger.error(f"Error loading STIG JSON: {e}")
            raise HTTPException(status_code=400, detail=f"Failed to load STIG data: {e}")
    
    def _process_controls_format(self, data):
        processed = {}
        for control in data.get('controls', []):
            control_id = control.get('id') or control.get('rule_id') or control.get('stig_id')
            if control_id:
                processed[control_id] = control
        return processed
    
    def _process_stigs_format(self, data):
        processed = {}
        for stig_name, stig_data in data.get('stigs', {}).items():
            if isinstance(stig_data, dict) and 'controls' in stig_data:
                for control in stig_data['controls']:
                    control_id = control.get('id') or control.get('rule_id')
                    if control_id:
                        control['stig_source'] = stig_name
                        processed[control_id] = control
        return processed
    
    def _process_flat_format(self, data):
        return data
    
    def _process_list_format(self, data):
        processed = {}
        for control in data:
            if isinstance(control, dict):
                control_id = control.get('id') or control.get('rule_id') or control.get('stig_id')
                if control_id:
                    processed[control_id] = control
        return processed
    
    def index_stig_data(self, stig_data):
        try:
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
        except Exception as e:
            logger.error(f"Error indexing: {e}")
            self.stig_data = stig_data
            self.data_loaded = True
    
    def _create_searchable_text(self, control_id, control_data):
        text_parts = [control_id]
        for field in ['title', 'description', 'check', 'fix', 'discussion', 'rationale']:
            if field in control_data and control_data[field]:
                text_parts.append(str(control_data[field]))
        if 'severity' in control_data:
            text_parts.append(f"Severity: {control_data['severity']}")
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
            
            for indexed_word in self.search_index:
                if word in indexed_word or indexed_word in word:
                    for control_id in self.search_index[indexed_word]:
                        control_scores[control_id] = control_scores.get(control_id, 0) + 1
        
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
                'score': score,
                'metadata': {'control_id': control_id}
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
            "search_method": "text_search",
            "indexed_words": len(self.search_index)
        }

stig_loader = STIGDataLoader()

# Create basic templates
with open("templates/index.html", "w") as f:
    f.write('''<!DOCTYPE html>
<html>
<head>
    <title>RHEL STIG RAG Assistant</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
        h1 { color: #e53e3e; text-align: center; }
        .form-section { background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }
        input, textarea, select { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
        button { background: #e53e3e; color: white; padding: 12px 24px; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #c53030; }
        .status { padding: 15px; border-radius: 8px; margin: 15px 0; }
        .loaded { background: #d4edda; border-left: 5px solid #28a745; }
        .no-data { background: #fff3cd; border-left: 5px solid #ffc107; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ RHEL STIG RAG Assistant</h1>
        <p style="text-align: center; color: #666;">Text Search Mode - Fast & Reliable</p>
        
        <div id="status" class="status">
            <div id="status-content">Loading...</div>
        </div>

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
                <select name="rhel_version">
                    <option value="9">RHEL 9</option>
                    <option value="8">RHEL 8</option>
                </select>
                <input type="text" name="stig_id" placeholder="Specific STIG ID (optional)">
                <button type="submit">🔍 Search</button>
            </form>
        </div>
    </div>

    <script>
        fetch('/api/stats')
            .then(r => r.json())
            .then(data => {
                const status = document.getElementById('status');
                const content = document.getElementById('status-content');
                if (data.status === 'loaded') {
                    status.className = 'status loaded';
                    content.innerHTML = `✅ ${data.total_controls} STIG controls loaded (${data.indexed_words} indexed words)`;
                } else {
                    status.className = 'status no-data';
                    content.innerHTML = '⚠️ No STIG data loaded. Upload a JSON file to begin.';
                }
            });
    </script>
</body>
</html>''')

with open("templates/result.html", "w") as f:
    f.write('''<!DOCTYPE html>
<html>
<head>
    <title>STIG Results</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
        h1 { color: #e53e3e; }
        .back-link { color: #007bff; text-decoration: none; padding: 10px 15px; background: #e3f2fd; border-radius: 20px; }
        .result { background: #e8f5e8; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 5px solid #28a745; }
        .query-info { background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0; }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-link">← Back</a>
        <h1>🛡️ STIG Results</h1>
        
        <div class="query-info">
            <strong>Question:</strong> {{ question }}<br>
            <strong>RHEL Version:</strong> {{ rhel_version }}<br>
            {% if stig_id %}<strong>STIG ID:</strong> {{ stig_id }}<br>{% endif %}
        </div>

        <div class="result">
            {{ answer|safe }}
        </div>
    </div>
</body>
</html>''')

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

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
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/stats")
def get_stats():
    return stig_loader.get_stats()

@app.post("/query", response_class=HTMLResponse)
async def query_form(
    request: Request,
    question: str = Form(...),
    rhel_version: str = Form("9"),
    stig_id: Optional[str] = Form(None)
):
    if not stig_loader.data_loaded:
        answer = "<div style='background: #fff3cd; padding: 15px; border-radius: 8px;'><h4>⚠️ No Data</h4><p>Please upload STIG JSON data first.</p></div>"
        return templates.TemplateResponse("result.html", {
            "request": request, "question": question, "rhel_version": rhel_version,
            "stig_id": stig_id, "answer": answer
        })
    
    if stig_id:
        control_data = stig_loader.get_control_by_id(stig_id)
        if control_data:
            title = control_data.get('title', 'No title')
            description = control_data.get('description', 'No description')
            check = control_data.get('check', 'No check procedure')
            fix = control_data.get('fix', 'No fix procedure')
            severity = control_data.get('severity', 'Unknown')
            
            answer = f"""
            <h4>🎯 {stig_id}: {title}</h4>
            <p><strong>Severity:</strong> {severity}</p>
            <div style="background: #f8f9fa; padding: 10px; margin: 10px 0; border-radius: 4px;">
                <h5>Description:</h5>
                <p>{description}</p>
            </div>
            <div style="background: #fff3cd; padding: 10px; margin: 10px 0; border-radius: 4px;">
                <h5>Check:</h5>
                <p>{check}</p>
            </div>
            <div style="background: #e1f5fe; padding: 10px; margin: 10px 0; border-radius: 4px;">
                <h5>Fix:</h5>
                <p>{fix}</p>
            </div>
            """
        else:
            answer = f"<div style='background: #f8d7da; padding: 15px; border-radius: 8px;'><h4>❌ Not Found</h4><p>STIG control {stig_id} not found.</p></div>"
    else:
        results = stig_loader.search_controls(question, n_results=3)
        if results:
            answer = f"<h4>🔍 Found {len(results)} matching controls:</h4>"
            for i, result in enumerate(results, 1):
                control_id = result['control_id']
                control_data = result['control_data']
                title = control_data.get('title', 'No title')
                score = result['score']
                answer += f"""
                <div style="background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 3px solid #e53e3e;">
                    <h5>#{i} {control_id}: {title} (Score: {score})</h5>
                    <p>{control_data.get('description', 'No description')[:200]}...</p>
                </div>
                """
        else:
            answer = "<div style='background: #fff3cd; padding: 15px; border-radius: 8px;'><h4>🔍 No Results</h4><p>No matching STIG controls found. Try different keywords.</p></div>"
    
    return templates.TemplateResponse("result.html", {
        "request": request, "question": question, "rhel_version": rhel_version,
        "stig_id": stig_id, "answer": answer
    })

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "message": "STIG RAG text search system operational",
        "data_loaded": stig_loader.data_loaded,
        "search_method": "text_search"
    }

if __name__ == "__main__":
    print("🚀 Starting RHEL STIG RAG (Text Search)...")
    print("🌐 http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
