#!/usr/bin/env python3
"""
Enhanced STIG RAG with Llama 3.2 Integration
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
import requests
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RHEL STIG RAG Assistant with Llama 3.2")
os.makedirs("templates", exist_ok=True)
os.makedirs("stig_data", exist_ok=True)

# Ollama configuration
OLLAMA_BASE_URL = "http://localhost:11434"
LLAMA_MODEL = "llama3.2:3b"  # Change to :1b if you prefer smaller/faster

class OllamaClient:
    """Client for interacting with Ollama/Llama 3.2"""
    
    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = LLAMA_MODEL):
        self.base_url = base_url
        self.model = model
    
    def is_available(self) -> bool:
        """Check if Ollama is running"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def generate_response(self, prompt: str, context: str = "") -> str:
        """Generate response using Llama 3.2"""
        try:
            full_prompt = f"""You are a RHEL STIG compliance expert. Answer the user's question using the provided STIG control information.

STIG Controls Context:
{context}

User Question: {prompt}

Instructions:
- Focus on practical implementation steps
- Reference specific STIG control IDs when relevant
- Provide clear, actionable guidance
- If the context doesn't contain relevant information, say so clearly
- Be concise but thorough

Answer:"""

            payload = {
                "model": self.model,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Low temperature for consistent technical responses
                    "top_p": 0.9,
                    "num_predict": 500   # Limit response length
                }
            }
            
            response = requests.post(
                f"{self.base_url}/api/generate", 
                json=payload, 
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', 'No response generated')
            else:
                return f"Error: Ollama returned status {response.status_code}"
                
        except requests.exceptions.Timeout:
            return "Error: Request timed out. Llama model may be too slow."
        except Exception as e:
            return f"Error: {str(e)}"

# Initialize Ollama client
ollama_client = OllamaClient()

# [Include your existing XCCDF parser functions here]
def parse_xccdf_json(data):
    """Parse XCCDF-converted JSON structure"""
    processed_controls = {}
    
    if isinstance(data, list):
        for rhel_data in data:
            if isinstance(rhel_data, dict) and 'data' in rhel_data:
                rhel_version = rhel_data.get('rhel_version', 'unknown')
                benchmark_data = rhel_data['data'].get('Benchmark', {})
                version_controls = extract_controls_from_benchmark(benchmark_data, rhel_version)
                processed_controls.update(version_controls)
    
    elif isinstance(data, dict):
        if 'Benchmark' in data:
            version_controls = extract_controls_from_benchmark(data['Benchmark'], 'unknown')
            processed_controls.update(version_controls)
    
    return processed_controls

def extract_controls_from_benchmark(benchmark, rhel_version):
    """Extract STIG controls from Benchmark structure"""
    controls = {}
    
    groups = []
    if 'Group' in benchmark:
        group_data = benchmark['Group']
        if isinstance(group_data, list):
            groups = group_data
        elif isinstance(group_data, dict):
            groups = [group_data]
    
    rules = []
    for group in groups:
        if isinstance(group, dict) and 'Rule' in group:
            group_rules = group['Rule']
            if isinstance(group_rules, list):
                rules.extend(group_rules)
            elif isinstance(group_rules, dict):
                rules.append(group_rules)
    
    for rule in rules:
        if isinstance(rule, dict):
            control = extract_control_from_rule(rule, rhel_version)
            if control and 'id' in control:
                controls[control['id']] = control
    
    return controls

def extract_control_from_rule(rule, rhel_version):
    """Extract control information from a Rule element"""
    control = {}
    
    rule_id = rule.get('@id', '')
    if rule_id:
        control['id'] = rule_id
    
    title = rule.get('title', '')
    if isinstance(title, dict):
        title = title.get('#text', str(title))
    control['title'] = str(title)
    
    description = rule.get('description', '')
    if isinstance(description, dict):
        description = description.get('#text', str(description))
    control['description'] = str(description)
    
    severity = rule.get('@severity', 'medium')
    control['severity'] = severity
    
    check_content = ''
    if 'check' in rule:
        check = rule['check']
        if isinstance(check, dict) and 'check-content' in check:
            check_content = check['check-content']
            if isinstance(check_content, dict):
                check_content = check_content.get('#text', str(check_content))
    control['check'] = str(check_content).strip()
    
    fix_content = ''
    if 'fixtext' in rule:
        fixtext = rule['fixtext']
        if isinstance(fixtext, dict):
            fix_content = fixtext.get('#text', str(fixtext))
    control['fix'] = str(fix_content).strip()
    
    control['rhel_version'] = rhel_version
    return control

# Enhanced STIG Data Loader with Llama integration
class EnhancedSTIGDataLoader:
    def __init__(self):
        self.data_loaded = False
        self.stig_data = {}
        self.search_index = {}
        logger.info("Enhanced STIG Data Loader with Llama 3.2 initialized")
    
    def load_stig_json(self, json_file_path: str) -> Dict[str, Any]:
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"Loaded STIG data from {json_file_path}")
            
            # Try XCCDF format first
            try:
                xccdf_controls = parse_xccdf_json(data)
                if xccdf_controls:
                    logger.info(f"Successfully parsed XCCDF format with {len(xccdf_controls)} controls")
                    return xccdf_controls
            except Exception as e:
                logger.warning(f"XCCDF parsing failed: {e}")
            
            # Fallback
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
        """Enhanced search with better relevance scoring"""
        if not self.data_loaded:
            return []
        
        query_lower = query.lower()
        query_words = re.findall(r'\b\w+\b', query_lower)
        control_scores = {}
        
        # Score controls based on word matches
        for word in query_words:
            if word in self.search_index:
                for control_id in self.search_index[word]:
                    control_scores[control_id] = control_scores.get(control_id, 0) + 2
        
        # Boost scores for phrase matches and title matches
        for control_id, control_data in self.stig_data.items():
            searchable_text = self._create_searchable_text(control_id, control_data).lower()
            title = control_data.get('title', '').lower()
            
            # Phrase match boost
            if query_lower in searchable_text:
                control_scores[control_id] = control_scores.get(control_id, 0) + 5
            
            # Title match boost (higher relevance)
            if any(word in title for word in query_words):
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
    
    def get_enhanced_response(self, query: str, search_results: List[Dict]) -> str:
        """Generate enhanced response using Llama 3.2"""
        if not ollama_client.is_available():
            return self._fallback_response(query, search_results)
        
        # Create context from search results
        context_parts = []
        for result in search_results:
            control_id = result['control_id']
            control_data = result['control_data']
            
            context_parts.append(f"""
Control ID: {control_id}
Title: {control_data.get('title', 'No title')}
Description: {control_data.get('description', 'No description')}
Check: {control_data.get('check', 'No check procedure')}
Fix: {control_data.get('fix', 'No fix procedure')}
Severity: {control_data.get('severity', 'Unknown')}
RHEL Version: {control_data.get('rhel_version', 'Unknown')}
""")
        
        context = "\n".join(context_parts)
        
        # Generate response using Llama 3.2
        response = ollama_client.generate_response(query, context)
        return response
    
    def _fallback_response(self, query: str, search_results: List[Dict]) -> str:
        """Fallback response when Llama is not available"""
        if not search_results:
            return "No relevant STIG controls found for your query."
        
        response = f"Found {len(search_results)} relevant STIG controls:\n\n"
        for i, result in enumerate(search_results, 1):
            control_id = result['control_id']
            control_data = result['control_data']
            title = control_data.get('title', 'No title')
            response += f"{i}. **{control_id}**: {title}\n"
        
        response += "\nNote: Llama 3.2 is not available. Click 'View Full Details' for complete implementation guidance."
        return response
    
    def get_control_by_id(self, control_id):
        return self.stig_data.get(control_id)
    
    def get_stats(self):
        if not self.data_loaded:
            return {"status": "no_data", "count": 0}
        return {
            "status": "loaded",
            "total_controls": len(self.stig_data),
            "search_method": "enhanced_text_search_with_llama3.2",
            "llama_available": ollama_client.is_available()
        }

