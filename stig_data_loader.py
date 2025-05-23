#!/usr/bin/env python3
"""
STIG Data Loader and Enhanced RAG Application
Integrates with your existing containerized setup
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
from pathlib import Path
import chromadb
from chromadb.config import Settings
import hashlib
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RHEL STIG RAG Assistant", description="AI-powered RHEL STIG compliance assistant with real data")

# Create necessary directories
os.makedirs("templates", exist_ok=True)
os.makedirs("stig_data", exist_ok=True)
os.makedirs("stig_chroma_db", exist_ok=True)

class STIGDataLoader:
    """Handles loading and indexing STIG data from JSON files"""
    
    def __init__(self, db_path: str = "./stig_chroma_db"):
        self.db_path = db_path
        self.client = None
        self.collection = None
        self.data_loaded = False
        self.stig_data = {}
        self._initialize_db()
    
    def _initialize_db(self):
        """Initialize ChromaDB for vector storage"""
        try:
            self.client = chromadb.PersistentClient(
                path=self.db_path,
                settings=Settings(allow_reset=True, anonymized_telemetry=False)
            )
            # Create or get collection
            self.collection = self.client.get_or_create_collection(
                name="stig_controls",
                metadata={"description": "DISA STIG controls and guidance"}
            )
            logger.info(f"ChromaDB initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self.client = None
    
    def load_stig_json(self, json_file_path: str) -> Dict[str, Any]:
        """Load STIG data from JSON file"""
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"Loaded STIG data from {json_file_path}")
            
            # Process different JSON structures
            if isinstance(data, dict):
                if 'controls' in data:
                    return self._process_controls_format(data)
                elif 'stigs' in data:
                    return self._process_stigs_format(data)
                else:
                    # Assume it's a flat structure of controls
                    return self._process_flat_format(data)
            elif isinstance(data, list):
                return self._process_list_format(data)
            
            return data
            
        except Exception as e:
            logger.error(f"Error loading STIG JSON: {e}")
            raise HTTPException(status_code=400, detail=f"Failed to load STIG data: {e}")
    
    def _process_controls_format(self, data: Dict) -> Dict:
        """Process JSON with 'controls' key structure"""
        processed = {}
        for control in data.get('controls', []):
            control_id = control.get('id') or control.get('rule_id') or control.get('stig_id')
            if control_id:
                processed[control_id] = control
        return processed
    
    def _process_stigs_format(self, data: Dict) -> Dict:
        """Process JSON with 'stigs' key structure"""
        processed = {}
        for stig_name, stig_data in data.get('stigs', {}).items():
            if isinstance(stig_data, dict) and 'controls' in stig_data:
                for control in stig_data['controls']:
                    control_id = control.get('id') or control.get('rule_id')
                    if control_id:
                        control['stig_source'] = stig_name
                        processed[control_id] = control
        return processed
    
    def _process_flat_format(self, data: Dict) -> Dict:
        """Process flat JSON structure where keys are control IDs"""
        return data
    
    def _process_list_format(self, data: List) -> Dict:
        """Process JSON list of controls"""
        processed = {}
        for control in data:
            if isinstance(control, dict):
                control_id = control.get('id') or control.get('rule_id') or control.get('stig_id')
                if control_id:
                    processed[control_id] = control
        return processed
    
    def index_stig_data(self, stig_data: Dict):
        """Index STIG data in ChromaDB for vector search"""
        if not self.client or not self.collection:
            logger.warning("ChromaDB not available, storing in memory only")
            self.stig_data = stig_data
            self.data_loaded = True
            return
        
        try:
            # Clear existing data
            self.collection.delete(where={})
            
            documents = []
            metadatas = []
            ids = []
            
            for control_id, control_data in stig_data.items():
                # Create searchable document text
                doc_text = self._create_searchable_text(control_id, control_data)
                documents.append(doc_text)
                
                # Create metadata
                metadata = self._extract_metadata(control_id, control_data)
                metadatas.append(metadata)
                
                # Use control ID as unique identifier
                ids.append(control_id)
            
            # Add to ChromaDB in batches
            batch_size = 100
            for i in range(0, len(documents), batch_size):
                batch_docs = documents[i:i+batch_size]
                batch_metadata = metadatas[i:i+batch_size]
                batch_ids = ids[i:i+batch_size]
                
                self.collection.add(
                    documents=batch_docs,
                    metadatas=batch_metadata,
                    ids=batch_ids
                )
            
            # Store in memory for quick access
            self.stig_data = stig_data
            self.data_loaded = True
            
            logger.info(f"Indexed {len(stig_data)} STIG controls in ChromaDB")
            
        except Exception as e:
            logger.error(f"Error indexing STIG data: {e}")
            # Fallback to memory storage
            self.stig_data = stig_data
            self.data_loaded = True
    
    def _create_searchable_text(self, control_id: str, control_data: Dict) -> str:
        """Create searchable text from control data"""
        text_parts = [control_id]
        
        # Add common fields
        for field in ['title', 'description', 'check', 'fix', 'discussion', 'rationale']:
            if field in control_data and control_data[field]:
                text_parts.append(str(control_data[field]))
        
        # Add severity/category
        if 'severity' in control_data:
            text_parts.append(f"Severity: {control_data['severity']}")
        
        if 'category' in control_data:
            text_parts.append(f"Category: {control_data['category']}")
        
        return " ".join(text_parts)
    
    def _extract_metadata(self, control_id: str, control_data: Dict) -> Dict:
        """Extract metadata for ChromaDB"""
        metadata = {"control_id": control_id}
        
        # Add string metadata (ChromaDB requirement)
        for field in ['title', 'severity', 'category', 'stig_source', 'rhel_version']:
            if field in control_data and control_data[field]:
                metadata[field] = str(control_data[field])[:500]  # Limit length
        
        return metadata
    
    def search_controls(self, query: str, n_results: int = 5) -> List[Dict]:
        """Search for relevant STIG controls"""
        if not self.data_loaded:
            return []
        
        if self.collection:
            try:
                results = self.collection.query(
                    query_texts=[query],
                    n_results=n_results,
                    include=['documents', 'metadatas', 'distances']
                )
                
                # Format results
                formatted_results = []
                for i, control_id in enumerate(results['ids'][0]):
                    formatted_results.append({
                        'control_id': control_id,
                        'control_data': self.stig_data.get(control_id, {}),
                        'distance': results['distances'][0][i],
                        'metadata': results['metadatas'][0][i]
                    })
                
                return formatted_results
            except Exception as e:
                logger.error(f"Vector search error: {e}")
        
        # Fallback to simple text search
        return self._simple_text_search(query, n_results)
    
    def _simple_text_search(self, query: str, n_results: int = 5) -> List[Dict]:
        """Simple text-based search fallback"""
        query_lower = query.lower()
        matches = []
        
        for control_id, control_data in self.stig_data.items():
            score = 0
            searchable_text = self._create_searchable_text(control_id, control_data).lower()
            
            # Simple scoring
            for term in query_lower.split():
                if term in searchable_text:
                    score += searchable_text.count(term)
            
            if score > 0:
                matches.append({
                    'control_id': control_id,
                    'control_data': control_data,
                    'score': score,
                    'metadata': self._extract_metadata(control_id, control_data)
                })
        
        # Sort by score and return top results
        matches.sort(key=lambda x: x['score'], reverse=True)
        return matches[:n_results]
    
    def get_control_by_id(self, control_id: str) -> Optional[Dict]:
        """Get specific control by ID"""
        return self.stig_data.get(control_id)
    
    def get_stats(self) -> Dict:
        """Get data statistics"""
        if not self.data_loaded:
            return {"status": "no_data", "count": 0}
        
        stats = {
            "status": "loaded",
            "total_controls": len(self.stig_data),
            "vector_db": self.collection is not None
        }
        
        # Count by severity
        severity_counts = {}
        rhel_version_counts = {}
        
        for control_data in self.stig_data.values():
            severity = control_data.get('severity', 'unknown')
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            rhel_version = control_data.get('rhel_version', 'unknown')
            rhel_version_counts[rhel_version] = rhel_version_counts.get(rhel_version, 0) + 1
        
        stats['severity_breakdown'] = severity_counts
        stats['rhel_version_breakdown'] = rhel_version_counts
        
        return stats

# Initialize data loader
stig_loader = STIGDataLoader()

# Update your existing templates (templates/index.html content)
with open("templates/index.html", "w") as f:
    f.write('''
<!DOCTYPE html>
<html>
<head>
    <title>RHEL STIG RAG Assistant</title>
    <style>
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            margin: 0; 
            padding: 40px; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container { 
            max-width: 1200px; 
            margin: 0 auto; 
            background: white; 
            padding: 40px; 
            border-radius: 15px; 
            box-shadow: 0 10px 30px rgba(0,0,0,0.2); 
        }
        h1 { 
            color: #e53e3e; 
            text-align: center; 
            margin-bottom: 10px;
            font-size: 2.5em;
        }
        .subtitle {
            text-align: center; 
            color: #666; 
            margin-bottom: 30px;
            font-size: 1.1em;
        }
        .data-status {
            background: linear-gradient(135deg, #e8f5e8 0%, #c8e6c9 100%);
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
            border-left: 5px solid #4caf50;
        }
        .no-data {
            background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
            border-left: 5px solid #ffc107;
        }
        .query-form { 
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); 
            padding: 30px; 
            border-radius: 12px; 
            margin: 30px 0; 
            border: 1px solid #dee2e6;
        }
        .form-group { margin: 20px 0; }
        label { 
            display: block; 
            margin-bottom: 8px; 
            font-weight: 600; 
            color: #495057;
        }
        input, select, textarea { 
            width: 100%; 
            padding: 12px; 
            border: 2px solid #dee2e6; 
            border-radius: 8px; 
            box-sizing: border-box;
            font-size: 14px;
            transition: border-color 0.3s ease;
        }
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #e53e3e;
        }
        button { 
            background: linear-gradient(135deg, #e53e3e 0%, #c53030 100%); 
            color: white; 
            padding: 12px 30px; 
            border: none; 
            border-radius: 8px; 
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            transition: transform 0.2s ease;
        }
        button:hover { 
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(229, 62, 62, 0.4);
        }
        .upload-section {
            background: linear-gradient(135deg, #f0f4f8 0%, #d6eaf8 100%);
            padding: 25px;
            border-radius: 12px;
            margin: 30px 0;
            border-left: 5px solid #3498db;
        }
        .examples { 
            background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%); 
            padding: 25px; 
            border-radius: 12px; 
            margin: 30px 0;
            border-left: 5px solid #ffc107;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 15px 0;
        }
        .stat-item {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }
        .stat-number {
            font-size: 24px;
            font-weight: bold;
            color: #e53e3e;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ RHEL STIG RAG Assistant</h1>
        <p class="subtitle">AI-powered Red Hat Enterprise Linux Security Technical Implementation Guide assistant</p>
        
        <div id="data-status" class="data-status">
            <h4>📊 Data Status: Loading...</h4>
            <div id="stats-content">Checking STIG data...</div>
        </div>

        <div class="upload-section">
            <h3>📁 Load STIG Data</h3>
            <p>Upload your STIG JSON file to enable full RAG functionality:</p>
            <form action="/upload-stig" method="post" enctype="multipart/form-data">
                <div class="form-group">
                    <label for="stig_file">Choose STIG JSON file:</label>
                    <input type="file" name="stig_file" id="stig_file" accept=".json" required>
                </div>
                <button type="submit">🚀 Load STIG Data</button>
            </form>
        </div>
        
        <div class="query-form">
            <h3>🔍 Ask a STIG Compliance Question</h3>
            <form action="/query" method="post">
                <div class="form-group">
                    <label for="question">🤔 Your Question:</label>
                    <textarea name="question" id="question" rows="4" placeholder="How do I configure GPG signature verification in RHEL 9? What are the SELinux requirements? How do I enable secure boot?" required></textarea>
                </div>
                <div class="form-group">
                    <label for="rhel_version">🐧 RHEL Version:</label>
                    <select name="rhel_version" id="rhel_version">
                        <option value="9" selected>RHEL 9 (Primary Focus)</option>
                        <option value="8">RHEL 8 (Legacy Support)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="stig_id">🎯 Specific STIG Control ID (optional):</label>
                    <input type="text" name="stig_id" id="stig_id" placeholder="e.g., RHEL-09-211010 or RHEL-08-010020">
                </div>
                <button type="submit">🚀 Get STIG Guidance</button>
            </form>
        </div>

        <div class="examples">
            <h3>💡 Example Questions to Try</h3>
            <ul>
                <li><strong>Package Security:</strong> "How do I verify GPG signatures for packages in RHEL 9?"</li>
                <li><strong>Access Control:</strong> "What are the SELinux requirements for RHEL compliance?"</li>
                <li><strong>Boot Security:</strong> "How do I configure secure boot and UEFI settings?"</li>
                <li><strong>Specific Controls:</strong> "How do I implement RHEL-09-211010?"</li>
            </ul>
        </div>
    </div>

    <script>
        // Load data status on page load
        fetch('/api/stats')
            .then(response => response.json())
            .then(data => {
                const statusDiv = document.getElementById('data-status');
                const statsContent = document.getElementById('stats-content');
                
                if (data.status === 'loaded') {
                    statusDiv.className = 'data-status';
                    statsContent.innerHTML = `
                        <div class="stats-grid">
                            <div class="stat-item">
                                <div class="stat-number">${data.total_controls}</div>
                                <div>Total Controls</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-number">${data.vector_db ? 'Yes' : 'No'}</div>
                                <div>Vector Search</div>
                            </div>
                        </div>
                        <p><strong>✅ STIG data loaded and ready for queries!</strong></p>
                    `;
                } else {
                    statusDiv.className = 'data-status no-data';
                    statsContent.innerHTML = '<p><strong>⚠️ No STIG data loaded. Please upload a JSON file to enable full functionality.</strong></p>';
                }
            })
            .catch(error => {
                console.error('Error loading stats:', error);
            });
    </script>
</body>
</html>
    ''')

# Enhanced API endpoints
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    templates = Jinja2Templates(directory="templates")
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload-stig")
async def upload_stig_file(stig_file: UploadFile = File(...)):
    """Upload and process STIG JSON file"""
    try:
        # Save uploaded file
        file_path = f"stig_data/{stig_file.filename}"
        with open(file_path, "wb") as f:
            content = await stig_file.read()
            f.write(content)
        
        # Load and index the data
        stig_data = stig_loader.load_stig_json(file_path)
        stig_loader.index_stig_data(stig_data)
        
        stats = stig_loader.get_stats()
        
        return JSONResponse({
            "message": f"Successfully loaded STIG data from {stig_file.filename}",
            "stats": stats,
            "status": "success"
        })
        
    except Exception as e:
        logger.error(f"Error uploading STIG file: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to process STIG file: {e}")

@app.get("/api/stats")
def get_stats():
    """Get current data statistics"""
    return stig_loader.get_stats()

@app.post("/query", response_class=HTMLResponse)
async def query_form(
    request: Request,
    question: str = Form(...),
    rhel_version: str = Form("9"),
    stig_id: Optional[str] = Form(None)
):
    """Process web form queries with real STIG data"""
    templates = Jinja2Templates(directory="templates")
    
    if not stig_loader.data_loaded:
        answer = """
        <div style="background: #fff3cd; padding: 20px; border-radius: 8px; border-left: 5px solid #ffc107;">
            <h4>⚠️ No STIG Data Loaded</h4>
            <p>Please upload a STIG JSON file using the upload form on the main page to enable full RAG functionality.</p>
            <p>Without STIG data, only basic demonstration responses are available.</p>
        </div>
        """
        return templates.TemplateResponse("result.html", {
            "request": request, "question": question, "rhel_version": rhel_version,
            "stig_id": stig_id, "answer": answer
        })
    
    # Search for relevant controls
    if stig_id:
        # Direct control lookup
        control_data = stig_loader.get_control_by_id(stig_id)
        if control_data:
            answer = format_control_response(stig_id, control_data, question, rhel_version)
        else:
            answer = f"""
            <div style="background: #f8d7da; padding: 20px; border-radius: 8px; border-left: 5px solid #dc3545;">
                <h4>❌ Control Not Found</h4>
                <p>STIG control <code>{stig_id}</code> was not found in the loaded data.</p>
                <p>Please verify the control ID or try a general search.</p>
            </div>
            """
    else:
        # Vector/semantic search
        search_results = stig_loader.search_controls(question, n_results=3)
        if search_results:
            answer = format_search_response(search_results, question, rhel_version)
        else:
            answer = """
            <div style="background: #fff3cd; padding: 20px; border-radius: 8px; border-left: 5px solid #ffc107;">
                <h4>🔍 No Matching Controls Found</h4>
                <p>No STIG controls were found matching your query. Try rephrasing your question or using different keywords.</p>
            </div>
            """
    
    return templates.TemplateResponse("result.html", {
        "request": request, "question": question, "rhel_version": rhel_version,
        "stig_id": stig_id, "answer": answer
    })

def format_control_response(control_id: str, control_data: Dict, question: str, rhel_version: str) -> str:
    """Format response for a specific control"""
    title = control_data.get('title', 'No title available')
    description = control_data.get('description', '')
    check = control_data.get('check', '')
    fix = control_data.get('fix', '')
    severity = control_data.get('severity', 'Unknown')
    
    return f"""
    <div style="background: #e8f5e8; padding: 25px; border-radius: 12px; border-left: 5px solid #4caf50;">
        <h4>🎯 STIG Control: {control_id}</h4>
        <h5>{title}</h5>
        
        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0;">
            <h6>📋 Description:</h6>
            <p>{description}</p>
        </div>
        
        <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin: 15px 0;">
            <h6>🔍 Check Procedure:</h6>
            <p>{check}</p>
        </div>
        
        <div style="background: #e1f5fe; padding: 15px; border-radius: 8px; margin: 15px 0;">
            <h6>🔧 Fix Implementation:</h6>
            <p>{fix}</p>
        </div>
        
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin: 15px 0;">
            <div style="background: #f8f9fa; padding: 10px; border-radius: 6px; text-align: center;">
                <strong>Severity:</strong><br><span style="color: #e53e3e;">{severity}</span>
            </div>
            <div style="background: #f8f9fa; padding: 10px; border-radius: 6px; text-align: center;">
                <strong>RHEL Version:</strong><br><span style="color: #e53e3e;">RHEL {rhel_version}</span>
            </div>
        </div>
    </div>
    """

def format_search_response(search_results: List[Dict], question: str, rhel_version: str) -> str:
    """Format response for search results"""
    response = f"""
    <div style="background: #e8f5e8; padding: 25px; border-radius: 12px; border-left: 5px solid #4caf50;">
        <h4>🔍 STIG Controls Found ({len(search_results)} matches)</h4>
        <p><strong>Your Question:</strong> {question}</p>
    </div>
    """
    
    for i, result in enumerate(search_results, 1):
        control_id = result['control_id']
        control_data = result['control_data']
        title = control_data.get('title', 'No title available')
        description = control_data.get('description', '')[:300] + '...' if len(control_data.get('description', '')) > 300 else control_data.get('description', '')
        severity = control_data.get('severity', 'Unknown')
        
        response += f"""
        <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 15px 0; border-left: 3px solid #e53e3e;">
            <h5>#{i} {control_id}: {title}</h5>
            <p><strong>Severity:</strong> <span style="color: #e53e3e;">{severity}</span></p>
            <p>{description}</p>
            <div style="margin-top: 10px;">
                <a href="/search/{control_id}" style="color: #3182ce; text-decoration: none; font-weight: bold;">View Full Details →</a>
            </div>
        </div>
        """
    
    return response

@app.get("/search/{stig_id}")
def search_stig(stig_id: str):
    """Get specific STIG control details"""
    control_data = stig_loader.get_control_by_id(stig_id)
    if control_data:
        return {
            "stig_id": stig_id,
            "control_data": control_data,
            "status": "found"
        }
    else:
        raise HTTPException(status_code=404, detail=f"STIG control {stig_id} not found")

@app.post("/api/query")
def api_query(request: Dict[str, Any]):
    """API endpoint for programmatic queries"""
    question = request.get('question', '')
    stig_id = request.get('stig_id')
    rhel_version = request.get('rhel_version', '9')
    
    if not stig_loader.data_loaded:
        return {"error": "No STIG data loaded", "status": "no_data"}
    
    if stig_id:
        control_data = stig_loader.get_control_by_id(stig_id)
        if control_data:
            return {
                "stig_id": stig_id,
                "control_data": control_data,
                "query": question,
                "status": "found"
            }
        else:
            return {"error": f"Control {stig_id} not found", "status": "not_found"}
    else:
        results = stig_loader.search_controls(question, n_results=5)
        return {
            "results": results,
            "query": question,
            "rhel_version": rhel_version,
            "status": "success"
        }

@app.get("/health")
def health_check():
    stats = stig_loader.get_stats()
    return {
        "status": "healthy",
        "message": "RHEL STIG RAG system operational",
        "data_loaded": stig_loader.data_loaded,
        "stats": stats
    }

if __name__ == "__main__":
    print("🚀 Starting Enhanced RHEL STIG RAG application with data loading...")
    print("🌐 Web Interface: http://localhost:8000")
    print("📚 API Documentation: http://localhost:8000/docs")
    print("📁 Upload STIG JSON files via the web interface")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")