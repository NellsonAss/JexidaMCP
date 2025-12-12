#!/usr/bin/env python3
import re

file_path = "/opt/jexida-mcp/server.py"

with open(file_path, 'r') as f:
    content = f.read()

# Find the exact line and replace it
# Look for: "        if not request.session.get("authenticated", False):"
old_line = r'        if not request\.session\.get\("authenticated", False\):'
new_code = '''        if "session" not in request.scope:
            is_authed = False
        else:
            session = request.scope.get("session", {})
            is_authed = session.get("authenticated", False)
        
        if not is_authed:'''

if re.search(old_line, content):
    content = re.sub(old_line, new_code, content)
    with open(file_path, 'w') as f:
        f.write(content)
    print("SUCCESS: File patched!")
    # Verify
    with open(file_path, 'r') as f:
        lines = f.readlines()
        for i, line in enumerate(lines[192:200], 193):
            print(f"{i}: {line.rstrip()}")
else:
    print("ERROR: Pattern not found!")
    # Show what's actually there
    lines = content.split('\n')
    for i, line in enumerate(lines[190:200], 191):
        if 'session' in line.lower() or 'authenticated' in line.lower():
            print(f"{i}: {line}")






