#!/usr/bin/env python3
"""
Client script to interact with the RHEL STIG RAG system
"""

import requests
import json
import argparse
from pathlib import Path

class STIGClient:
    """Client for interacting with STIG RAG system"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def query(self, question: str, stig_id: str = None, rhel_version: str = None) -> dict:
        """Query the STIG system with RHEL version preference"""
        payload = {"question": question}
        if stig_id:
            payload["stig_id"] = stig_id
        if rhel_version:
            payload["rhel_version"] = rhel_version
        
        try:
            response = self.session.post(
                f"{self.base_url}/query",
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {"error": str(e)}
    
    def load_stig(self, file_path: str) -> dict:
        """Load a STIG document"""
        try:
            # Convert to absolute path
            abs_path = Path(file_path).resolve()
            
            response = self.session.post(
                f"{self.base_url}/load-stig",
                params={"file_path": str(abs_path)}
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {"error": str(e)}
    
    def search_by_id(self, stig_id: str) -> dict:
        """Search for specific STIG by ID"""
        try:
            response = self.session.get(
                f"{self.base_url}/search/{stig_id}"
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {"error": str(e)}
    
    def health_check(self) -> dict:
        """Check system health"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {"error": str(e)}

def main():
    parser = argparse.ArgumentParser(description="RHEL STIG RAG Client")
    parser.add_argument("--url", default="http://localhost:8000", 
                      help="Base URL of the STIG RAG service")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Query command
    query_parser = subparsers.add_parser("query", help="Query the STIG system")
    query_parser.add_argument("question", help="Question to ask")
    query_parser.add_argument("--stig-id", help="Specific STIG ID to focus on")
    query_parser.add_argument("--rhel-version", choices=["8", "9"], 
                            help="Prefer RHEL version (8 or 9)", default="9")
    
    # Load command
    load_parser = subparsers.add_parser("load", help="Load STIG document")
    load_parser.add_argument("file_path", help="Path to STIG file")
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Search by STIG ID")
    search_parser.add_argument("stig_id", help="STIG ID to search for")
    
    # Health command
    health_parser = subparsers.add_parser("health", help="Check system health")
    
    # Interactive command
    interactive_parser = subparsers.add_parser("interactive", help="Interactive mode")
    
    args = parser.parse_args()
    
    client = STIGClient(args.url)
    
    if args.command == "query":
        result = client.query(args.question, args.stig_id, args.rhel_version)
        print_query_result(result)
    
    elif args.command == "load":
        result = client.load_stig(args.file_path)
        print_json_result(result)
    
    elif args.command == "search":
        result = client.search_by_id(args.stig_id)
        print_search_result(result)
    
    elif args.command == "health":
        result = client.health_check()
        print_json_result(result)
    
    elif args.command == "interactive":
        interactive_mode(client)
    
    else:
        parser.print_help()

def print_query_result(result: dict):
    """Print formatted query result"""
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        return
    
    print("🔍 Query Results")
    print("=" * 50)
    print(f"Question: {result.get('query', 'N/A')}")
    print(f"RHEL Version Focus: {result.get('rhel_version_focus', 'N/A')}")
    print("\n💡 Answer:")
    print("-" * 30)
    print(result.get('answer', 'No answer provided'))
    
    sources = result.get('sources', [])
    if sources:
        print(f"\n📚 Sources ({len(sources)} found):")
        print("-" * 30)
        for i, source in enumerate(sources[:3], 1):  # Show top 3 sources
            metadata = source.get('metadata', {})
            print(f"{i}. STIG ID: {metadata.get('stig_id', 'N/A')}")
            print(f"   Severity: {metadata.get('severity', 'N/A')}")
            print(f"   Title: {metadata.get('title', 'N/A')}")
            print()

def print_search_result(result: dict):
    """Print formatted search result"""
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        return
    
    print(f"🔍 Search Results for STIG ID: {result.get('stig_id', 'N/A')}")
    print("=" * 50)
    
    results = result.get('results', [])
    if not results:
        print("No results found.")
        return
    
    for i, item in enumerate(results, 1):
        metadata = item.get('metadata', {})
        print(f"{i}. {metadata.get('title', 'N/A')}")
        print(f"   Severity: {metadata.get('severity', 'N/A')}")
        print(f"   Type: {metadata.get('type', 'N/A')}")
        content = item.get('content', '')
        # Show first 200 characters
        print(f"   Preview: {content[:200]}...")
        print()

def print_json_result(result: dict):
    """Print JSON result in a formatted way"""
    print(json.dumps(result, indent=2))

def interactive_mode(client: STIGClient):
    """Interactive mode for querying the system"""
    print("🚀 RHEL STIG RAG Interactive Mode (RHEL 9 Priority)")
    print("=" * 50)
    print("Commands:")
    print("  query <question>               - Ask a question (defaults to RHEL 9)")
    print("  query9 <question>              - Ask RHEL 9 specific question")
    print("  query8 <question>              - Ask RHEL 8 specific question")
    print("  search <stig_id>               - Search by STIG ID") 
    print("  load <file_path>               - Load STIG file")
    print("  health                         - Check system health")
    print("  help                           - Show this help")
    print("  exit                           - Exit interactive mode")
    print()
    
    while True:
        try:
            user_input = input("STIG> ").strip()
            
            if not user_input:
                continue
            
            parts = user_input.split(' ', 1)
            command = parts[0].lower()
            
            if command == "exit":
                break
            elif command == "help":
                print("Available commands: query, query9, query8, search, load, health, help, exit")
            elif command == "health":
                result = client.health_check()
                print_json_result(result)
            elif command in ["query", "query9", "query8"] and len(parts) > 1:
                question = parts[1]
                # Determine RHEL version
                if command == "query9":
                    rhel_version = "9"
                elif command == "query8":
                    rhel_version = "8"
                else:
                    rhel_version = "9"  # Default to RHEL 9
                
                # Check if question includes STIG ID
                stig_id = None
                if "RHEL-" in question:
                    import re
                    match = re.search(r'RHEL-\d+-\d+', question)
                    if match:
                        stig_id = match.group()
                
                result = client.query(question, stig_id, rhel_version)
                print_query_result(result)
            elif command == "search" and len(parts) > 1:
                stig_id = parts[1]
                result = client.search_by_id(stig_id)
                print_search_result(result)
            elif command == "load" and len(parts) > 1:
                file_path = parts[1]
                result = client.load_stig(file_path)
                print_json_result(result)
            else:
                print("Invalid command. Type 'help' for available commands.")
                
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()