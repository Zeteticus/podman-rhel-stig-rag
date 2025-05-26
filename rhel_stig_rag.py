#!/usr/bin/env python3
"""
Enhanced STIG RAG with Llama 3.2 Integration - Container Network Fixed
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

# Fixed Ollama configuration for container networking (Podman compatible)
# For Podman, use host.containers.internal or actual host IP
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.containers.internal:11434")
LLAMA_MODEL = os.getenv("LLAMA_MODEL", "llama3.2:3b")

class OllamaClient:
    """Client for interacting with Ollama/Llama 3.2"""

    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = LLAMA_MODEL):
        self.base_url = base_url
        self.model = model
        logger.info(f"Initializing Ollama client with URL: {self.base_url}")

    def is_available(self) -> bool:
        """Check if Ollama is running"""
        try:
            logger.info(f"Checking Ollama availability at: {self.base_url}")
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            is_available = response.status_code == 200
            logger.info(f"Ollama availability check: {is_available} (status: {response.status_code})")
            
            # Also check if our specific model is available
            if is_available:
                try:
                    models = response.json().get('models', [])
                    model_available = any(self.model in model.get('name', '') for model in models)
                    logger.info(f"Model {self.model} available: {model_available}")
                    return model_available
                except:
                    logger.warning("Could not parse models list, assuming model is available")
                    return True
            return False
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error to Ollama: {e}")
            return False
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout connecting to Ollama: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error checking Ollama: {e}")
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

            logger.info(f"Sending request to Ollama at: {self.base_url}/api/generate")
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return result.get('response', 'No response generated')
            else:
                error_msg = f"Error: Ollama returned status {response.status_code}"
                logger.error(error_msg)
                return error_msg

        except requests.exceptions.ConnectionError as e:
            error_msg = "Error: Cannot connect to Ollama. Check if Ollama is running and accessible."
            logger.error(f"{error_msg} Details: {e}")
            return error_msg
        except requests.exceptions.Timeout:
            error_msg = "Error: Request timed out. Llama model may be too slow or overloaded."
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error(error_msg)
            return error_msg

# Rest of your existing code remains the same...
# [Include all your existing parse_xccdf_json, extract_controls_from_benchmark, etc. functions]

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

# Enhanced STIG Data Loader with better error handling
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
            logger.warning("Ollama not available, using fallback response")
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
        
        # Check Ollama availability and log the result
        llama_available = ollama_client.is_available()
        logger.info(f"Stats check - Llama available: {llama_available}")
        
        # Determine how data was loaded
        auto_load_path = os.getenv("AUTO_LOAD_STIG_PATH")
        data_source = "auto-loaded" if auto_load_path and os.path.exists(auto_load_path) else "uploaded"
        
        return {
            "status": "loaded",
            "total_controls": len(self.stig_data),
            "search_method": "enhanced_text_search_with_llama3.2",
            "llama_available": llama_available,
            "ollama_url": OLLAMA_BASE_URL,
            "llama_model": LLAMA_MODEL,
            "data_source": data_source,
            "auto_load_path": auto_load_path if data_source == "auto-loaded" else None
        }

# Initialize Ollama client
ollama_client = OllamaClient()

# Log initialization info
logger.info(f"Application starting with Ollama URL: {OLLAMA_BASE_URL}")
logger.info(f"Llama model: {LLAMA_MODEL}")

stig_loader = EnhancedSTIGDataLoader()

# Auto-load STIG data on startup if specified
AUTO_LOAD_STIG_PATH = os.getenv("AUTO_LOAD_STIG_PATH")
if AUTO_LOAD_STIG_PATH and os.path.exists(AUTO_LOAD_STIG_PATH):
    try:
        logger.info(f"Auto-loading STIG data from: {AUTO_LOAD_STIG_PATH}")
        stig_data = stig_loader.load_stig_json(AUTO_LOAD_STIG_PATH)
        stig_loader.index_stig_data(stig_data)
        stats = stig_loader.get_stats()
        logger.info(f"✅ Successfully auto-loaded {stats['total_controls']} STIG controls")
    except Exception as e:
        logger.error(f"❌ Failed to auto-load STIG data: {e}")
        logger.error("Application will continue but STIG data upload will be required")
elif AUTO_LOAD_STIG_PATH:
    logger.warning(f"Auto-load path specified but file not found: {AUTO_LOAD_STIG_PATH}")
    logger.warning("Application will continue but STIG data upload will be required")
else:
    logger.info("No auto-load path specified. STIG data upload will be required.")

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
        details summary { font-weight: bold; }
        details[open] summary { margin-bottom: 10px; }
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

        <div id="upload-section" class="form-section" style="display: none;">
            <h3>📁 Upload STIG Data</h3>
            <form action="/upload-stig" method="post" enctype="multipart/form-data">
                <input type="file" name="stig_file" accept=".json" required>
                <button type="submit">🚀 Load STIG Data</button>
            </form>
        </div>

        <div id="loaded-section" class="form-section" style="display: none;">
            <h3>📁 STIG Data Status</h3>
            <div id="loaded-info" style="background: #d4edda; padding: 15px; border-radius: 8px; border-left: 5px solid #28a745; margin-bottom: 15px;">
                <div id="loaded-details">Data loaded successfully</div>
            </div>
            <details>
                <summary style="cursor: pointer; padding: 10px; background: #f8f9fa; border-radius: 4px; margin-bottom: 10px;">
                    🔄 Replace STIG Data (Advanced)
                </summary>
                <form action="/upload-stig" method="post" enctype="multipart/form-data" style="margin-top: 10px;">
                    <input type="file" name="stig_file" accept=".json" required>
                    <button type="submit">🔄 Replace Current Data</button>
                </form>
            </details>
        </div>

        <div id="query-section" class="form-section" style="display: none;">
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
            
            <div id="example-questions" style="display: none; margin-top: 20px; padding: 15px; background: #fff; border-radius: 8px; border-left: 4px solid #1976d2;">
                <h5>💡 Try asking questions like:</h5>
                <ul>
                    <li>"How do I configure SSH security settings?"</li>
                    <li>"What are the firewall requirements for RHEL?"</li>
                    <li>"Show me SELinux configuration steps"</li>
                    <li>"What controls are related to password policies?"</li>
                    <li>"How do I implement audit logging?"</li>
                </ul>
            </div>
        </div>
    </div>

    <script>
        // Check Llama and STIG data status
        fetch('/api/stats')
            .then(r => r.json())
            .then(data => {
                const llamaStatus = document.getElementById('llama-status');
                const llamaContent = document.getElementById('llama-content');
                const status = document.getElementById('status');
                const statusContent = document.getElementById('status-content');
                
                const uploadSection = document.getElementById('upload-section');
                const loadedSection = document.getElementById('loaded-section');
                const querySection = document.getElementById('query-section');
                const loadedDetails = document.getElementById('loaded-details');
                const exampleQuestions = document.getElementById('example-questions');

                // Handle Llama status
                if (data.llama_available) {
                    llamaStatus.className = 'llama-status llama-online';
                    llamaContent.innerHTML = '🦙 Llama 3.2 is online and ready for intelligent responses!';
                } else {
                    llamaStatus.className = 'llama-status llama-offline';
                    llamaContent.innerHTML = '⚠️ Llama 3.2 is offline. Install: <code>ollama pull llama3.2:3b</code>';
                }

                // Handle STIG data status
                if (data.status === 'loaded') {
                    const controlCount = data.total_controls || 0;
                    const dataSource = data.data_source || 'unknown';
                    const autoLoadPath = data.auto_load_path;
                    
                    // Hide status section and upload section
                    status.style.display = 'none';
                    uploadSection.style.display = 'none';
                    
                    // Show loaded section and query section
                    loadedSection.style.display = 'block';
                    querySection.style.display = 'block';
                    exampleQuestions.style.display = 'block';
                    
                    // Update loaded details based on data source
                    let sourceInfo = '';
                    if (dataSource === 'auto-loaded') {
                        sourceInfo = `<p><strong>📁 Source:</strong> Auto-loaded on container startup</p>`;
                        if (autoLoadPath) {
                            sourceInfo += `<p><strong>📂 File:</strong> ${autoLoadPath}</p>`;
                        }
                    } else if (dataSource === 'uploaded') {
                        sourceInfo = `<p><strong>📁 Source:</strong> Uploaded via web interface</p>`;
                    }
                    
                    loadedDetails.innerHTML = `
                        <h4>✅ STIG Data Ready</h4>
                        <p><strong>${controlCount}</strong> STIG controls loaded and indexed</p>
                        ${sourceInfo}
                        <p><strong>🔍 Search:</strong> ${data.search_method || 'Text search with AI enhancement'}</p>
                        <p><em>🤖 Ready for AI-powered STIG questions! Use the form below.</em></p>
                    `;
                } else {
                    // Show status section and upload section
                    status.className = 'status no-data';
                    statusContent.innerHTML = '⚠️ No STIG data loaded. Upload JSON file below to get started.';
                    status.style.display = 'block';
                    uploadSection.style.display = 'block';
                    
                    // Hide loaded section and query section
                    loadedSection.style.display = 'none';
                    querySection.style.display = 'none';
                    exampleQuestions.style.display = 'none';
                }
            })
            .catch(error => {
                console.error('Error fetching status:', error);
                // Show upload form as fallback
                document.getElementById('upload-section').style.display = 'block';
                document.getElementById('status').innerHTML = '<div class="status no-data"><div>⚠️ Unable to check system status. Upload STIG data below.</div></div>';
                document.getElementById('example-questions').style.display = 'none';
            });
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
        # Check if data was previously auto-loaded
        was_auto_loaded = stig_loader.data_loaded and os.getenv("AUTO_LOAD_STIG_PATH")
        
        file_path = f"stig_data/{stig_file.filename}"
        with open(file_path, "wb") as f:
            content = await stig_file.read()
            f.write(content)

        stig_data = stig_loader.load_stig_json(file_path)
        stig_loader.index_stig_data(stig_data)
        stats = stig_loader.get_stats()

        action = "replaced" if was_auto_loaded else "loaded"
        message = f"Successfully {action} STIG data: {stats['total_controls']} controls from {stig_file.filename}"
        
        if was_auto_loaded:
            logger.info(f"User replaced auto-loaded STIG data with uploaded file: {stig_file.filename}")
        else:
            logger.info(f"User uploaded STIG data: {stig_file.filename}")

        return JSONResponse({
            "message": message,
            "stats": stats,
            "status": "success",
            "action": action
        })
    except Exception as e:
        logger.error(f"Failed to upload STIG data: {e}")
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
    print(f"🦙 Ollama URL: {OLLAMA_BASE_URL}")
    print(f"🤖 Model: {LLAMA_MODEL}")
    print("🦙 Make sure Ollama is running and accessible")
    print("🌐 Web Interface: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
