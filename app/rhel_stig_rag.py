import os
import re
import json
from typing import List, Dict, Optional
from pathlib import Path
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime

# Core libraries
import chromadb
from sentence_transformers import SentenceTransformer
from transformers import pipeline

# LangChain components
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.llms import HuggingFacePipeline
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate

# FastAPI for API
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

class STIGDocumentLoader:
    """Load and process STIG documents from various formats"""
    
    def __init__(self):
        self.supported_formats = ['.xml', '.json', '.txt']
    
    def load_stig_xml(self, file_path: str) -> List[Document]:
        """Load STIG from XML format (XCCDF)"""
        documents = []
        
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Parse XCCDF namespace
            ns = {'xccdf': 'http://checklists.nist.gov/xccdf/1.1'}
            
            for rule in root.findall('.//xccdf:Rule', ns):
                stig_id = rule.get('id', '')
                severity = rule.get('severity', 'medium')
                
                # Extract title
                title_elem = rule.find('xccdf:title', ns)
                title = title_elem.text if title_elem is not None else ''
                
                # Extract description
                desc_elem = rule.find('xccdf:description', ns)
                description = desc_elem.text if desc_elem is not None else ''
                
                # Extract check content
                check_elem = rule.find('.//xccdf:check-content', ns)
                check_content = check_elem.text if check_elem is not None else ''
                
                # Extract fix text
                fix_elem = rule.find('.//xccdf:fixtext', ns)
                fix_text = fix_elem.text if fix_elem is not None else ''
                
                # Create document
                content = f"""
STIG ID: {stig_id}
Title: {title}
Severity: {severity}

Description:
{description}

Check Procedure:
{check_content}

Fix/Implementation:
{fix_text}
                """.strip()
                
                # Extract version information
                rhel_version = None
                if 'RHEL-09' in stig_id or 'rhel-09' in stig_id.lower():
                    rhel_version = "9"
                elif 'RHEL-08' in stig_id or 'rhel-08' in stig_id.lower():
                    rhel_version = "8"
                
                metadata = {
                    'stig_id': stig_id,
                    'title': title,
                    'severity': severity,
                    'rhel_version': rhel_version,
                    'source': file_path,
                    'type': 'stig_control',
                    'priority': 1 if rhel_version == "9" else 2 if rhel_version == "8" else 3
                }
                
                documents.append(Document(page_content=content, metadata=metadata))
                
        except Exception as e:
            print(f"Error loading STIG XML: {e}")
            
        return documents
    
    def load_stig_json(self, file_path: str) -> List[Document]:
        """Load STIG from JSON format"""
        documents = []
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            if 'controls' in data:
                for control in data['controls']:
                    content = f"""
STIG ID: {control.get('id', '')}
Title: {control.get('title', '')}
Severity: {control.get('severity', 'medium')}

Description:
{control.get('description', '')}

Check Procedure:
{control.get('check', '')}

Fix/Implementation:
{control.get('fix', '')}
                    """.strip()
                    
                    metadata = {
                        'stig_id': control.get('id', ''),
                        'title': control.get('title', ''),
                        'severity': control.get('severity', 'medium'),
                        'rhel_version': control.get('version', ''),
                        'source': file_path,
                        'type': 'stig_control',
                        'priority': 1 if control.get('version') == "9" else 2 if control.get('version') == "8" else 3
                    }
                    
                    documents.append(Document(page_content=content, metadata=metadata))
                    
        except Exception as e:
            print(f"Error loading STIG JSON: {e}")
            
        return documents

class STIGPreprocessor:
    """Preprocess STIG documents for better RAG performance"""
    
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", ". ", " "]
        )
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters that might interfere
        text = re.sub(r'[^\w\s\-\.\,\:\;\(\)]', ' ', text)
        
        # Normalize control references
        text = re.sub(r'RHEL-\d+-\d+', lambda m: m.group().upper(), text)
        
        return text.strip()
    
    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        """Split documents into smaller chunks while preserving metadata"""
        chunked_docs = []
        
        for doc in documents:
            cleaned_content = self.clean_text(doc.page_content)
            chunks = self.text_splitter.split_text(cleaned_content)
            
            for i, chunk in enumerate(chunks):
                chunk_metadata = doc.metadata.copy()
                chunk_metadata['chunk_id'] = i
                chunk_metadata['total_chunks'] = len(chunks)
                
                chunked_docs.append(Document(
                    page_content=chunk,
                    metadata=chunk_metadata
                ))
        
        return chunked_docs