stig_loader = EnhancedSTIGDataLoader()

# Create enhanced templates with Llama integration
with open("templates/index.html", "w") as f:
    f.write('''<!DOCTYPE html>
<html>
<head>
    <title>RHEL STIG RAG with Llama 3.2</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
        h1 { color: #e53e3e; text-align: center; }
        .llama-status { padding: 15px; border-radius: 8px; margin: 20px 0; text-align: center; }
        .llama-online { background: #d4edda; border-left: 5px solid #28a745; }
        .llama-offline { background: #f8d7da; border-left: 5px solid #dc3545; }
        .form-section { background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }
        input, textarea, select { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
        button { background: #e53e3e; color: white; padding: 12px 24px; border: none; border-radius: 4px; cursor: pointer; }
        .status { padding: 15px; border-radius: 8px; margin: 15px 0; }
        .loaded { background: #d4edda; border-left: 5px solid #28a745; }
        .no-data { background: #fff3cd; border-left: 5px solid #ffc107; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ RHEL STIG RAG Assistant</h1>
        <h2 style="text-align: center; color: #666;">Powered by Llama 3.2 🦙</h2>
        
        <div id="llama-status" class="llama-status">
            <div id="llama-content">Checking Llama 3.2 status...</div>
        </div>
        
        <div id="status" class="status">
            <div id="status-content">Loading STIG data...</div>
        </div>

        <div class="form-section">
            <h3>📁 Upload STIG Data</h3>
            <form action="/upload-stig" method="post" enctype="multipart/form-data">
                <input type="file" name="stig_file" accept=".json" required>
                <button type="submit">🚀 Load STIG Data</button>
            </form>
        </div>
        
        <div class="form-section">
            <h3>🔍 Ask STIG Questions (AI-Powered)</h3>
            <form action="/query" method="post">
                <textarea name="question" rows="3" placeholder="Ask in natural language: How do I configure SSH security? What are the firewall requirements? How do I enable SELinux?" required></textarea>
                <input type="text" name="stig_id" placeholder="Specific STIG ID (optional)">
                <button type="submit">🤖 Get AI-Powered Answer</button>
            </form>
        </div>
        
        <div style="background: #e8f4f8; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <h4>🦙 Llama 3.2 Features:</h4>
            <ul>
                <li><strong>Intelligent Responses:</strong> Understands your questions semantically</li>
                <li><strong>Contextual Analysis:</strong> Provides relevant STIG guidance</li>
                <li><strong>Implementation Focus:</strong> Gives practical, actionable steps</li>
                <li><strong>Private & Secure:</strong> Runs locally on your machine</li>
            </ul>
        </div>
    </div>

    <script>
        // Check Llama status
        fetch('/api/stats')
            .then(r => r.json())
            .then(data => {
                const llamaStatus = document.getElementById('llama-status');
                const llamaContent = document.getElementById('llama-content');
                const status = document.getElementById('status');
                const statusContent = document.getElementById('status-content');
                
                if (data.llama_available) {
                    llamaStatus.className = 'llama-status llama-online';
                    llamaContent.innerHTML = '🦙 Llama 3.2 is online and ready for intelligent responses!';
                } else {
                    llamaStatus.className = 'llama-status llama-offline';
                    llamaContent.innerHTML = '⚠️ Llama 3.2 is offline. Install: <code>ollama pull llama3.2:3b</code>';
                }
                
                if (data.status === 'loaded') {
                    status.className = 'status loaded';
                    statusContent.innerHTML = `✅ ${data.total_controls} STIG controls loaded`;
                } else {
                    status.className = 'status no-data';
                    statusContent.innerHTML = '⚠️ No STIG data loaded. Upload JSON file above.';
                }
            })
            .catch(console.error);
    </script>
</body>
</html>''')

