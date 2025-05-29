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
        """Generate response using Llama with aggressive timeout handling"""
        try:
            # Aggressively truncate context if too long to prevent timeouts
            max_context_length = 1500  # Much smaller context
            if len(context) > max_context_length:
                context = context[:max_context_length] + "\n[...truncated...]"
            
            # Much shorter and simpler prompt
            full_prompt = f"""STIG Expert: Answer concisely using the provided controls.

Controls:
{context}

Question: {prompt}

Brief Answer:"""

            payload = {
                "model": self.model,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.9,
                    "num_predict": 150,   # Much shorter responses
                    "num_ctx": 1024,     # Smaller context window
                    "num_thread": 4      # Limit CPU usage
                }
            }

            logger.info(f"Sending short request to Ollama")
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=30  # Back to 30s but with much smaller context
            )

            if response.status_code == 200:
                result = response.json()
                return result.get('response', 'No response generated')
            else:
                error_msg = f"Error: Ollama returned status {response.status_code}"
                logger.error(error_msg)
                return error_msg

        except requests.exceptions.ConnectionError as e:
            error_msg = "Error: Cannot connect to Ollama."
            logger.error(f"{error_msg} Details: {e}")
            return error_msg
        except requests.exceptions.Timeout:
            error_msg = "Error: Request timed out. Consider disabling AI with DISABLE_AI=true"
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
            # Create enhanced searchable text with field separation
            searchable_text = self._create_enhanced_searchable_text(control_id, control_data).lower()
            words = re.findall(r'\b\w+\b', searchable_text)
            
            # Filter out very common words and short words for better indexing
            stop_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
            meaningful_words = [word for word in words if len(word) > 2 and word not in stop_words]
            
            for word in meaningful_words:
                if word not in self.search_index:
                    self.search_index[word] = []
                if control_id not in self.search_index[word]:
                    self.search_index[word].append(control_id)

        self.data_loaded = True
        logger.info(f"Indexed {len(stig_data)} STIG controls with enhanced search algorithm")

    def _create_enhanced_searchable_text(self, control_id, control_data):
        """Create enhanced searchable text with field importance markers"""
        text_parts = []
        
        # Control ID (high importance)
        text_parts.append(control_id)
        
        # Title (highest importance) - repeat for emphasis
        title = control_data.get('title', '')
        if title:
            text_parts.append(title)
            text_parts.append(title)  # Double weight
        
        # Description (high importance)
        description = control_data.get('description', '')
        if description:
            text_parts.append(description)
        
        # Check procedure (medium importance)
        check = control_data.get('check', '')
        if check:
            text_parts.append(check)
        
        # Fix procedure (lower importance for search)
        fix = control_data.get('fix', '')
        if fix:
            text_parts.append(fix)
        
        # Add severity and version info
        severity = control_data.get('severity', '')
        rhel_version = control_data.get('rhel_version', '')
        if severity:
            text_parts.append(f"severity {severity}")
        if rhel_version:
            text_parts.append(f"rhel {rhel_version}")
        
        return " ".join(text_parts)

    def _create_searchable_text(self, control_id, control_data):
        """Legacy method - redirects to enhanced version"""
        return self._create_enhanced_searchable_text(control_id, control_data)

    def search_controls(self, query: str, n_results: int = 5, rhel_version: Optional[str] = None):
        """Enhanced search with improved relevance scoring and optional version filtering"""
        if not self.data_loaded:
            return []

        query_lower = query.lower()
        
        # Enhanced keyword extraction and mapping
        enhanced_query = self._enhance_query_terms(query_lower)
        query_words = re.findall(r'\b\w+\b', enhanced_query)
        
        # Remove common stop words that don't add search value
        stop_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 
                     'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 
                     'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'must',
                     'how', 'what', 'when', 'where', 'why', 'which', 'who', 'that', 'this', 'these',
                     'those', 'a', 'an', 'some', 'any', 'all', 'each', 'every', 'many', 'much',
                     'show', 'tell', 'explain', 'describe', 'help', 'need', 'want', 'get', 'make'}
        
        query_words = [word for word in query_words if word not in stop_words and len(word) > 2]
        
        control_scores = {}

        # Score controls with weighted field importance
        for control_id, control_data in self.stig_data.items():
            # Apply RHEL version filtering if specified
            if rhel_version:
                control_version = control_data.get('rhel_version', '').lower()
                # Handle different version format variations
                if rhel_version.lower() not in control_version and rhel_version.replace('rhel', '') not in control_version:
                    continue  # Skip this control if version doesn't match
            
            score = self._calculate_control_relevance(control_id, control_data, query_lower, query_words)
            if score > 0:
                control_scores[control_id] = score

        # Sort by relevance score
        sorted_controls = sorted(control_scores.items(), key=lambda x: x[1], reverse=True)

        # Filter out very low relevance scores to improve quality
        min_score = 1.0  # Only return controls with meaningful matches
        filtered_controls = [(cid, score) for cid, score in sorted_controls if score >= min_score]

        results = []
        for control_id, score in filtered_controls[:n_results]:
            results.append({
                'control_id': control_id,
                'control_data': self.stig_data.get(control_id, {}),
                'score': round(score, 1)  # Round for cleaner display
            })
        return results

    def _enhance_query_terms(self, query):
        """Map common terms to STIG-related synonyms and concepts"""
        # Technical term mappings for better matching
        term_mappings = {
            'ssh': 'ssh secure shell openssh',
            'firewall': 'firewall iptables nftables netfilter',
            'selinux': 'selinux security enhanced linux mandatory access control',
            'password': 'password passwd authentication credential',
            'audit': 'audit auditd logging log',
            'encryption': 'encryption encrypt crypto cryptographic',
            'user': 'user account login username',
            'permission': 'permission permissions privilege access',
            'network': 'network networking tcp ip',
            'service': 'service daemon systemd',
            'file': 'file filesystem directory',
            'security': 'security secure',
            'configuration': 'configuration config configure',
            'policy': 'policy policies rule',
            'access': 'access control authorization',
            'system': 'system operating os',
            'kernel': 'kernel system',
            'root': 'root administrator admin superuser',
            'login': 'login logon authentication',
            'certificate': 'certificate cert x509 ssl tls',
            'key': 'key private public cryptographic',
            'compliance': 'compliance compliant requirement',
            'vulnerability': 'vulnerability vuln cve security',
            'patch': 'patch update upgrade',
            'backup': 'backup restore recovery',
            'monitoring': 'monitoring monitor surveillance',
            'lockout': 'lockout lock account disable',
            'timeout': 'timeout session idle',
            'banner': 'banner notice warning message',
            'integrity': 'integrity checksum hash verification'
        }
        
        enhanced_query = query
        for term, synonyms in term_mappings.items():
            if term in query:
                enhanced_query += ' ' + synonyms
        
        return enhanced_query

    def _calculate_control_relevance(self, control_id, control_data, query_lower, query_words):
        """Calculate relevance score with weighted field importance"""
        score = 0.0
        
        title = control_data.get('title', '').lower()
        description = control_data.get('description', '').lower()
        check = control_data.get('check', '').lower()
        fix = control_data.get('fix', '').lower()
        
        # Field importance weights
        TITLE_WEIGHT = 10.0      # Highest - title matches are most relevant
        DESCRIPTION_WEIGHT = 5.0  # High - descriptions are important
        CHECK_WEIGHT = 3.0       # Medium - check procedures are relevant
        FIX_WEIGHT = 2.0         # Lower - fix procedures are less searchable
        
        # 1. Exact phrase matches (highest relevance)
        if query_lower in title:
            score += 50.0 * TITLE_WEIGHT
        elif query_lower in description:
            score += 25.0 * DESCRIPTION_WEIGHT
        elif query_lower in check:
            score += 15.0 * CHECK_WEIGHT
        elif query_lower in fix:
            score += 10.0 * FIX_WEIGHT

        # 2. Multi-word phrase detection (important technical terms)
        tech_phrases = self._extract_tech_phrases(query_lower)
        for phrase in tech_phrases:
            if phrase in title:
                score += 30.0 * TITLE_WEIGHT
            elif phrase in description:
                score += 15.0 * DESCRIPTION_WEIGHT
            elif phrase in check:
                score += 10.0 * CHECK_WEIGHT
            elif phrase in fix:
                score += 5.0 * FIX_WEIGHT

        # 3. Individual word matches with diminishing returns
        title_words = set(re.findall(r'\b\w+\b', title))
        description_words = set(re.findall(r'\b\w+\b', description))
        check_words = set(re.findall(r'\b\w+\b', check))
        fix_words = set(re.findall(r'\b\w+\b', fix))
        
        matched_words = 0
        for word in query_words:
            word_score = 0
            
            if word in title_words:
                word_score += TITLE_WEIGHT
            if word in description_words:
                word_score += DESCRIPTION_WEIGHT
            if word in check_words:
                word_score += CHECK_WEIGHT
            if word in fix_words:
                word_score += FIX_WEIGHT
            
            if word_score > 0:
                matched_words += 1
                # Diminishing returns: fewer points for each additional word match
                word_multiplier = max(0.3, 1.0 - (matched_words * 0.1))
                score += word_score * word_multiplier

        # 4. Boost for high-severity controls (more important)
        severity = control_data.get('severity', '').lower()
        if severity == 'high':
            score *= 1.3
        elif severity == 'medium':
            score *= 1.1

        # 5. Penalty for very long controls (often less specific)
        total_text_length = len(title) + len(description) + len(check) + len(fix)
        if total_text_length > 5000:  # Very verbose controls
            score *= 0.8

        return score

    def _extract_tech_phrases(self, query):
        """Extract common technical phrases that should be matched as units"""
        tech_phrases = []
        
        # Common multi-word technical terms in STIG context
        phrase_patterns = [
            r'ssh\s+key[s]?',
            r'ssh\s+config\w*',
            r'password\s+policy',
            r'password\s+complexity',
            r'account\s+lockout',
            r'session\s+timeout',
            r'file\s+permission[s]?',
            r'access\s+control',
            r'audit\s+log[s]?',
            r'system\s+log[s]?',
            r'security\s+policy',
            r'login\s+banner',
            r'root\s+access',
            r'user\s+account[s]?',
            r'network\s+service[s]?',
            r'system\s+service[s]?',
            r'kernel\s+parameter[s]?',
            r'boot\s+loader',
            r'file\s+system',
            r'mount\s+point[s]?',
            r'certificate\s+authority',
            r'public\s+key',
            r'private\s+key',
            r'cryptographic\s+\w+',
            r'mandatory\s+access\s+control',
            r'discretionary\s+access\s+control',
        ]
        
        for pattern in phrase_patterns:
            matches = re.findall(pattern, query)
            tech_phrases.extend(matches)
        
        return tech_phrases

    def get_enhanced_response(self, query: str, search_results: List[Dict]) -> str:
        """Generate enhanced response using Llama 3.2"""
        
        # Check if AI is disabled for performance
        disable_ai = os.getenv("DISABLE_AI", "false").lower() == "true"
        if disable_ai:
            logger.info("AI disabled - using fallback text search only")
            return self._fallback_response(query, search_results)
            
        if not ollama_client.is_available():
            logger.warning("Ollama not available, using fallback response")
            return self._fallback_response(query, search_results)

        # Try AI with aggressive timeouts and fallback
        try:
            # Optional: Disable re-ranking for faster performance
            disable_reranking = os.getenv("DISABLE_LLAMA_RERANKING", "false").lower() == "true"
            
            # Use Llama to re-rank results for better relevance (unless disabled)
            if len(search_results) > 1 and not disable_reranking:
                try:
                    search_results = self._llama_rerank_results(query, search_results)
                except Exception as e:
                    logger.warning(f"Re-ranking failed, using original order: {e}")

            # Create context from search results (limit to top 2 for performance)
            top_results = search_results[:2]  # Reduced from 3 to prevent timeouts
            context_parts = []
            for result in top_results:
                control_id = result['control_id']
                control_data = result['control_data']

                # Aggressively truncate fields to prevent context overflow
                title = control_data.get('title', 'No title')[:150]
                description = control_data.get('description', 'No description')[:300]
                check = control_data.get('check', 'No check procedure')[:200]
                fix = control_data.get('fix', 'No fix procedure')[:200]

                context_parts.append(f"""
Control: {control_id}
Title: {title}
Description: {description}
Check: {check}
Fix: {fix}
""")

            context = "\n".join(context_parts)

            # Generate response using Llama with short timeout
            response = ollama_client.generate_response(query, context)
            
            # Check if response indicates timeout/error
            if "timed out" in response.lower() or "error:" in response.lower():
                logger.warning("AI response failed, falling back to text search")
                return self._fallback_response(query, search_results)
                
            return response
            
        except Exception as e:
            logger.error(f"AI response completely failed: {e}")
            return self._fallback_response(query, search_results)

    def _llama_rerank_results(self, query: str, search_results: List[Dict]) -> List[Dict]:
        """Use Llama to re-rank search results for better relevance"""
        try:
            # Skip re-ranking for models that don't handle it well
            problematic_models = ['phi3:mini', 'tinyllama', 'gemma2:2b']
            if any(model in self.model.lower() for model in problematic_models):
                logger.info(f"Skipping re-ranking for model {self.model} (known formatting issues)")
                return search_results
            
            # Create a prompt for Llama to evaluate relevance
            controls_summary = []
            for i, result in enumerate(search_results):
                control_id = result['control_id']
                title = result['control_data'].get('title', 'No title')
                controls_summary.append(f"{i+1}. {control_id}: {title}")
            
            rerank_prompt = f"""Rank these STIG controls by relevance to: "{query}"

{chr(10).join(controls_summary)}

IMPORTANT: Respond with ONLY the ranking numbers separated by commas.
Example: 2,1,4,3,5

Ranking:"""

            # Get Llama's ranking with shorter parameters to avoid issues
            payload = {
                "model": self.model,
                "prompt": rerank_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.0,  # Very deterministic
                    "top_p": 0.1,       # Very focused
                    "num_predict": 20,   # Very short response
                    "num_ctx": 512      # Small context
                }
            }
            
            response = requests.post(
                f"{ollama_client.base_url}/api/generate",
                json=payload,
                timeout=15  # Short timeout for re-ranking
            )
            
            if response.status_code != 200:
                logger.warning("Re-ranking request failed, keeping original order")
                return search_results
                
            ranking_response = response.json().get('response', '').strip()
            
            # Parse the ranking with better error handling
            try:
                # Try to extract just the numbers from the response
                numbers = re.findall(r'\b\d+\b', ranking_response)
                rankings = [int(x) for x in numbers]
                
                # Validate we have the right number of rankings
                if len(rankings) == len(search_results) and set(rankings) == set(range(1, len(search_results) + 1)):
                    # Reorder results based on Llama's ranking
                    reordered_results = []
                    for rank in rankings:
                        if 1 <= rank <= len(search_results):
                            result = search_results[rank - 1]
                            # Update score to reflect new ranking
                            result['score'] = len(search_results) - rankings.index(rank)
                            reordered_results.append(result)
                    logger.info(f"Successfully re-ranked {len(search_results)} results")
                    return reordered_results
                else:
                    logger.warning(f"Invalid ranking count or range: {rankings}, keeping original order")
                    return search_results
            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse ranking response '{ranking_response[:50]}...': {e}")
                return search_results
                
        except requests.exceptions.Timeout:
            logger.warning("Re-ranking timed out, keeping original order")
            return search_results
        except Exception as e:
            logger.warning(f"Re-ranking failed: {e}, keeping original order")
            return search_results

    def _fallback_response(self, query: str, search_results: List[Dict]) -> str:
        """Enhanced fallback response when Llama is not available"""
        if not search_results:
            return "No relevant STIG controls found for your query."

        # Check if AI is disabled vs. unavailable
        disable_ai = os.getenv("DISABLE_AI", "false").lower() == "true"
        
        if disable_ai:
            response = f"Found {len(search_results)} relevant STIG controls for: **{query}**\n\n"
            response += "*Using enhanced text search (AI disabled for performance)*\n\n"
        else:
            response = f"Found {len(search_results)} relevant STIG controls:\n\n"
        
        for i, result in enumerate(search_results, 1):
            control_id = result['control_id']
            control_data = result['control_data']
            title = control_data.get('title', 'No title')
            score = result.get('score', 0)
            
            # Add relevance indicator
            if score >= 50:
                relevance = "🟢 Highly Relevant"
            elif score >= 20:
                relevance = "🟡 Moderately Relevant"  
            elif score >= 5:
                relevance = "🔵 Somewhat Relevant"
            else:
                relevance = "⚪ Related"
                
            response += f"**{i}. {control_id}**: {title} ({relevance})\n"

        if not disable_ai:
            response += "\nNote: Llama AI is not available. Click 'View Full Details' for complete implementation guidance."
        else:
            response += "\n*💡 Tip: Click 'View Full Details' on any control for complete implementation steps.*"
            
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
        
        # Get available RHEL versions
        rhel_versions = set()
        for control_data in self.stig_data.values():
            version = control_data.get('rhel_version', '')
            if version and version.lower() != 'unknown':
                rhel_versions.add(version)
        
        return {
            "status": "loaded",
            "total_controls": len(self.stig_data),
            "search_method": "semantic_enhanced_search_with_llama3.2_reranking",
            "llama_available": llama_available,
            "ollama_url": OLLAMA_BASE_URL,
            "llama_model": LLAMA_MODEL,
            "data_source": data_source,
            "auto_load_path": auto_load_path if data_source == "auto-loaded" else None,
            "rhel_versions": sorted(list(rhel_versions))
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
        .form-row { display: flex; gap: 15px; margin: 10px 0; align-items: center; }
        .form-row .flex-1 { flex: 1; }
        .form-row .flex-auto { flex: 0 0 200px; }
        .form-row input, .form-row select { margin: 0; }
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
                
                <div class="form-row">
                    <div class="flex-1">
                        <input type="text" name="stig_id" placeholder="Specific STIG ID (optional)">
                    </div>
                    <div class="flex-auto">
                        <label for="rhel_version" style="font-weight: bold; margin-right: 8px;">RHEL Version:</label>
                        <select name="rhel_version" id="rhel_version">
                            <option value="">All Versions</option>
                            <option value="rhel8">RHEL 8</option>
                            <option value="rhel9">RHEL 9</option>
                        </select>
                    </div>
                </div>
                
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
                    const rhelVersions = data.rhel_versions || [];
                    
                    // Hide status section and upload section
                    status.style.display = 'none';
                    uploadSection.style.display = 'none';
                    
                    // Show loaded section and query section
                    loadedSection.style.display = 'block';
                    querySection.style.display = 'block';
                    exampleQuestions.style.display = 'block';
                    
                    // Update RHEL version dropdown with available versions
                    const versionSelect = document.getElementById('rhel_version');
                    if (versionSelect && rhelVersions.length > 0) {
                        // Clear existing options except "All Versions"
                        versionSelect.innerHTML = '<option value="">All Versions</option>';
                        
                        // Add available versions
                        rhelVersions.forEach(version => {
                            const option = document.createElement('option');
                            const displayVersion = version.toLowerCase().includes('rhel') ? version.toUpperCase() : `RHEL ${version.toUpperCase()}`;
                            option.value = version.toLowerCase();
                            option.textContent = displayVersion;
                            versionSelect.appendChild(option);
                        });
                    }
                    
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
                    
                    let versionInfo = '';
                    if (rhelVersions.length > 0) {
                        versionInfo = `<p><strong>🔢 RHEL Versions:</strong> ${rhelVersions.map(v => v.toUpperCase()).join(', ')}</p>`;
                    }
                    
                    loadedDetails.innerHTML = `
                        <h4>✅ STIG Data Ready</h4>
                        <p><strong>${controlCount}</strong> STIG controls loaded and indexed</p>
                        ${sourceInfo}
                        ${versionInfo}
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
            {% if rhel_version %}<strong>RHEL Version:</strong> {{ rhel_version.upper() }}<br>{% endif %}
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
    stig_id: Optional[str] = Form(None),
    rhel_version: Optional[str] = Form(None)
):
    if not stig_loader.data_loaded:
        answer = "<div style='background: #fff3cd; padding: 15px; border-radius: 8px;'><h4>⚠️ No Data</h4><p>Please upload STIG JSON data first.</p></div>"
        return templates.TemplateResponse("result.html", {
            "request": request, "question": question, "stig_id": stig_id, "rhel_version": rhel_version, "answer": answer
        })

    if stig_id:
        # Direct control lookup
        control_data = stig_loader.get_control_by_id(stig_id)
        if control_data:
            answer = format_control_response(control_id=stig_id, control_data=control_data)
        else:
            answer = f"<div style='background: #f8d7da; padding: 15px; border-radius: 8px;'><h4>❌ Not Found</h4><p>STIG control {stig_id} not found.</p></div>"
    else:
        # Enhanced AI-powered search with version filtering
        search_results = stig_loader.search_controls(question, n_results=5, rhel_version=rhel_version)
        if search_results:
            # Get AI-enhanced response
            ai_response = stig_loader.get_enhanced_response(question, search_results)
            answer = format_ai_response(question, ai_response, search_results, rhel_version)
        else:
            # No good matches found - provide helpful guidance
            version_text = f" for RHEL {rhel_version.upper()}" if rhel_version else ""
            answer = f"""<div style='background: #fff3cd; padding: 15px; border-radius: 8px; border-left: 5px solid #ffc107;'>
                <h4>🔍 No Highly Relevant Controls Found</h4>
                <p>No STIG controls were found with high relevance to your question{version_text}: <em>"{question}"</em></p>
                <p><strong>💡 Try these suggestions:</strong></p>
                <ul>
                    <li>Use more specific technical terms (e.g., "SSH configuration" instead of "remote access")</li>
                    <li>Include RHEL-specific terminology</li>
                    <li>Try different keywords or phrasing</li>
                    <li>Search for a specific STIG ID if you know it</li>
                    {"<li>Try selecting 'All Versions' to see controls from other RHEL versions</li>" if rhel_version else ""}
                </ul>
                <p><strong>Example queries that work well:</strong></p>
                <ul>
                    <li>"SSH key authentication setup"</li>
                    <li>"Password policy requirements"</li>
                    <li>"Audit logging configuration"</li>
                    <li>"SELinux enforcement settings"</li>
                </ul>
            </div>"""

    return templates.TemplateResponse("result.html", {
        "request": request, "question": question, "stig_id": stig_id, "rhel_version": rhel_version, "answer": answer
    })

def format_ai_response(question: str, ai_response: str, search_results: List[Dict], rhel_version: Optional[str] = None) -> str:
    """Format AI response with related controls"""

    # Add version filter info if applicable
    version_info = ""
    if rhel_version:
        version_display = rhel_version.upper() if rhel_version.startswith('rhel') else f"RHEL {rhel_version.upper()}"
        version_info = f" (filtered for {version_display})"

    answer = f"""
    <div style="background: #e3f2fd; padding: 20px; border-radius: 8px; margin: 15px 0; border-left: 5px solid #1976d2;">
        <h4>🤖 AI Analysis{version_info}</h4>
        <div style="white-space: pre-wrap; line-height: 1.6;">{ai_response}</div>
    </div>

    <h4>📋 Most Relevant STIG Controls{version_info}:</h4>
    """

    for i, result in enumerate(search_results, 1):
        control_id = result['control_id']
        control_data = result['control_data']
        title = control_data.get('title', 'No title')
        score = result.get('score', 0)
        control_version = control_data.get('rhel_version', 'Unknown')
        
        # Create relevance indicator
        if score >= 50:
            relevance_color = "#28a745"  # Green - highly relevant
            relevance_text = "Highly Relevant"
        elif score >= 20:
            relevance_color = "#ffc107"  # Yellow - moderately relevant  
            relevance_text = "Moderately Relevant"
        elif score >= 5:
            relevance_color = "#17a2b8"  # Blue - somewhat relevant
            relevance_text = "Somewhat Relevant"
        else:
            relevance_color = "#6c757d"  # Gray - low relevance
            relevance_text = "Related"

        # Truncate description more intelligently
        description = control_data.get('description', 'No description')
        if len(description) > 250:
            # Try to break at sentence end
            truncated = description[:250]
            last_period = truncated.rfind('.')
            if last_period > 150:  # Good break point
                description = description[:last_period + 1] + "..."
            else:
                description = truncated + "..."
        
        # Format version display
        version_display = control_version.upper() if control_version != 'Unknown' else control_version
        
        answer += f"""
        <div style="background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 3px solid #e53e3e;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <h5 style="margin: 0;">#{i} {control_id}: {title}</h5>
                <div style="display: flex; gap: 8px;">
                    <span style="background: {relevance_color}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 12px; font-weight: bold;">
                        {relevance_text}
                    </span>
                    <span style="background: #6c757d; color: white; padding: 3px 8px; border-radius: 12px; font-size: 12px; font-weight: bold;">
                        {version_display}
                    </span>
                </div>
            </div>
            <p style="margin: 10px 0; color: #666;">{description}</p>
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
