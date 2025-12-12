#!/usr/bin/env python3
"""Register JexidaDroid2 worker node in the database.

Run this on the MCP server.
"""

import os
import sys
import django

# Add the jexida_dashboard to the path
sys.path.insert(0, '/opt/jexida-mcp/jexida_dashboard')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jexida_dashboard.settings')

django.setup()

from mcp_tools_core.models import WorkerNode

# Create or update the JexidaDroid2 worker node
node, created = WorkerNode.objects.update_or_create(
    name='JexidaDroid2',
    defaults={
        'host': '192.168.1.254',
        'user': 'jexida',
        'ssh_port': 22,
        'tags': 'ubuntu,worker',
        'is_active': True,
    }
)

action = "Created" if created else "Updated"
print(f"{action} worker node: {node.name} ({node.host})")
print(f"  User: {node.user}")
print(f"  Port: {node.ssh_port}")
print(f"  Tags: {node.tags}")
print(f"  Active: {node.is_active}")

