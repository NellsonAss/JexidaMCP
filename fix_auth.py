#!/usr/bin/env python3
"""Fix auth middleware in server.py"""

import re

file_path = "/opt/jexida-mcp/server.py"

with open(file_path, 'r') as f:
    content = f.read()

# Find and replace the problematic line
old_pattern = r'        # Check if authenticated \(safely handle missing session\)\n        # Must check if session is in scope first, as SessionMiddleware may not have run yet\n        if "session" not in request\.scope:\n            is_authed = False\n        else:\n            try:\n                is_authed = request\.session\.get\("authenticated", False\)\n            except Exception:\n                is_authed = False'
new_code = '''        # Check if authenticated (safely handle missing session)
        # Must check if session is in scope first, as SessionMiddleware may not have run yet
        if "session" not in request.scope:
            is_authed = False
        else:
            try:
                is_authed = request.session.get("authenticated", False)
            except Exception:
                is_authed = False'''

# Also try simpler pattern
old_simple = r'if not request\.session\.get\("authenticated", False\):'
new_simple = '''if "session" not in request.scope:
            is_authed = False
        else:
            try:
                is_authed = request.session.get("authenticated", False)
            except Exception:
                is_authed = False
        
        if not is_authed:'''

if old_simple in content:
    content = re.sub(old_simple, new_simple, content)
    with open(file_path, 'w') as f:
        f.write(content)
    print("Fixed!")
else:
    print("Pattern not found, checking current state...")
    # Find the line
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'request.session.get("authenticated"' in line:
            print(f"Found at line {i+1}: {line}")
            # Replace it
            indent = len(line) - len(line.lstrip())
            lines[i] = ' ' * indent + 'if "session" not in request.scope:'
            lines.insert(i+1, ' ' * indent + '    is_authed = False')
            lines.insert(i+2, ' ' * indent + 'else:')
            lines.insert(i+3, ' ' * indent + '    try:')
            lines.insert(i+4, ' ' * indent + '        is_authed = request.session.get("authenticated", False)')
            lines.insert(i+5, ' ' * indent + '    except Exception:')
            lines.insert(i+6, ' ' * indent + '        is_authed = False')
            lines.insert(i+7, '')
            lines.insert(i+8, ' ' * indent + 'if not is_authed:')
            break
    
    with open(file_path, 'w') as f:
        f.write('\n'.join(lines))
    print("Fixed with line-by-line replacement!")