class STIGVectorStore:
    """Manage vector storage for STIG documents"""
    
    def __init__(self, persist_directory: str = "./stig_chroma_db"):
        self.persist_directory = persist_directory
        
        # Initialize embeddings model
        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'}
        )
        
        # Initialize or load vector store
        self.vectorstore = Chroma(
            persist_directory=persist_directory,
            embedding_function=self.embeddings
        )
    
    def add_documents(self, documents: List[Document]):
        """Add documents to the vector store"""
        self.vectorstore.add_documents(documents)
        self.vectorstore.persist()
    
    def search(self, query: str, k: int = 5, filter_dict: Optional[Dict] = None, prefer_rhel9: bool = True) -> List[Document]:
        """Search for relevant documents with RHEL 9 prioritization"""
        if prefer_rhel9:
            # First try to get RHEL 9 results
            rhel9_results = self.vectorstore.similarity_search(
                query, k=k//2 + 1, filter={"rhel_version": "9"}
            )
            
            # Then get remaining results (could include RHEL 8)
            remaining_k = k - len(rhel9_results)
            if remaining_k > 0:
                other_results = self.vectorstore.similarity_search(
                    query, k=remaining_k, filter={"rhel_version": {"$ne": "9"}}
                )
                results = rhel9_results + other_results
            else:
                results = rhel9_results
            
            return results[:k]
        
        # Standard search if not preferring RHEL 9
        if filter_dict:
            return self.vectorstore.similarity_search(
                query, k=k, filter=filter_dict
            )
        return self.vectorstore.similarity_search(query, k=k)
    
    def search_by_stig_id(self, stig_id: str) -> List[Document]:
        """Search for specific STIG control by ID"""
        return self.vectorstore.similarity_search(
            stig_id,
            k=5,
            filter={"stig_id": {"$regex": f".*{stig_id}.*"}}
        )

class STIGRAGSystem:
    """Main RAG system for STIG assistance"""
    
    def __init__(self, vector_store: STIGVectorStore):
        self.vector_store = vector_store
        
        # Initialize LLM
        self.llm = HuggingFacePipeline.from_model_id(
            model_id="microsoft/DialoGPT-medium",
            task="text-generation",
            model_kwargs={"temperature": 0.1, "max_length": 2048}
        )
        
        # Create custom prompt template optimized for RHEL 9
        self.prompt_template = PromptTemplate(
            input_variables=["context", "question"],
            template="""You are an expert RHEL security consultant specializing in STIG compliance for RHEL 9 (primarily) and RHEL 8 (secondarily). 
Use the following STIG documentation to answer the question. Prioritize RHEL 9 guidance when available.

Context from STIG documentation:
{context}

Question: {question}

Answer: Provide a detailed, step-by-step response that includes:
1. The relevant STIG control(s) - prioritizing RHEL 9 controls
2. RHEL version-specific implementation steps
3. Verification procedures 
4. Key differences between RHEL 9 and RHEL 8 if applicable
5. Any important considerations or warnings

Focus on RHEL 9 best practices while noting any RHEL 8 differences.

Response:"""
        )
        
        # Create retrieval QA chain
        self.qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.vector_store.vectorstore.as_retriever(search_kwargs={"k": 5}),
            chain_type_kwargs={"prompt": self.prompt_template},
            return_source_documents=True
        )
    
    def query(self, question: str, stig_id: Optional[str] = None, rhel_version: Optional[str] = None) -> Dict:
        """Query the RAG system with RHEL version prioritization"""
        try:
            # Determine preferred RHEL version (default to 9)
            if rhel_version:
                prefer_version = rhel_version
            elif stig_id and "RHEL-08" in stig_id:
                prefer_version = "8"
            elif stig_id and "RHEL-09" in stig_id:
                prefer_version = "9"
            else:
                prefer_version = "9"  # Default to RHEL 9
            
            if stig_id:
                # Search for specific STIG ID first
                specific_docs = self.vector_store.search_by_stig_id(stig_id)
                if specific_docs:
                    context = "\n\n".join([doc.page_content for doc in specific_docs[:3]])
                    enhanced_question = f"Question about STIG {stig_id} for RHEL {prefer_version}: {question}"
                else:
                    enhanced_question = f"Question about RHEL {prefer_version}: {question}"
            else:
                enhanced_question = f"Question about RHEL {prefer_version}: {question}"
                
                # Use version-aware search
                if prefer_version == "9":
                    # Prioritize RHEL 9 results
                    docs = self.vector_store.search(enhanced_question, k=5, prefer_rhel9=True)
                else:
                    # Filter for specific version
                    docs = self.vector_store.search(
                        enhanced_question, k=5, 
                        filter_dict={"rhel_version": prefer_version}
                    )
            
            result = self.qa_chain({"query": enhanced_question})
            
            return {
                "answer": result["result"],
                "rhel_version_focus": prefer_version,
                "source_documents": [
                    {
                        "content": doc.page_content,
                        "metadata": doc.metadata
                    } for doc in result.get("source_documents", [])
                ],
                "query": enhanced_question
            }
        except Exception as e:
            return {
                "answer": f"Error processing query: {str(e)}",
                "rhel_version_focus": prefer_version if 'prefer_version' in locals() else "9",
                "source_documents": [],
                "query": question
            }

