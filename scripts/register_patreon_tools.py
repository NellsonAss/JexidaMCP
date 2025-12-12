#!/usr/bin/env python3
"""Register Patreon MCP tools in the database.

Run this on the MCP server after deploying the Patreon tools modules.

Usage:
    python scripts/register_patreon_tools.py
"""

import os
import sys
import django

# Add the jexida_dashboard to the path
sys.path.insert(0, '/opt/jexida-mcp/jexida_dashboard')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jexida_dashboard.settings')

django.setup()

from mcp_tools_core.models import Tool

# =============================================================================
# Patreon Tools
# =============================================================================

PATREON_TOOLS = [
    {
        "name": "patreon_get_creator",
        "description": "Get Patreon creator and primary campaign information. Returns creator ID, name, email, and campaign details including patron count.",
        "handler_path": "mcp_tools_core.tools.patreon.tools.patreon_get_creator",
        "tags": "patreon,creator,campaign",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "patreon_get_tiers",
        "description": "Get all tiers for a Patreon campaign. Returns tier ID, title, amount, description, and patron count for each tier.",
        "handler_path": "mcp_tools_core.tools.patreon.tools.patreon_get_tiers",
        "tags": "patreon,tiers,campaign",
        "input_schema": {
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "Campaign ID (uses PATREON_CREATOR_CAMPAIGN_ID env if not provided)"
                }
            },
            "required": []
        }
    },
    {
        "name": "patreon_get_patrons",
        "description": "Get patrons for a Patreon campaign with optional filtering. Returns patron details including name, email, status, pledge amount, and tier.",
        "handler_path": "mcp_tools_core.tools.patreon.tools.patreon_get_patrons",
        "tags": "patreon,patrons,members,campaign",
        "input_schema": {
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "Campaign ID (uses PATREON_CREATOR_CAMPAIGN_ID env if not provided)"
                },
                "status_filter": {
                    "type": "string",
                    "enum": ["active_patron", "declined_patron", "former_patron"],
                    "description": "Filter by patron status"
                },
                "tier_filter": {
                    "type": "string",
                    "description": "Filter by tier name (case-insensitive partial match)"
                }
            },
            "required": []
        }
    },
    {
        "name": "patreon_get_patron",
        "description": "Get detailed information for a specific Patreon patron by member ID.",
        "handler_path": "mcp_tools_core.tools.patreon.tools.patreon_get_patron",
        "tags": "patreon,patron,member",
        "input_schema": {
            "type": "object",
            "properties": {
                "patron_id": {
                    "type": "string",
                    "description": "The patron/member ID to look up"
                }
            },
            "required": ["patron_id"]
        }
    },
    {
        "name": "patreon_export_patrons",
        "description": "Export patron data as JSON or CSV for external use (email workflows, Discord sync, etc.).",
        "handler_path": "mcp_tools_core.tools.patreon.tools.patreon_export_patrons",
        "tags": "patreon,patrons,export,csv,automation",
        "input_schema": {
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "Campaign ID (uses PATREON_CREATOR_CAMPAIGN_ID env if not provided)"
                },
                "status_filter": {
                    "type": "string",
                    "enum": ["active_patron", "declined_patron", "former_patron"],
                    "description": "Filter by patron status"
                },
                "format": {
                    "type": "string",
                    "enum": ["json", "csv"],
                    "default": "json",
                    "description": "Export format: json or csv"
                }
            },
            "required": []
        }
    },
]


def main():
    print("Registering Patreon MCP tools...")
    print("=" * 60)
    
    created_count = 0
    updated_count = 0
    
    for tool_data in PATREON_TOOLS:
        tool, created = Tool.objects.update_or_create(
            name=tool_data["name"],
            defaults={
                "description": tool_data["description"],
                "handler_path": tool_data["handler_path"],
                "tags": tool_data["tags"],
                "input_schema": tool_data["input_schema"],
                "is_active": True,
            }
        )
        action = "Created" if created else "Updated"
        if created:
            created_count += 1
        else:
            updated_count += 1
        print(f"  {action}: {tool.name}")
    
    print()
    print("=" * 60)
    print(f"Summary: {created_count} created, {updated_count} updated")
    print(f"Total Patreon tools: {len(PATREON_TOOLS)}")
    print()
    print("Don't forget to restart the jexida-mcp service:")
    print("  sudo systemctl restart jexida-mcp.service")


if __name__ == "__main__":
    main()

