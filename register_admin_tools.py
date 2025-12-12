#!/usr/bin/env python3
"""Register the admin tools in the database."""

import os
import sys

# Setup paths
os.chdir('/opt/jexida-mcp/jexida_dashboard')
sys.path.insert(0, '/opt/jexida-mcp/jexida_dashboard')
sys.path.insert(0, '/opt/jexida-mcp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jexida_dashboard.settings')

import django
django.setup()

from mcp_tools_core.models import Tool, Fact

# Register register_mcp_tool
tool1, created1 = Tool.objects.update_or_create(
    name='register_mcp_tool',
    defaults={
        'description': 'Register a new MCP tool in the database. Use this to add new tools without SSH access (code must be deployed first).',
        'handler_path': 'mcp_tools_core.tools.admin.register_tool.register_mcp_tool',
        'tags': 'admin,mcp,tools',
        'input_schema': {
            'type': 'object',
            'properties': {
                'name': {'type': 'string', 'description': 'Unique tool name'},
                'description': {'type': 'string', 'description': 'Tool description'},
                'handler_path': {'type': 'string', 'description': 'Python import path to handler'},
                'tags': {'type': 'string', 'description': 'Comma-separated tags'},
                'input_schema': {'type': 'object', 'description': 'JSON Schema for input'},
                'is_active': {'type': 'boolean', 'default': True},
                'restart_service': {'type': 'boolean', 'default': False}
            },
            'required': ['name', 'description', 'handler_path']
        },
        'is_active': True
    }
)
print(f'Tool {"created" if created1 else "updated"}: register_mcp_tool')

# Register get_mcp_knowledge
tool2, created2 = Tool.objects.update_or_create(
    name='get_mcp_knowledge',
    defaults={
        'description': 'Retrieve knowledge from the MCP knowledge store. Use to look up stored facts, best practices, and learned information.',
        'handler_path': 'mcp_tools_core.tools.admin.knowledge.get_mcp_knowledge',
        'tags': 'admin,mcp,knowledge,facts',
        'input_schema': {
            'type': 'object',
            'properties': {
                'key': {'type': 'string', 'description': 'Specific key to retrieve'},
                'source': {'type': 'string', 'description': 'Filter by source'},
                'search': {'type': 'string', 'description': 'Search term for keys'}
            },
            'required': []
        },
        'is_active': True
    }
)
print(f'Tool {"created" if created2 else "updated"}: get_mcp_knowledge')

# Register store_mcp_knowledge
tool3, created3 = Tool.objects.update_or_create(
    name='store_mcp_knowledge',
    defaults={
        'description': 'Store knowledge in the MCP knowledge store for future reference by any LLM. Use to save learned information, best practices, and documentation.',
        'handler_path': 'mcp_tools_core.tools.admin.knowledge.store_mcp_knowledge',
        'tags': 'admin,mcp,knowledge,facts',
        'input_schema': {
            'type': 'object',
            'properties': {
                'key': {'type': 'string', 'description': 'Unique key (use dot notation like mcp.topic.subtopic)'},
                'value': {'description': 'Knowledge to store (string, dict, or list)'},
                'source': {'type': 'string', 'default': 'llm_learning', 'description': 'Source of knowledge'}
            },
            'required': ['key', 'value']
        },
        'is_active': True
    }
)
print(f'Tool {"created" if created3 else "updated"}: store_mcp_knowledge')

# Store knowledge about how to use these tools
fact, fact_created = Fact.objects.update_or_create(
    key='mcp.knowledge.usage',
    defaults={
        'value': {
            'title': 'How to Use MCP Knowledge System',
            'description': 'The MCP knowledge system allows LLMs to store and retrieve information across sessions.',
            'tools': {
                'get_mcp_knowledge': 'Retrieve stored knowledge by key, source, or search term',
                'store_mcp_knowledge': 'Store new knowledge for future reference'
            },
            'key_conventions': {
                'mcp.*': 'MCP platform knowledge (deployment, tools, etc.)',
                'network.*': 'Network-related knowledge',
                'unifi.*': 'UniFi-specific knowledge',
                'synology.*': 'Synology NAS knowledge', 
                'user.*': 'User preferences and settings',
                'best_practices.*': 'Best practices for various operations'
            },
            'best_practices': [
                'Always check for existing knowledge before asking the user',
                'Store learned information for future sessions',
                'Use descriptive keys with dot notation',
                'Include source to track where knowledge came from'
            ]
        },
        'source': 'system'
    }
)
print(f'Knowledge {"created" if fact_created else "updated"}: mcp.knowledge.usage')

print('\\nAll admin tools registered successfully!')

