#!/usr/bin/env python3
"""
Fix the exact search results pattern to add View Full Details links
"""

with open('rhel_stig_rag.py', 'r') as f:
    content = f.read()

# The exact pattern we need to find and replace
old_pattern = '''                answer += f"""
                <div style="background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 3px solid #e53e3e;">
                    <h5>#{i} {control_id}: {title} (Score: {score})</h5>
                    <p>{control_data.get('description', 'No description')[:200]}...</p>
                </div>
                """'''

# New pattern with View Full Details link
new_pattern = '''                answer += f"""
                <div style="background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 3px solid #e53e3e;">
                    <h5>#{i} {control_id}: {title} (Score: {score})</h5>
                    <p>{control_data.get('description', 'No description')[:200]}...</p>
                    <div style="margin-top: 15px; padding: 12px; background: #e3f2fd; border-radius: 5px; text-align: center; border: 2px solid #1976d2;">
                        <a href="/control/{control_id}" style="color: #1976d2; text-decoration: none; font-weight: bold; font-size: 16px;">
                            📋 View Full Details & Implementation Steps →
                        </a>
                    </div>
                </div>
                """'''

if old_pattern in content:
    content = content.replace(old_pattern, new_pattern)
    
    with open('rhel_stig_rag.py', 'w') as f:
        f.write(content)
    
    print("✅ Successfully added View Full Details links!")
else:
    print("❌ Exact pattern not found. Let's try a simpler approach...")
    
    # Look for the specific line we need to modify
    lines = content.split('\n')
    new_lines = []
    
    for i, line in enumerate(lines):
        new_lines.append(line)
        
        # Look for the description line followed by </div>
        if 'control_data.get(\'description\', \'No description\')[:200]}...</p>' in line:
            # Check if next non-empty line is </div>
            j = i + 1
            while j < len(lines) and lines[j].strip() == '':
                new_lines.append(lines[j])
                j += 1
            
            if j < len(lines) and '</div>' in lines[j]:
                # Insert the View Full Details link before the closing div
                new_lines.append('                    <div style="margin-top: 15px; padding: 12px; background: #e3f2fd; border-radius: 5px; text-align: center; border: 2px solid #1976d2;">')
                new_lines.append('                        <a href="/control/{control_id}" style="color: #1976d2; text-decoration: none; font-weight: bold; font-size: 16px;">')
                new_lines.append('                            📋 View Full Details & Implementation Steps →')
                new_lines.append('                        </a>')
                new_lines.append('                    </div>')
    
    # Write the updated content
    with open('rhel_stig_rag.py', 'w') as f:
        f.write('\n'.join(new_lines))
    
    print("✅ Applied View Full Details fix using line-by-line approach")
