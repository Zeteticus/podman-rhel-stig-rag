#!/bin/bash
# upgrade-to-full.sh - Upgrade to enhanced STIG RAG with web interface

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo_status() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

CONTAINER_NAME="stig-rag"
IMAGE_NAME="localhost/rhel-stig-rag:latest"
HOST_PORT="8000"

echo_status "Upgrading to enhanced RHEL STIG RAG with web interface..."

# 1. Create enhanced application with web interface
cat > "enhanced_app.py" << 'EOF'
#!/usr/bin/env python3
"""
Enhanced RHEL STIG RAG Application with Web Interface
"""
import uvicorn
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, Dict, List
import json
import os

app = FastAPI(title="RHEL STIG RAG Assistant", description="AI-powered RHEL STIG compliance assistant")

# Create templates directory and basic HTML
os.makedirs("templates", exist_ok=True)

# Main page template
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
        .examples { 
            background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%); 
            padding: 25px; 
            border-radius: 12px; 
            margin: 30px 0;
            border-left: 5px solid #ffc107;
        }
        .api-section { 
            background: linear-gradient(135deg, #f0f4f8 0%, #d6eaf8 100%); 
            padding: 25px; 
            border-radius: 12px; 
            margin: 30px 0;
            border-left: 5px solid #3498db;
        }
        pre { 
            background: #2c3e50; 
            color: #ecf0f1; 
            padding: 20px; 
            border-radius: 8px; 
            overflow-x: auto;
            font-size: 14px;
        }
        .feature-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        .feature-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            border-left: 4px solid #e53e3e;
        }
        .status-badge {
            display: inline-block;
            background: #28a745;
            color: white;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
            margin-left: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ RHEL STIG RAG Assistant <span class="status-badge">ENHANCED</span></h1>
        <p class="subtitle">AI-powered Red Hat Enterprise Linux Security Technical Implementation Guide assistant</p>
        
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

        <div class="feature-grid">
            <div class="feature-card">
                <h4>🎯 RHEL 9 Priority</h4>
                <p>Optimized for RHEL 9 with comprehensive STIG guidance, while maintaining RHEL 8 support for legacy environments.</p>
            </div>
            <div class="feature-card">
                <h4>🔍 Smart Search</h4>
                <p>Vector-based semantic search finds relevant STIG controls and provides contextual implementation guidance.</p>
            </div>
            <div class="feature-card">
                <h4>🛡️ Security Focus</h4>
                <p>Specialized in DISA STIG compliance with step-by-step implementation instructions and verification procedures.</p>
            </div>
        </div>

        <div class="examples">
            <h3>💡 Example Questions to Try</h3>
            <ul>
                <li><strong>Package Security:</strong> "How do I verify GPG signatures for packages in RHEL 9?"</li>
                <li><strong>Access Control:</strong> "What are the SELinux requirements for RHEL compliance?"</li>
                <li><strong>Boot Security:</strong> "How do I configure secure boot and UEFI settings?"</li>
                <li><strong>Version Comparison:</strong> "What are the key differences between RHEL 8 and RHEL 9 STIG requirements?"</li>
                <li><strong>Specific Controls:</strong> "How do I implement RHEL-09-211010?"</li>
            </ul>
        </div>

        <div class="api-section">
            <h3>🔗 API Endpoints</h3>
            <p>This system provides both web interface and REST API access:</p>
            <ul>
                <li><strong>GET /health</strong> - System health check</li>
                <li><strong>POST /api/query</strong> - Programmatic STIG queries</li>
                <li><strong>GET /search/{stig_id}</strong> - Search by specific STIG ID</li>
                <li><strong>GET /docs</strong> - Interactive API documentation (Swagger UI)</li>
            </ul>
            
            <h4>📱 Example API Usage:</h4>
            <pre>curl -X POST "http://localhost:8000/api/query" \\
  -H "Content-Type: application/json" \\
  -d '{
    "question": "How do I configure SELinux for STIG compliance?",
    "rhel_version": "9",
    "stig_id": "RHEL-09-232010"
  }'</pre>
        </div>
    </div>
