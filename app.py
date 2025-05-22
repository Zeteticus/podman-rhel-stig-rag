#!/usr/bin/env python3
"""
Complete RHEL STIG RAG Implementation with Real Data - FINISHED VERSION
"""
import uvicorn
import os
import json
import xml.etree.ElementTree as ET
import requests
import zipfile
from pathlib import Path
from typing import Optional, Dict, List, Any
import logging
from datetime import datetime
import re

# Core RAG components
import chromadb
from sentence_transformers import SentenceTransformer
import openai
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

# FastAPI components
from fastapi import FastAPI, Request, Form, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RHEL STIG RAG Assistant", description="AI-powered RHEL STIG compliance assistant with real data")

# Global variables
EMBEDDING_MODEL = None
CHROMA_CLIENT = None
COLLECTION = None
OPENAI_CLIENT = None

class STIGDataLoader:
    """Load and process STIG documents from various sources"""

    def __init__(self, data_dir: str = "/app/stig_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        # STIG download URLs (updated as of 2024)
        self.stig_sources = {
            "rhel9": {
                "url": "https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/U_RHEL_9_STIG_V1R3_Manual-xccdf.xml.zip",
                "filename": "rhel9_stig.zip",
                "priority": 1
            },
            "rhel8": {
                "url": "https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/U_RHEL_8_STIG_V1R12_Manual-xccdf.xml.zip",
                "filename": "rhel8_stig.zip",
                "priority": 2
            },
            # Added additional STIG sources for comprehensive coverage
            "rhel7": {
                "url": "https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/U_RHEL_7_STIG_V3R14_Manual-xccdf.xml.zip",
                "filename": "rhel7_stig.zip",
                "priority": 3
            }
        }

    def download_stig(self, version: str) -> bool:
        """Download STIG document for specified version"""
        if version not in self.stig_sources:
            logger.error(f"Unknown STIG version: {version}")
            return False

        source = self.stig_sources[version]
        output_file = self.data_dir / source["filename"]

        # Check if file already exists
        if output_file.exists():
            logger.info(f"STIG file already exists: {output_file}")
            self.extract_stig(output_file)
            return True

        try:
            logger.info(f"Downloading {version} STIG...")
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(source["url"], stream=True, timeout=300, headers=headers)
            response.raise_for_status()

            with open(output_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"Downloaded to: {output_file}")

            # Extract if it's a zip file
            if output_file.suffix == '.zip':
                self.extract_stig(output_file)

            return True

        except requests.RequestException as e:
            logger.error(f"Error downloading STIG: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error downloading STIG: {e}")
            return False

    def extract_stig(self, zip_path: Path):
        """Extract STIG from zip file"""
        extract_dir = self.data_dir / zip_path.stem
        extract_dir.mkdir(exist_ok=True)

        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

            logger.info(f"Extracted to: {extract_dir}")

            # Find XML files
            xml_files = list(extract_dir.glob("*.xml"))
            if xml_files:
                logger.info(f"Found XML files: {[f.name for f in xml_files]}")
            else:
                # Sometimes XML files are in subdirectories
                xml_files = list(extract_dir.rglob("*.xml"))
                logger.info(f"Found XML files in subdirectories: {[f.name for f in xml_files]}")

        except zipfile.BadZipFile as e:
            logger.error(f"Error extracting zip: {e}")
        except Exception as e:
            logger.error(f"Unexpected error extracting zip: {e}")

    def parse_stig_xml(self, file_path: Path) -> List[Document]:
        """Parse STIG XML (XCCDF) format and extract controls"""
        documents = []

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            # Parse XCCDF namespace - handle multiple possible namespaces
            namespaces = {
                'xccdf': 'http://checklists.nist.gov/xccdf/1.1',
                'xccdf2': 'http://checklists.nist.gov/xccdf/1.2'
            }

            # Try to detect the correct namespace
            if root.tag.startswith('{'):
                detected_ns = root.tag[1:root.tag.index('}')]
                namespaces['xccdf'] = detected_ns

            # Extract STIG metadata
            title_elem = root.find('.//xccdf:title', namespaces) or root.find('.//title')
            stig_title = title_elem.text if title_elem is not None else str(file_path.name)

            version_elem = root.find('.//xccdf:version', namespaces) or root.find('.//version')
            stig_version = version_elem.text if version_elem is not None else "Unknown"

            logger.info(f"Parsing STIG: {stig_title} - {stig_version}")

            # Find all rules - try multiple XPath expressions
            rules = (root.findall('.//xccdf:Rule', namespaces) or 
                    root.findall('.//Rule') or
                    root.findall('.//*[local-name()="Rule"]'))

            logger.info(f"Found {len(rules)} rules in {file_path.name}")

            for rule in rules:
                stig_id = rule.get('id', '')
                severity = rule.get('severity', 'medium')
                weight = rule.get('weight', '10.0')

                # Extract title - try multiple approaches
                title_elem = (rule.find('xccdf:title', namespaces) or 
                             rule.find('title') or 
                             rule.find('.//*[local-name()="title"]'))
                title = title_elem.text if title_elem is not None else ''

                # Extract description
                desc_elem = (rule.find('xccdf:description', namespaces) or 
                            rule.find('description') or 
                            rule.find('.//*[local-name()="description"]'))
                description = desc_elem.text if desc_elem is not None else ''

                # Extract rationale
                rationale_elem = (rule.find('xccdf:rationale', namespaces) or 
                                 rule.find('rationale') or 
                                 rule.find('.//*[local-name()="rationale"]'))
                rationale = rationale_elem.text if rationale_elem is not None else ''

                # Extract check content
                check_elem = (rule.find('.//xccdf:check-content', namespaces) or 
                             rule.find('.//check-content') or 
                             rule.find('.//*[local-name()="check-content"]'))
                check_content = check_elem.text if check_elem is not None else ''

                # Extract fix text
                fix_elem = (rule.find('.//xccdf:fixtext', namespaces) or 
                           rule.find('.//fixtext') or 
                           rule.find('.//*[local-name()="fixtext"]'))
                fix_text = fix_elem.text if fix_elem is not None else ''

                # Extract references
                references = []
                for ref in (rule.findall('.//xccdf:ident', namespaces) or 
                           rule.findall('.//ident') or 
                           rule.findall('.//*[local-name()="ident"]')):
                    if ref.text:
                        references.append(ref.text)

                # Enhanced RHEL version detection
                rhel_version = "unknown"
                if "RHEL-09" in stig_id or "RHEL_9" in stig_title:
                    rhel_version = "9"
                elif "RHEL-08" in stig_id or "RHEL_8" in stig_title:
                    rhel_version = "8"
                elif "RHEL-07" in stig_id or "RHEL_7" in stig_title:
                    rhel_version = "7"

                # Skip empty rules
                if not title and not description and not check_content:
                    continue

                # Create comprehensive document content
                content = f"""
STIG Control: {stig_id}
Title: {title}
Severity: {severity}
Weight: {weight}
RHEL Version: {rhel_version}

Description:
{description}

Rationale:
{rationale}

Check Procedure:
{check_content}

Implementation/Fix:
{fix_text}

References: {', '.join(references)}
                """.strip()

                metadata = {
                    'stig_id': stig_id,
                    'title': title,
                    'severity': severity,
                    'weight': float(weight) if weight.replace('.', '').isdigit() else 10.0,
                    'rhel_version': rhel_version,
                    'references': references,
                    'source_file': str(file_path),
                    'stig_title': stig_title,
                    'stig_version': stig_version,
                    'priority': 1 if rhel_version == "9" else 2 if rhel_version == "8" else 3,
                    'type': 'stig_control'
                }

                documents.append(Document(page_content=content, metadata=metadata))

        except ET.ParseError as e:
            logger.error(f"XML parse error in {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error parsing STIG XML {file_path}: {e}")

        logger.info(f"Successfully parsed {len(documents)} controls from {file_path.name}")
        return documents

class STIGVectorStore:
    """Manage vector storage for STIG documents"""

    def __init__(self, persist_directory: str = "/app/stig_chroma_db"):
        self.persist_directory = persist_directory

        # Initialize embedding model
        global EMBEDDING_MODEL
        if EMBEDDING_MODEL is None:
            logger.info("Loading embedding model...")
            try:
                EMBEDDING_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("Embedding model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                # Fallback to a different model
                EMBEDDING_MODEL = SentenceTransformer('paraphrase-MiniLM-L6-v2')

        # Initialize ChromaDB
        global CHROMA_CLIENT, COLLECTION
        if CHROMA_CLIENT is None:
            try:
                CHROMA_CLIENT = chromadb.PersistentClient(path=persist_directory)
                try:
                    COLLECTION = CHROMA_CLIENT.get_collection("stig_controls")
                    logger.info("Loaded existing STIG collection")
                except:
                    COLLECTION = CHROMA_CLIENT.create_collection("stig_controls")
                    logger.info("Created new STIG collection")
            except Exception as e:
                logger.error(f"Failed to initialize ChromaDB: {e}")
                raise

    def add_documents(self, documents: List[Document]):
        """Add documents to the vector store"""
        if not documents:
            return

        logger.info(f"Adding {len(documents)} documents to vector store...")

        # Prepare data for ChromaDB
        ids = []
        embeddings = []
        metadatas = []
        documents_text = []

        for i, doc in enumerate(documents):
            doc_id = doc.metadata.get('stig_id', f'doc_{i}_{datetime.now().timestamp()}')
            
            # Ensure unique IDs
            if doc_id in ids:
                doc_id = f"{doc_id}_{i}"
            
            ids.append(doc_id)

            try:
                # Create embedding
                embedding = EMBEDDING_MODEL.encode(doc.page_content).tolist()
                embeddings.append(embedding)

                # Prepare metadata (ChromaDB requires string values)
                metadata = {}
                for k, v in doc.metadata.items():
                    if isinstance(v, list):
                        metadata[k] = ', '.join(str(item) for item in v)
                    else:
                        metadata[k] = str(v)
                metadatas.append(metadata)

                documents_text.append(doc.page_content)

            except Exception as e:
                logger.error(f"Error processing document {doc_id}: {e}")
                continue

        if ids:
            try:
                # Add to collection
                COLLECTION.add(
                    ids=ids,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    documents=documents_text
                )
                logger.info(f"Successfully added {len(ids)} documents to vector store")
            except Exception as e:
                logger.error(f"Error adding documents to collection: {e}")

    def search(self, query: str, n_results: int = 5, rhel_version: Optional[str] = None) -> List[Dict]:
        """Search for relevant documents"""
        try:
            # Create query embedding
            query_embedding = EMBEDDING_MODEL.encode(query).tolist()

            # Prepare filters
            where_filter = {}
            if rhel_version:
                where_filter["rhel_version"] = rhel_version

            # Search
            results = COLLECTION.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter if where_filter else None
            )

            # Format results
            formatted_results = []
            if results['documents']:
                for i in range(len(results['documents'][0])):
                    formatted_results.append({
                        'content': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i],
                        'distance': results['distances'][0][i] if 'distances' in results else 0.0
                    })

            return formatted_results

        except Exception as e:
            logger.error(f"Error searching vector store: {e}")
            return []

