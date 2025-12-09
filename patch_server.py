#!/usr/bin/env python3
import sys

file_path = "/opt/jexida-mcp/server.py"

with open(file_path, 'r') as f:
    lines = f.readlines()

# Find line 193 (index 192) and replace it
for i, line in enumerate(lines):
    if i == 192:  # Line 193 (0-indexed)
        if 'request.session.get("authenticated"' in line:
            indent = len(line) - len(line.lstrip())
            # Replace the problematic line
            lines[i] = ' ' * indent + 'if "session" not in request.scope:\n'
            lines.insert(i+1, ' ' * indent + '    is_authed = False\n')
            lines.insert(i+2, ' ' * indent + 'else:\n')
            lines.insert(i+3, ' ' * indent + '    session = request.scope.get("session", {})\n')
            lines.insert(i+4, ' ' * indent + '    is_authed = session.get("authenticated", False)\n')
            lines.insert(i+5, '\n')
            lines.insert(i+6, ' ' * indent + 'if not is_authed:\n')
            print(f"Found and fixed line {i+1}")
            break

with open(file_path, 'w') as f:
    f.writelines(lines)

print("File patched successfully!")