# FastAPI Application
app = FastAPI(title="RHEL STIG RAG Assistant", version="1.0.0")

# Global variables (in production, use proper dependency injection)
stig_loader = STIGDocumentLoader()
stig_preprocessor = STIGPreprocessor()
vector_store = STIGVectorStore()
rag_system = STIGRAGSystem(vector_store)

# Pydantic models for API
class QueryRequest(BaseModel):
    question: str
    stig_id: Optional[str] = None
    rhel_version: Optional[str] = None  # "8" or "9"

class QueryResponse(BaseModel):
    answer: str
    rhel_version_focus: str
    sources: List[Dict]
    query: str

@app.post("/query", response_model=QueryResponse)
async def query_stig(request: QueryRequest):
    """Query the STIG RAG system with RHEL version prioritization"""
    result = rag_system.query(request.question, request.stig_id, request.rhel_version)
    
    return QueryResponse(
        answer=result["answer"],
        rhel_version_focus=result["rhel_version_focus"],
        sources=result["source_documents"],
        query=result["query"]
    )

@app.post("/load-stig")
async def load_stig_document(file_path: str):
    """Load a STIG document into the system"""
    try:
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        # Determine file type and load
        if file_path.endswith('.xml'):
            documents = stig_loader.load_stig_xml(file_path)
        elif file_path.endswith('.json'):
            documents = stig_loader.load_stig_json(file_path)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format")
        
        # Preprocess and add to vector store
        chunked_docs = stig_preprocessor.chunk_documents(documents)
        vector_store.add_documents(chunked_docs)
        
        return {
            "message": f"Successfully loaded {len(documents)} STIG controls",
            "chunks_created": len(chunked_docs)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/search/{stig_id}")
async def search_stig_by_id(stig_id: str):
    """Search for specific STIG control by ID"""
    try:
        documents = vector_store.search_by_stig_id(stig_id)
        
        return {
            "stig_id": stig_id,
            "results": [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata
                } for doc in documents
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    # Example usage
    print("RHEL STIG RAG System")
    print("===================")
    
    # Load sample STIG data (you'll need to provide actual STIG files)
    # documents = stig_loader.load_stig_xml("path/to/rhel-stig.xml")
    # chunked_docs = stig_preprocessor.chunk_documents(documents)
    # vector_store.add_documents(chunked_docs)
    
    # Start the API server
    uvicorn.run(app, host="0.0.0.0", port=8000)