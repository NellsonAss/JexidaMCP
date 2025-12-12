#!/usr/bin/env python3
"""Register the unifi_list_clients tool in the database."""

import os
import sys

# Setup paths
os.chdir('/opt/jexida-mcp/jexida_dashboard')
sys.path.insert(0, '/opt/jexida-mcp/jexida_dashboard')
sys.path.insert(0, '/opt/jexida-mcp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jexida_dashboard.settings')

import django
django.setup()

from mcp_tools_core.models import Tool

tool, created = Tool.objects.update_or_create(
    name='unifi_list_clients',
    defaults={
        'description': 'List all connected client devices (WiFi and wired) from the UniFi controller',
        'handler_path': 'mcp_tools_core.tools.unifi.clients.unifi_list_clients',
        'tags': 'unifi,network,clients,wifi',
        'input_schema': {
            'type': 'object',
            'properties': {
                'site_id': {'type': 'string', 'description': 'UniFi site ID'},
                'wifi_only': {'type': 'boolean', 'default': False, 'description': 'Only return WiFi clients'}
            },
            'required': []
        },
        'is_active': True
    }
)
print(f'Tool {"created" if created else "updated"}: {tool.name}')