class STIGRAGGenerator:
    """Generate responses using retrieved STIG information"""

    def __init__(self):
        global OPENAI_CLIENT

        # Initialize OpenAI client if API key is available
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if openai_api_key:
            try:
                OPENAI_CLIENT = openai.OpenAI(api_key=openai_api_key)
                logger.info("OpenAI client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                OPENAI_CLIENT = None
        else:
            logger.warning("OpenAI API key not found. Using template responses.")

    def generate_response(self, query: str, retrieved_docs: List[Dict], rhel_version: str = "9") -> str:
        """Generate a response using retrieved STIG documents"""

        if not retrieved_docs:
            return self._generate_fallback_response(query, rhel_version)

        # If OpenAI is available, use it
        if OPENAI_CLIENT:
            return self._generate_openai_response(query, retrieved_docs, rhel_version)
        else:
            return self._generate_template_response(query, retrieved_docs, rhel_version)

    def _generate_openai_response(self, query: str, retrieved_docs: List[Dict], rhel_version: str) -> str:
        """Generate response using OpenAI"""
        try:
            # Prepare context from retrieved documents
            context = "\n\n".join([
                f"STIG Control {doc['metadata']['stig_id']}:\n{doc['content'][:1000]}..."
                for doc in retrieved_docs[:3]
            ])

            # Create prompt
            prompt = f"""You are an expert RHEL security consultant specializing in DISA STIG compliance.
Based on the following STIG documentation, provide detailed implementation guidance for RHEL {rhel_version}.

STIG Documentation:
{context}

User Question: {query}

Please provide:
1. Relevant STIG control(s)
2. Step-by-step implementation instructions
3. Verification procedures
4. Any RHEL {rhel_version} specific considerations
5. Command examples where appropriate

Format your response as HTML with proper headings and styling."""

            response = OPENAI_CLIENT.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert RHEL security consultant specializing in DISA STIG compliance. Provide detailed, accurate, and actionable guidance."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1500,
                temperature=0.1
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            return self._generate_template_response(query, retrieved_docs, rhel_version)

    def _generate_template_response(self, query: str, retrieved_docs: List[Dict], rhel_version: str) -> str:
        """Generate response using templates based on retrieved docs"""

        if not retrieved_docs:
            return self._generate_fallback_response(query, rhel_version)

        # Get the most relevant document
        top_doc = retrieved_docs[0]
        metadata = top_doc['metadata']
        content = top_doc['content']

        stig_id = metadata.get('stig_id', 'Unknown')
        title = metadata.get('title', 'Unknown Control')
        severity = metadata.get('severity', 'medium')

        # Extract sections from content
        sections = content.split('\n\n')
        check_section = next((s for s in sections if 'Check Procedure:' in s), '')
        fix_section = next((s for s in sections if 'Implementation/Fix:' in s), '')
        description_section = next((s for s in sections if 'Description:' in s), '')

        response = f"""
<div class="stig-response">
<h4>🎯 STIG Control: {stig_id}</h4>
<p><strong>Title:</strong> {title}</p>
<p><strong>Severity:</strong> <span class="severity-{severity}">{severity.upper()}</span></p>
<p><strong>RHEL Version:</strong> {rhel_version}</p>

<h5>📋 Your Question:</h5>
<p><em>{query}</em></p>

<h5>📝 STIG Description:</h5>
<div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0;">
{description_section.replace('Description:', '').strip()}
</div>

<h5>🔍 STIG Requirements:</h5>
<div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0;">
{check_section.replace('Check Procedure:', '').strip()}
</div>

<h5>⚙️ Implementation Steps:</h5>
<div style="background: #e8f5e8; padding: 15px; border-radius: 8px; margin: 15px 0;">
{fix_section.replace('Implementation/Fix:', '').strip()}
</div>

<h5>🔄 Additional Related Controls:</h5>
<ul>
"""

        # Add related controls
        for doc in retrieved_docs[1:4]:
            doc_meta = doc['metadata']
            doc_title = doc_meta.get('title', 'Unknown')[:80]
            response += f"<li><strong>{doc_meta.get('stig_id', 'Unknown')}:</strong> {doc_title}{'...' if len(doc_meta.get('title', '')) > 80 else ''}</li>"

        response += """
</ul>

<div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin: 15px 0;">
<p><strong>💡 Implementation Note:</strong> This guidance is based on official DISA STIG documentation. Always test configurations in a non-production environment first and ensure they meet your organization's specific requirements.</p>
</div>
</div>
"""

        return response

    def _generate_fallback_response(self, query: str, rhel_version: str) -> str:
        """Generate fallback response when no documents are found"""
        return f"""
<div class="stig-response">
<h4>🔍 STIG Information Search</h4>
<p><strong>Query:</strong> {query}</p>
<p><strong>RHEL Version:</strong> {rhel_version}</p>

<div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin: 15px 0;">
<p><strong>⚠️ No specific STIG controls found for this query.</strong></p>
<p>This could mean:</p>
<ul>
<li>The STIG data hasn't been loaded yet</li>
<li>Your query doesn't match existing STIG controls</li>
<li>Try using different keywords or a more specific question</li>
</ul>
</div>

<h5>💡 Suggestions:</h5>
<ul>
<li>Try searching for specific terms like "GPG", "SELinux", "firewall"</li>
<li>Use STIG control IDs like "RHEL-09-211010"</li>
<li>Ask about general security topics like "package management" or "access control"</li>
</ul>

<h5>🔧 Quick Actions:</h5>
<ul>
<li><a href="javascript:loadSTIGData('rhel{rhel_version}')">Load RHEL {rhel_version} STIG Data</a></li>
<li><a href="javascript:checkDataStatus()">Check Data Status</a></li>
</ul>
</div>
"""

# Initialize global components
def initialize_components():
    """Initialize all components with error handling"""
    global stig_loader, vector_store, rag_generator
    
    try:
        stig_loader = STIGDataLoader()
        vector_store = STIGVectorStore()
        rag_generator = STIGRAGGenerator()
        logger.info("All components initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        raise

# Create templates directory and files
def setup_templates():
    """Create all required template files"""
    os.makedirs("templates", exist_ok=True)
    os.makedirs("static", exist_ok=True)

    # Create enhanced index.html (already exists in your code)
    with open("templates/index.html", "w") as f:
        f.write('''<!DOCTYPE html>
<html>
<head>
    <title>RHEL STIG RAG Assistant - Production</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 40px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
        h1 { color: #e53e3e; text-align: center; margin-bottom: 10px; font-size: 2.5em; }
        .subtitle { text-align: center; color: #666; margin-bottom: 30px; font-size: 1.1em; }
        .status-badge { display: inline-block; background: #28a745; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 600; margin-left: 10px; }
        .query-form { background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); padding: 30px; border-radius: 12px; margin: 30px 0; border: 1px solid #dee2e6; }
        .form-group { margin: 20px 0; }
        label { display: block; margin-bottom: 8px; font-weight: 600; color: #495057; }
        input, select, textarea { width: 100%; padding: 12px; border: 2px solid #dee2e6; border-radius: 8px; box-sizing: border-box; font-size: 14px; transition: border-color 0.3s ease; }
        input:focus, select:focus, textarea:focus { outline: none; border-color: #e53e3e; }
        button { background: linear-gradient(135deg, #e53e3e 0%, #c53030 100%); color: white; padding: 12px 30px; border: none; border-radius: 8px; cursor: pointer; font-size: 16px; font-weight: 600; transition: transform 0.2s ease; }
        button:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(229, 62, 62, 0.4); }
        .admin-section { background: linear-gradient(135deg, #f0f4f8 0%, #d6eaf8 100%); padding: 25px; border-radius: 12px; margin: 30px 0; border-left: 5px solid #3498db; }
        .feature-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin: 30px 0; }
        .feature-card { background: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 4px solid #e53e3e; }
        .severity-high { color: #dc3545; font-weight: bold; }
        .severity-medium { color: #fd7e14; font-weight: bold; }
        .severity-low { color: #28a745; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ RHEL STIG RAG Assistant <span class="status-badge">PRODUCTION</span></h1>
        <p class="subtitle">AI-powered RHEL Security Technical Implementation Guide assistant with real DISA STIG data</p>

        <div class="query-form">
            <h3>🔍 Ask a STIG Compliance Question</h3>
            <form action="/query" method="post">
                <div class="form-group">
                    <label for="question">🤔 Your Question:</label>
                    <textarea name="question" id="question" rows="4" placeholder="How do I configure GPG signature verification in RHEL 9? What are the SELinux requirements? How do I implement RHEL-09-211010?" required></textarea>
                </div>
                <div class="form-group">
                    <label for="rhel_version">🐧 RHEL Version:</label>
                    <select name="rhel_version" id="rhel_version">
                        <option value="9" selected>RHEL 9 (Primary Focus)</option>
                        <option value="8">RHEL 8 (Legacy Support)</option>
                        <option value="7">RHEL 7 (Legacy Support)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="stig_id">🎯 Specific STIG Control ID (optional):</label>
                    <input type="text" name="stig_id" id="stig_id" placeholder="e.g., RHEL-09-211010 or RHEL-08-010020">
                </div>
                <button type="submit">🚀 Get STIG Guidance</button>
            </form>
        </div>

        <div class="admin-section">
            <h3>🔧 Data Management</h3>
            <p>Manage STIG data and system configuration:</p>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                <button onclick="loadSTIGData('rhel9')" style="margin: 5px;">📥 Load RHEL 9 STIG</button>
                <button onclick="loadSTIGData('rhel8')" style="margin: 5px;">📥 Load RHEL 8 STIG</button>
                <button onclick="loadSTIGData('rhel7')" style="margin: 5px;">📥 Load RHEL 7 STIG</button>
                <button onclick="checkDataStatus()" style="margin: 5px;">📊 Check Data Status</button>
                <a href="/docs" style="text-decoration: none;"><button style="margin: 5px;">📚 API Docs</button></a>
            </div>
            <div id="status-message" style="margin-top: 15px; padding: 10px; border-radius: 5px; display: none;"></div>
        </div>

        <div class="feature-grid">
            <div class="feature-card">
                <h4>🎯 Real STIG Data</h4>
                <p>Powered by official DISA STIG documentation with real control implementations and verification procedures.</p>
            </div>
            <div class="feature-card">
                <h4>🔍 AI-Powered Search</h4>
                <p>Semantic search finds relevant STIG controls and generates contextual implementation guidance using AI.</p>
            </div>
            <div class="feature-card">
                <h4>🛡️ Multi-Version Support</h4>
                <p>Comprehensive support for RHEL 9, 8, and 7 with version-specific guidance and recommendations.</p>
            </div>
        </div>
    </div>

    <script>
        async function loadSTIGData(version) {
            const statusDiv = document.getElementById('status-message');
            statusDiv.style.display = 'block';
            statusDiv.style.background = '#fff3cd';
            statusDiv.innerHTML = `🔄 Loading ${version.toUpperCase()} STIG data... This may take a few minutes.`;

            try {
                const response = await fetch(`/load-stig/${version}`, { method: 'POST' });
                const result = await response.json();

                if (response.ok) {
                    statusDiv.style.background = '#d4edda';
                    statusDiv.innerHTML = `✅ ${result.message}`;
                } else {
                    statusDiv.style.background = '#f8d7da';
                    statusDiv.innerHTML = `❌ Error: ${result.detail}`;
                }
            } catch (error) {
                statusDiv.style.background = '#f8d7da';
                statusDiv.innerHTML = `❌ Error: ${error.message}`;
            }
        }

        async function checkDataStatus() {
            const statusDiv = document.getElementById('status-message');
            statusDiv.style.display = 'block';
            statusDiv.style.background = '#e2e3e5';
            statusDiv.innerHTML = '🔍 Checking data status...';

            try {
                const response = await fetch('/data-status');
                const result = await response.json();

                statusDiv.style.background = '#d1ecf1';
                statusDiv.innerHTML = `📊 STIG Data Status:<br>
                    Total Controls: ${result.total_controls}<br>
                    RHEL 9 Controls: ${result.rhel9_controls}<br>
                    RHEL 8 Controls: ${result.rhel8_controls}<br>
                    RHEL 7 Controls: ${result.rhel7_controls || 0}<br>
                    Last Updated: ${result.last_updated}`;
            } catch (error) {
                statusDiv.style.background = '#f8d7da';
                statusDiv.innerHTML = `❌ Error: ${error.message}`;
            }
        }
    </script>
</body>
</html>''')

    # Create the missing result.html template
    with open("templates/result.html", "w") as f:
        f.write('''<!DOCTYPE html>
<html>
<head>
    <title>STIG Query Results - RHEL STIG RAG Assistant</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 40px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
        h1 { color: #e53e3e; text-align: center; margin-bottom: 10px; font-size: 2.5em; }
        .subtitle { text-align: center; color: #666; margin-bottom: 30px; font-size: 1.1em; }
        .query-info { background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); padding: 20px; border-radius: 12px; margin: 20px 0; border-left: 5px solid #e53e3e; }
        .result-content { background: white; padding: 30px; border-radius: 12px; margin: 20px 0; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .severity-high { color: #dc3545; font-weight: bold; }
        .severity-medium { color: #fd7e14; font-weight: bold; }
        .severity-low { color: #28a745; font-weight: bold; }
        .stig-response h4, .stig-response h5 { color: #495057; }
        .stig-response div { margin: 15px 0; }
        .back-button { display: inline-block; background: linear-gradient(135deg, #6c757d 0%, #495057 100%); color: white; padding: 12px 30px; border: none; border-radius: 8px; text-decoration: none; font-size: 16px; font-weight: 600; transition: transform 0.2s ease; margin: 20px 0; }
        .back-button:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(108, 117, 125, 0.4); }
        .query-details { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
        .query-detail { background: #f8f9fa; padding: 15px; border-radius: 8px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ RHEL STIG RAG Assistant</h1>
        <p class="subtitle">Query Results</p>

        <div class="query-info">
            <h3>📋 Query Information</h3>
            <div class="query-details">
                <div class="query-detail">
                    <strong>Question:</strong><br>
                    {{ question }}
                </div>
                <div class="query-detail">
                    <strong>RHEL Version:</strong><br>
                    RHEL {{ rhel_version }}
                </div>
                {% if stig_id %}
                <div class="query-detail">
                    <strong>STIG Control ID:</strong><br>
                    {{ stig_id }}
                </div>
                {% endif %}
            </div>
        </div>

        <div class="result-content">
            <h3>🎯 STIG Implementation Guidance</h3>
            {{ answer|safe }}
        </div>

        <div style="text-align: center; margin: 30px 0;">
            <a href="/" class="back-button">← Ask Another Question</a>
            <a href="/docs" class="back-button" style="background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);">📚 API Documentation</a>
        </div>
    </div>
</body>
</html>''')

    # Create a basic CSS file for styling
    with open("static/style.css", "w") as f:
        f.write('''
/* Additional styling for STIG RAG Assistant */
.stig-response {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    line-height: 1.6;
}

.stig-response h4 {
    color: #e53e3e;
    border-bottom: 2px solid #e53e3e;
    padding-bottom: 10px;
}

.stig-response h5 {
    color: #495057;
    margin-top: 25px;
    margin-bottom: 15px;
}

.stig-response .severity-high {
    color: #dc3545;
    font-weight: bold;
}

.stig-response .severity-medium {
    color: #fd7e14;
    font-weight: bold;
}

.stig-response .severity-low {
    color: #28a745;
    font-weight: bold;
}

.stig-response code {
    background: #f8f9fa;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: 'Courier New', monospace;
}

.stig-response pre {
    background: #f8f9fa;
    padding: 15px;
    border-radius: 8px;
    overflow-x: auto;
    border-left: 4px solid #e53e3e;
}
        ''')

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

# Pydantic models
class QueryRequest(BaseModel):
    question: str
    stig_id: Optional[str] = None
    rhel_version: Optional[str] = "9"

class QueryResponse(BaseModel):
    answer: str
    rhel_version_focus: str
    sources: List[Dict] = []
    query: str

# Enhanced API endpoints
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
    try:
        # Use RAG system to generate response
        search_query = f"{question} {stig_id}" if stig_id else question
        retrieved_docs = vector_store.search(search_query, n_results=5, rhel_version=rhel_version)

        answer = rag_generator.generate_response(question, retrieved_docs, rhel_version)

        return templates.TemplateResponse("result.html", {
            "request": request,
            "question": question,
            "rhel_version": rhel_version,
            "stig_id": stig_id,
            "answer": answer
        })
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        error_message = f"""
        <div style="background: #f8d7da; padding: 20px; border-radius: 8px; color: #721c24;">
            <h4>❌ Error Processing Query</h4>
            <p>An error occurred while processing your request: {str(e)}</p>
            <p>Please try again or check the system status.</p>
        </div>
        """
        return templates.TemplateResponse("result.html", {
            "request": request,
            "question": question,
            "rhel_version": rhel_version,
            "stig_id": stig_id,
            "answer": error_message
        })

@app.post("/api/query", response_model=QueryResponse)
def api_query(request: QueryRequest):
    """API endpoint for programmatic access"""
    try:
        search_query = f"{request.question} {request.stig_id}" if request.stig_id else request.question
        retrieved_docs = vector_store.search(search_query, n_results=5, rhel_version=request.rhel_version)

        answer = rag_generator.generate_response(request.question, retrieved_docs, request.rhel_version)

        sources = [{"content": doc["content"][:200] + "...", "metadata": doc["metadata"]} for doc in retrieved_docs]

        return QueryResponse(
            answer=answer,
            rhel_version_focus=request.rhel_version,
            sources=sources,
            query=request.question
        )
    except Exception as e:
        logger.error(f"API query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/load-stig/{version}")
async def load_stig_data(version: str, background_tasks: BackgroundTasks):
    """Load STIG data in the background"""
    if version not in ["rhel7", "rhel8", "rhel9"]:
        raise HTTPException(status_code=400, detail="Invalid STIG version. Use 'rhel7', 'rhel8', or 'rhel9'")

    def load_data():
        try:
            logger.info(f"Starting background load of {version} STIG data")
            # Download STIG
            if stig_loader.download_stig(version):
                # Find extracted XML files
                extract_dir = stig_loader.data_dir / f"{version}_stig"
                xml_files = list(extract_dir.glob("*.xml"))
                
                if not xml_files:
                    # Try recursive search
                    xml_files = list(extract_dir.rglob("*.xml"))

                if xml_files:
                    # Parse and load into vector store
                    total_documents = 0
                    for xml_file in xml_files:
                        logger.info(f"Processing {xml_file}")
                        documents = stig_loader.parse_stig_xml(xml_file)
                        if documents:
                            vector_store.add_documents(documents)
                            total_documents += len(documents)
                            logger.info(f"Loaded {len(documents)} controls from {xml_file}")
                    
                    logger.info(f"Successfully loaded {total_documents} total controls for {version}")
                else:
                    logger.error(f"No XML files found for {version}")
            else:
                logger.error(f"Failed to download {version} STIG")
        except Exception as e:
            logger.error(f"Error in background STIG loading: {e}")

    background_tasks.add_task(load_data)

    return {"message": f"Started loading {version.upper()} STIG data. This will take a few minutes."}

@app.get("/data-status")
async def get_data_status():
    """Get current data status"""
    try:
        # Query collection for stats
        results = COLLECTION.get()
        total_controls = len(results['ids']) if results['ids'] else 0

        # Count by RHEL version
        rhel9_count = sum(1 for meta in results['metadatas'] if meta.get('rhel_version') == '9') if results['metadatas'] else 0
        rhel8_count = sum(1 for meta in results['metadatas'] if meta.get('rhel_version') == '8') if results['metadatas'] else 0
        rhel7_count = sum(1 for meta in results['metadatas'] if meta.get('rhel_version') == '7') if results['metadatas'] else 0

        return {
            "total_controls": total_controls,
            "rhel9_controls": rhel9_count,
            "rhel8_controls": rhel8_count,
            "rhel7_controls": rhel7_count,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        logger.error(f"Error getting data status: {e}")
        return {
            "total_controls": 0,
            "rhel9_controls": 0,
            "rhel8_controls": 0,
            "rhel7_controls": 0,
            "last_updated": "Never"
        }

@app.get("/health")
def health_check():
    """Health check endpoint"""
    try:
        # Test vector store connection
        vector_store.search("test", n_results=1)
        vector_store_status = "healthy"
    except:
        vector_store_status = "error"

    return {
        "status": "healthy",
        "message": "Production RHEL STIG RAG system with real data",
        "version": "production-complete",
        "features": ["real_stig_data", "vector_search", "ai_generation", "multi_version_support"],
        "components": {
            "vector_store": vector_store_status,
            "embedding_model": "loaded" if EMBEDDING_MODEL else "error",
            "openai_client": "available" if OPENAI_CLIENT else "unavailable"
        }
    }

@app.get("/system-info")
def system_info():
    """Get detailed system information"""
    return {
        "embedding_model": "all-MiniLM-L6-v2",
        "vector_store": "ChromaDB",
        "supported_versions": ["RHEL 7", "RHEL 8", "RHEL 9"],
        "data_sources": list(stig_loader.stig_sources.keys()),
        "ai_backend": "OpenAI GPT-3.5-turbo" if OPENAI_CLIENT else "Template-based responses"
    }

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize components on startup"""
    logger.info("🚀 Starting RHEL STIG RAG Assistant...")
    setup_templates()
    initialize_components()
    logger.info("✅ Application startup complete")

if __name__ == "__main__":
    print("🚀 Starting Complete Production RHEL STIG RAG application...")
    print("🌐 Web Interface will be available at http://localhost:8000")
    print("📚 API Documentation at http://localhost:8000/docs")
    print("🔧 Use the web interface to load STIG data before querying")
    print("💡 Features: Real STIG data, AI-powered search, Multi-version support")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