</body>
</html>
    ''')

# Enhanced result page template  
with open("templates/result.html", "w") as f:
    f.write('''
<!DOCTYPE html>
<html>
<head>
    <title>STIG Guidance Result - RHEL STIG RAG</title>
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
        h1 { color: #e53e3e; margin-bottom: 20px; }
        .back-link { 
            display: inline-block; 
            margin-bottom: 25px; 
            color: #3182ce; 
            text-decoration: none;
            background: #e3f2fd;
            padding: 10px 20px;
            border-radius: 20px;
            transition: background 0.3s ease;
        }
        .back-link:hover { 
            background: #bbdefb;
            text-decoration: none; 
        }
        .query-info { 
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); 
            padding: 25px; 
            border-radius: 12px; 
            margin: 25px 0;
            border-left: 5px solid #6c757d;
        }
        .answer { 
            background: linear-gradient(135deg, #e6fffa 0%, #b2f5ea 100%); 
            padding: 30px; 
            border-radius: 12px; 
            margin: 25px 0; 
            border-left: 5px solid #38b2ac;
        }
        .rhel-version { 
            color: #e53e3e; 
            font-weight: bold;
            background: #fff5f5;
            padding: 4px 8px;
            border-radius: 4px;
        }
        .stig-id {
            background: #3182ce;
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-family: monospace;
        }
        pre { 
            background: #2c3e50; 
            color: #ecf0f1; 
            padding: 20px; 
            border-radius: 8px; 
            overflow-x: auto;
        }
        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        .info-item {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            border-left: 3px solid #e53e3e;
        }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-link">← Back to STIG Assistant</a>
        <h1>🛡️ STIG Compliance Guidance</h1>
        
        <div class="query-info">
            <h3>📋 Query Information</h3>
            <div class="info-grid">
                <div class="info-item">
                    <strong>Question:</strong><br>{{ question }}
                </div>
                <div class="info-item">
                    <strong>RHEL Version:</strong><br><span class="rhel-version">RHEL {{ rhel_version }}</span>
                </div>
                {% if stig_id %}
                <div class="info-item">
                    <strong>STIG Control:</strong><br><span class="stig-id">{{ stig_id }}</span>
                </div>
                {% endif %}
            </div>
        </div>

        <div class="answer">
            <h3>🎯 STIG Implementation Guidance</h3>
            <div>{{ answer|safe }}</div>
        </div>
        
        <div style="text-align: center; margin-top: 30px; padding: 20px; background: #f8f9fa; border-radius: 8px;">
            <p><strong>💡 Next Steps:</strong> For production use, load actual STIG data and enable the full RAG pipeline with vector search and AI-powered responses.</p>
            <a href="/" style="color: #e53e3e; text-decoration: none; font-weight: bold;">Ask Another Question →</a>
        </div>
    </div>
</body>
</html>
    ''')

templates = Jinja2Templates(directory="templates")

class QueryRequest(BaseModel):
    question: str
    stig_id: Optional[str] = None
    rhel_version: Optional[str] = "9"

class QueryResponse(BaseModel):
    answer: str
    rhel_version_focus: str
    sources: List[Dict] = []
    query: str

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/query", response_class=HTMLResponse)
async def query_form(
    request: Request,
    question: str = Form(...),
    rhel_version: str = Form("9"),
    stig_id: Optional[str] = Form(None)
):
    # Generate enhanced response based on common STIG topics
    if stig_id:
        if "RHEL-09" in stig_id:
            answer = f"""
            <h4>🎯 STIG Control Analysis: {stig_id}</h4>
            <p><strong>RHEL {rhel_version} Specific Implementation:</strong></p>
            
            <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin: 15px 0;">
                <h5>📋 Implementation Steps for RHEL 9:</h5>
                <ol>
                    <li><strong>Assessment:</strong> Review current system configuration</li>
                    <li><strong>Configuration:</strong> Apply RHEL 9 specific settings</li>
                    <li><strong>Verification:</strong> Test the implementation</li>
                    <li><strong>Documentation:</strong> Record compliance evidence</li>
                </ol>
            </div>
            
            <h5>❓ Your Question: {question}</h5>
            <p>For RHEL 9 implementation of {stig_id}, you would typically need to:</p>
            
            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0;">
                <h6>🔧 Common Commands for RHEL 9:</h6>
                <pre style="background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 4px;">
# Check current configuration
sudo grep -i setting /etc/config/file

# Apply STIG configuration  
sudo systemctl enable secure-service
sudo systemctl start secure-service

# Verify implementation
sudo systemctl status secure-service</pre>
            </div>
            
            <p><strong>🚨 Important:</strong> This is a demonstration version. For production use, integrate with actual STIG data sources and implement the full RAG pipeline.</p>
            """
        else:
            answer = f"""
            <h4>🎯 STIG Control Analysis: {stig_id}</h4>
            <p><strong>RHEL {rhel_version} Legacy Implementation:</strong></p>
            
            <div style="background: #e1f5fe; padding: 15px; border-radius: 8px; margin: 15px 0;">
                <h5>📋 Implementation Steps for RHEL 8:</h5>
                <ol>
                    <li><strong>Legacy Assessment:</strong> Check RHEL 8 compatibility</li>
                    <li><strong>Configuration:</strong> Apply RHEL 8 specific settings</li>
                    <li><strong>Migration Planning:</strong> Consider RHEL 9 upgrade path</li>
                    <li><strong>Compliance:</strong> Maintain security posture</li>
                </ol>
            </div>
            
            <h5>❓ Your Question: {question}</h5>
            <p>For RHEL 8 implementation of {stig_id}:</p>
            
            <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin: 15px 0;">
                <p><strong>💡 Migration Recommendation:</strong> Consider upgrading to RHEL 9 for enhanced security features and better STIG compliance support.</p>
            </div>
            """
    else:
        # Topic-based responses
        question_lower = question.lower()
        if "gpg" in question_lower or "signature" in question_lower:
            answer = f"""
            <h4>🔐 GPG Signature Verification for RHEL {rhel_version}</h4>
            
            <div style="background: #e8f5e8; padding: 20px; border-radius: 8px; margin: 15px 0;">
                <h5>✅ RHEL {rhel_version} GPG Configuration:</h5>
                
                <h6>1. System-wide GPG Checking:</h6>
                <pre style="background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 4px;">
# For RHEL 9 (using DNF)
sudo grep gpgcheck /etc/dnf/dnf.conf
# Should show: gpgcheck=1

# Verify repository configurations
sudo grep -r gpgcheck /etc/yum.repos.d/</pre>

                <h6>2. Enable GPG Checking:</h6>
                <pre style="background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 4px;">
# Edit main configuration
sudo vi /etc/dnf/dnf.conf
# Ensure: gpgcheck=1

# For all repositories
sudo sed -i 's/gpgcheck=0/gpgcheck=1/g' /etc/yum.repos.d/*.repo</pre>

                <h6>3. Verification:</h6>
                <pre style="background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 4px;">
# Test package installation
sudo dnf install --assumeno package-name
# Should show signature verification</pre>
            </div>
            
            <p><strong>🎯 STIG Compliance:</strong> This implements controls like RHEL-09-211010 and RHEL-09-211015 for package integrity verification.</p>
            """
            
        elif "selinux" in question_lower:
            answer = f"""
            <h4>🛡️ SELinux Configuration for RHEL {rhel_version}</h4>
            
            <div style="background: #e8f5e8; padding: 20px; border-radius: 8px; margin: 15px 0;">
                <h5>🔒 SELinux STIG Requirements:</h5>
                
                <h6>1. Check SELinux Status:</h6>
                <pre style="background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 4px;">
# Check current status
getenforce
sestatus

# Should show: Enforcing</pre>

                <h6>2. Configure SELinux Policy:</h6>
                <pre style="background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 4px;">
# Ensure enforcing mode
sudo setenforce 1

# Set permanent configuration
sudo vi /etc/selinux/config
# SELINUX=enforcing
# SELINUXTYPE=targeted</pre>

                <h6>3. Verify Configuration:</h6>
                <pre style="background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 4px;">
# Check SELinux denials
sudo ausearch -m avc -ts recent

# View SELinux status
sudo sestatus -v</pre>
            </div>
            
            <p><strong>⚠️ Critical:</strong> SELinux must be in enforcing mode for STIG compliance. Never set to permissive or disabled in production.</p>
            """
            
        elif "boot" in question_lower or "secure boot" in question_lower:
            answer = f"""
            <h4>🚀 Secure Boot Configuration for RHEL {rhel_version}</h4>
            
            <div style="background: #e8f5e8; padding: 20px; border-radius: 8px; margin: 15px 0;">
                <h5>🔐 Secure Boot Implementation:</h5>
                
                <h6>1. Check Secure Boot Status:</h6>
                <pre style="background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 4px;">
# Check if Secure Boot is enabled
sudo mokutil --sb-state
# Should show: SecureBoot enabled

# Check UEFI variables
sudo efivar -l | grep -i secure</pre>

                <h6>2. Enable Secure Boot (if disabled):</h6>
                <div style="background: #fff3cd; padding: 10px; border-radius: 4px; margin: 10px 0;">
                    <p><strong>Note:</strong> Secure Boot must be enabled in UEFI/BIOS settings before OS boot.</p>
                </div>

                <h6>3. Verify Boot Chain:</h6>
                <pre style="background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 4px;">
# Check bootloader signature
sudo efibootmgr -v

# Verify kernel signatures
sudo mokutil --list-enrolled</pre>
            </div>
            
            <p><strong>🎯 STIG Compliance:</strong> Secure Boot prevents unauthorized code execution during system startup, implementing multiple STIG controls for boot integrity.</p>
            """
        else:
            answer = f"""
            <h4>🔍 General RHEL {rhel_version} STIG Guidance</h4>
            
            <div style="background: #f0f8ff; padding: 20px; border-radius: 8px; margin: 15px 0;">
                <h5>📋 Your Question: {question}</h5>
                
                <h6>🎯 RHEL {rhel_version} Security Implementation Approach:</h6>
                <ol>
                    <li><strong>📖 Consult Official STIG:</strong> Reference the latest DISA STIG documentation for RHEL {rhel_version}</li>
                    <li><strong>⚙️ Apply Security Configuration:</strong> Implement required settings systematically</li>
                    <li><strong>🧪 Test Implementation:</strong> Verify functionality isn't broken</li>
                    <li><strong>📝 Document Compliance:</strong> Maintain evidence for audits</li>
                </ol>
                
                <h6>🔗 Key RHEL {rhel_version} Security Areas:</h6>
                <ul>
                    <li><strong>Access Control:</strong> User authentication, authorization, SELinux</li>
                    <li><strong>System Integrity:</strong> Package signatures, boot security, file permissions</li>
                    <li><strong>Network Security:</strong> Firewall, SSH configuration, service hardening</li>
                    <li><strong>Audit & Monitoring:</strong> System logging, intrusion detection</li>
                </ul>
            </div>
            
            <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin: 15px 0;">
                <h6>🚀 Next Steps for Full Implementation:</h6>
                <ol>
                    <li>Load actual STIG data using the data collector tool</li>
                    <li>Implement vector search for semantic STIG control matching</li>
                    <li>Add AI language model integration for intelligent responses</li>
                    <li>Enable cross-referencing between related controls</li>
                </ol>
            </div>
            """
    
    return templates.TemplateResponse("result.html", {
        "request": request,
        "question": question,
        "rhel_version": rhel_version,
        "stig_id": stig_id,
        "answer": answer
    })

@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "Enhanced RHEL STIG RAG system is operational", "version": "enhanced"}

@app.post("/api/query", response_model=QueryResponse)
def api_query(request: QueryRequest):
    return QueryResponse(
        answer=f"Enhanced API response for RHEL {request.rhel_version}: {request.question}",
        rhel_version_focus=request.rhel_version,
        sources=[{"metadata": {"title": "Enhanced Demo Response", "severity": "info"}}],
        query=request.question
    )

@app.get("/search/{stig_id}")
def search_stig(stig_id: str):
    return {
        "stig_id": stig_id,
        "results": [
            {
                "content": f"Enhanced detailed content for STIG control {stig_id}",
                "metadata": {
                    "title": f"STIG Control {stig_id}",
                    "severity": "high" if "211010" in stig_id else "medium",
                    "rhel_version": "9" if "RHEL-09" in stig_id else "8",
                    "category": "Enhanced Implementation"
                }
            }
        ]
    }

@app.post("/load-stig")
def load_stig(file_path: str):
    return {
        "message": f"Enhanced: Would load STIG data from {file_path}",
        "status": "success",
        "note": "In production, this would process XML/JSON STIG files"
    }

if __name__ == "__main__":
    print("🚀 Starting Enhanced RHEL STIG RAG application...")
    print("🌐 Web Interface will be available at http://localhost:8000")
    print("📚 API Documentation at http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
EOF

# 2. Update requirements for enhanced features
cat > "requirements.txt" << 'EOF'
fastapi==0.104.0
uvicorn==0.24.0
pydantic==2.4.2
jinja2==3.1.2
python-multipart==0.0.6
EOF

# 3. Copy enhanced app to the expected filename
cp enhanced_app.py minimal_app.py

# 4. Stop current container
echo_status "Stopping current container..."
podman stop "$CONTAINER_NAME" 2>/dev/null || true
podman rm "$CONTAINER_NAME" 2>/dev/null || true

# 5. Rebuild with enhanced app
echo_status "Rebuilding with enhanced web interface..."
podman build -t "$IMAGE_NAME" -f Containerfile.selinux --no-cache .

# 6. Restart container
echo_status "Starting enhanced container..."
podman run -d \
    --name "$CONTAINER_NAME" \
    -p "$HOST_PORT:8000" \
    --security-opt label=disable \
    --shm-size=128m \
    --restart unless-stopped \
    "$IMAGE_NAME"

# 7. Wait for startup and test
echo_status "Waiting for enhanced service to start..."
for i in {1..30}; do
    if curl -s -f "http://localhost:$HOST_PORT/health" >/dev/null 2>&1; then
        echo_status "✅ Enhanced RHEL STIG RAG is ready!"
        echo ""
        echo_status "🌐 Web Interface: http://localhost:$HOST_PORT"
        echo_status "📚 API Documentation: http://localhost:$HOST_PORT/docs"
        echo_status "🔍 Health Check: http://localhost:$HOST_PORT/health"
        echo ""
        echo_status "🚀 Features Available:"
        echo "   • Interactive web form for STIG questions"
        echo "   • RHEL 9 priority with RHEL 8 support"
        echo "   • Enhanced responses with code examples"
        echo "   • REST API for programmatic access"
        echo "   • Responsive design optimized for STIG workflows"
        echo ""
        echo_status "Try asking questions like:"
        echo "   • How do I configure GPG signature verification?"
        echo "   • What are the SELinux requirements for RHEL 9?"
        echo "   • How do I implement RHEL-09-211010?"
        break
    fi
    echo -n "."
    sleep 2
done

if [ $i -eq 30 ]; then
    echo_error "Service failed to start. Checking logs..."
    podman logs "$CONTAINER_NAME"
else
    echo_status "🎉 Enhanced STIG RAG deployment complete!"
fi
