# Create an updated version with full details links
cat > fix_search_results.py << 'EOF'
#!/usr/bin/env python3
"""
Fix the search results to include full details links
"""

# Read the current app file
with open('stig_app_no_chromadb.py', 'r') as f:
    content = f.read()

# Update the format_search_response function to include full details links
old_format_function = '''def format_search_response(search_results: List[Dict], question: str, rhel_version: str) -> str:
    """Format response for search results"""
    response = f"""
    <div style="background: #e8f5e8; padding: 25px; border-radius: 12px; border-left: 5px solid #4caf50;">
        <h4>🔍 STIG Controls Found ({len(search_results)} matches)</h4>
        <p><strong>Your Question:</strong> {question}</p>
        <p><em>Using optimized text search for fast, reliable results</em></p>
    </div>
    """
    
    for i, result in enumerate(search_results, 1):
        control_id = result['control_id']
        control_data = result['control_data']
        title = control_data.get('title', 'No title available')
        description = control_data.get('description', '')[:300] + '...' if len(control_data.get('description', '')) > 300 else control_data.get('description', '')
        severity = control_data.get('severity', 'Unknown')
        score = result.get('score', 0)
        
        response += f"""
        <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 15px 0; border-left: 3px solid #e53e3e;">
            <h5>#{i} {control_id}: {title} <span style="color: #666; font-size: 14px;">(Score: {score})</span></h5>
            <p><strong>Severity:</strong> <span style="color: #e53e3e;">{severity}</span></p>
            <p>{description}</p>
        </div>
        """
    
    return response'''

new_format_function = '''def format_search_response(search_results: List[Dict], question: str, rhel_version: str) -> str:
    """Format response for search results with full details links"""
    response = f"""
    <div style="background: #e8f5e8; padding: 25px; border-radius: 12px; border-left: 5px solid #4caf50;">
        <h4>🔍 STIG Controls Found ({len(search_results)} matches)</h4>
        <p><strong>Your Question:</strong> {question}</p>
        <p><em>Click "View Full Details" for complete implementation guidance</em></p>
    </div>
    """
    
    for i, result in enumerate(search_results, 1):
        control_id = result['control_id']
        control_data = result['control_data']
        title = control_data.get('title', 'No title available')
        description = control_data.get('description', '')[:200] + '...' if len(control_data.get('description', '')) > 200 else control_data.get('description', '')
        severity = control_data.get('severity', 'Unknown')
        score = result.get('score', 0)
        
        response += f"""
        <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 15px 0; border-left: 3px solid #e53e3e;">
            <h5>#{i} {control_id}: {title} <span style="color: #666; font-size: 14px;">(Score: {score})</span></h5>
            <p><strong>Severity:</strong> <span style="color: #e53e3e;">{severity}</span></p>
            <p>{description}</p>
            <div style="margin-top: 15px; padding: 10px; background: #e3f2fd; border-radius: 5px;">
                <a href="/control/{control_id}" style="color: #1976d2; text-decoration: none; font-weight: bold; font-size: 16px;">
                    📋 View Full Details & Implementation Steps →
                </a>
            </div>
        </div>
        """
    
    return response'''

# Replace the function
content = content.replace(old_format_function, new_format_function, 1)

# Add a new endpoint for full control details
new_endpoint = '''
@app.get("/control/{stig_id}", response_class=HTMLResponse)
async def view_control_details(request: Request, stig_id: str):
    """View complete control details"""
    control_data = stig_loader.get_control_by_id(stig_id)
    
    if not control_data:
        # Show error page
        error_html = f"""
        <div style="max-width: 800px; margin: 50px auto; padding: 30px; background: white; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <h1 style="color: #e53e3e;">❌ Control Not Found</h1>
            <p>STIG control <code>{stig_id}</code> was not found in the loaded data.</p>
            <a href="/" style="color: #1976d2; text-decoration: none; font-weight: bold;">← Back to Search</a>
        </div>
        """
        return HTMLResponse(content=error_html)
    
    # Format complete control details
    title = control_data.get('title', 'No title available')
    description = control_data.get('description', 'No description available')
    check = control_data.get('check', 'No check procedure available')
    fix = control_data.get('fix', 'No fix procedure available')
    severity = control_data.get('severity', 'Unknown')
    rhel_version = control_data.get('rhel_version', 'Unknown')
    
    details_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{stig_id} - STIG Control Details</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
            .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            .header {{ background: #e53e3e; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
            .section {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 5px solid #007bff; }}
            .metadata {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
            .meta-item {{ background: #e8f5e8; padding: 15px; border-radius: 6px; text-align: center; }}
            .back-link {{ display: inline-block; background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-bottom: 20px; }}
            .back-link:hover {{ background: #0056b3; }}
            pre {{ background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 5px; overflow-x: auto; white-space: pre-wrap; }}
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/" class="back-link">← Back to Search</a>
            
            <div class="header">
                <h1>🛡️ {stig_id}</h1>
                <h2>{title}</h2>
            </div>
            
            <div class="metadata">
                <div class="meta-item">
                    <strong>Severity</strong><br>
                    <span style="color: #e53e3e; font-size: 18px; font-weight: bold;">{severity.upper()}</span>
                </div>
                <div class="meta-item">
                    <strong>RHEL Version</strong><br>
                    <span style="color: #e53e3e; font-size: 18px; font-weight: bold;">RHEL {rhel_version}</span>
                </div>
            </div>
            
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
            
            <div style="text-align: center; margin-top: 30px; padding: 20px; background: #e8f5e8; border-radius: 8px;">
                <p><strong>💡 Need help with implementation?</strong> Use the main search to find related controls or ask specific questions about this requirement.</p>
                <a href="/" style="color: #e53e3e; text-decoration: none; font-weight: bold; font-size: 16px;">Ask Another Question →</a>
            </div>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=details_html)
'''

# Add the new endpoint before the health check endpoint
health_endpoint_pos = content.find('@app.get("/health")')
if health_endpoint_pos > 0:
    content = content[:health_endpoint_pos] + new_endpoint + '\n\n' + content[health_endpoint_pos:]

# Write the updated file
with open('stig_app_no_chromadb_fixed.py', 'w') as f:
    f.write(content)

print("✅ Created fixed version: stig_app_no_chromadb_fixed.py")
EOF

# Run the fix
#python3 fix_search_results.py

# Replace the current app with the fixed version
#cp stig_app_no_chromadb_fixed.py rhel_stig_rag.py

# Restart the container
#podman restart stig-rag-textsearch
