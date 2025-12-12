#!/usr/bin/env python3
"""Register the append_mcp_timeseries tool."""
import os, sys
os.chdir('/opt/jexida-mcp/jexida_dashboard')
sys.path.insert(0, '/opt/jexida-mcp/jexida_dashboard')
sys.path.insert(0, '/opt/jexida-mcp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jexida_dashboard.settings')
import django
django.setup()
from mcp_tools_core.models import Tool

tool, created = Tool.objects.update_or_create(
    name='append_mcp_timeseries',
    defaults={
        'description': 'Append a data point to a timeseries for tracking changes over time. Auto-adds timestamp and maintains max entry limit.',
        'handler_path': 'mcp_tools_core.tools.admin.knowledge.append_mcp_timeseries',
        'tags': 'admin,mcp,knowledge,timeseries',
        'input_schema': {
            'type': 'object',
            'properties': {
                'key': {'type': 'string', 'description': 'Timeseries key (e.g., unifi.clients.history)'},
                'data': {'type': 'object', 'description': 'Data point to append'},
                'max_entries': {'type': 'integer', 'default': 100, 'description': 'Max entries to keep'},
                'source': {'type': 'string', 'default': 'timeseries'}
            },
            'required': ['key', 'data']
        },
        'is_active': True
    }
)
print(f'Tool {"created" if created else "updated"}: append_mcp_timeseries')