with open("templates/result.html", "w") as f:
    f.write('''<!DOCTYPE html>
<html>
<head>
    <title>STIG AI Response</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
        h1 { color: #e53e3e; }
        .back-link { color: #007bff; text-decoration: none; padding: 10px 15px; background: #e3f2fd; border-radius: 20px; }
        .result { background: #e8f5e8; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 5px solid #28a745; }
        .query-info { background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0; }
        .ai-badge { background: #e3f2fd; color: #1976d2; padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-link">← Back</a>
        <h1>🛡️ STIG AI Response <span class="ai-badge">🦙 Llama 3.2</span></h1>
        
        <div class="query-info">
            <strong>Question:</strong> {{ question }}<br>
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
def home(request: Request):
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
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/query", response_class=HTMLResponse)
def query_form(
    request: Request,
    question: str = Form(...),
    stig_id: Optional[str] = Form(None)
):
    if not stig_loader.data_loaded:
        answer = "<div style='background: #fff3cd; padding: 15px; border-radius: 8px;'><h4>⚠️ No Data</h4><p>Please upload STIG JSON data first.</p></div>"
        return templates.TemplateResponse("result.html", {
            "request": request, "question": question, "stig_id": stig_id, "answer": answer
        })
    
    if stig_id:
        # Direct control lookup
        control_data = stig_loader.get_control_by_id(stig_id)
        if control_data:
            answer = format_control_response(control_id=stig_id, control_data=control_data)
        else:
            answer = f"<div style='background: #f8d7da; padding: 15px; border-radius: 8px;'><h4>❌ Not Found</h4><p>STIG control {stig_id} not found.</p></div>"
    else:
        # Enhanced AI-powered search
        search_results = stig_loader.search_controls(question, n_results=5)
        if search_results:
            # Get AI-enhanced response
            ai_response = stig_loader.get_enhanced_response(question, search_results)
            answer = format_ai_response(question, ai_response, search_results)
        else:
            answer = "<div style='background: #fff3cd; padding: 15px; border-radius: 8px;'><h4>🔍 No Results</h4><p>No matching STIG controls found. Try different keywords.</p></div>"
    
    return templates.TemplateResponse("result.html", {
        "request": request, "question": question, "stig_id": stig_id, "answer": answer
    })

def format_ai_response(question: str, ai_response: str, search_results: List[Dict]) -> str:
    """Format AI response with related controls"""
    
    answer = f"""
    <div style="background: #e3f2fd; padding: 20px; border-radius: 8px; margin: 15px 0; border-left: 5px solid #1976d2;">
        <h4>🤖 AI Analysis</h4>
        <div style="white-space: pre-wrap; line-height: 1.6;">{ai_response}</div>
    </div>
    
    <h4>📋 Related STIG Controls:</h4>
    """
    
    for i, result in enumerate(search_results, 1):
        control_id = result['control_id']
        control_data = result['control_data']
        title = control_data.get('title', 'No title')
        score = result.get('score', 0)
        
        answer += f"""
        <div style="background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 3px solid #e53e3e;">
            <h5>#{i} {control_id}: {title} (Relevance: {score})</h5>
            <p>{control_data.get('description', 'No description')[:200]}...</p>
            <div style="margin-top: 15px; padding: 12px; background: #e3f2fd; border-radius: 5px; text-align: center; border: 2px solid #1976d2;">
                <a href="/control/{control_id}" style="color: #1976d2; text-decoration: none; font-weight: bold; font-size: 16px;">
                    📋 View Full Details & Implementation Steps →
                </a>
            </div>
        </div>
        """
    
    return answer

def format_control_response(control_id: str, control_data: Dict) -> str:
    """Format response for a specific control"""
    title = control_data.get('title', 'No title')
    description = control_data.get('description', 'No description')
    check = control_data.get('check', 'No check procedure')
    fix = control_data.get('fix', 'No fix procedure')
    severity = control_data.get('severity', 'Unknown')
    
    return f"""
    <h4>🎯 {control_id}: {title}</h4>
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

@app.get("/control/{stig_id}", response_class=HTMLResponse)
def view_control_details(request: Request, stig_id: str):
    control_data = stig_loader.get_control_by_id(stig_id)
    
    if not control_data:
        return HTMLResponse(content=f'<h1>Control {stig_id} not found</h1><a href="/">Back</a>')
    
    # Get AI explanation of this control
    ai_explanation = ""
    if ollama_client.is_available():
        context = f"""
Control ID: {stig_id}
Title: {control_data.get('title', '')}
Description: {control_data.get('description', '')}
Check: {control_data.get('check', '')}
Fix: {control_data.get('fix', '')}
"""
        ai_explanation = ollama_client.generate_response(
            f"Explain this STIG control and provide implementation guidance for {stig_id}",
            context
        )
    
    title = control_data.get('title', 'No title')
    description = control_data.get('description', 'No description')
    check = control_data.get('check', 'No check procedure')
    fix = control_data.get('fix', 'No fix procedure')
    severity = control_data.get('severity', 'Unknown')
    rhel_version = control_data.get('rhel_version', 'Unknown')
    
    return HTMLResponse(content=f'''
    <!DOCTYPE html>
    <html>
    <head><title>{stig_id} - AI Analysis</title>
    <style>
        body {{ font-family: Arial; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }}
        .section {{ background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 8px; border-left: 5px solid #007bff; }}
        .ai-section {{ background: #e3f2fd; padding: 20px; margin: 20px 0; border-radius: 8px; border-left: 5px solid #1976d2; }}
        .back-link {{ display: inline-block; background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-bottom: 20px; }}
    </style>
    </head>
    <body>
        <div class="container">
            <a href="/" class="back-link">← Back to Search</a>
            
            <h1>🛡️ {stig_id}</h1>
            <h2>{title}</h2>
            <p><strong>Severity:</strong> {severity} | <strong>RHEL Version:</strong> {rhel_version}</p>
            
            {f'<div class="ai-section"><h3>🤖 AI Analysis & Guidance</h3><div style="white-space: pre-wrap; line-height: 1.6;">{ai_explanation}</div></div>' if ai_explanation else ''}
            
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
    return {
        "status": "healthy",
        "message": "STIG RAG with Llama 3.2 operational",
        "llama_available": ollama_client.is_available()
    }

if __name__ == "__main__":
    print("🚀 Starting RHEL STIG RAG with Llama 3.2...")
    print("🦙 Make sure Ollama is running: ollama serve")
    print("🌐 Web Interface: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
