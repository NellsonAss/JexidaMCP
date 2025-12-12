#!/usr/bin/env python3
"""Register the new node capability and provisioning tools in the MCP database.

Run this on the MCP server after deploying the capabilities.py file.
"""

import os
import sys
import django

# Add the jexida_dashboard to the path
sys.path.insert(0, '/opt/jexida-mcp/jexida_dashboard')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jexida_dashboard.settings')

django.setup()

from mcp_tools_core.models import Tool

TOOLS = [
    {
        "name": "catalog_node_capabilities",
        "description": "Discover and catalog a worker node's capabilities including hardware, software, and configuration. Stores capabilities for job routing decisions.",
        "handler_path": "mcp_tools_core.tools.jobs.capabilities.catalog_node_capabilities",
        "tags": "jobs,nodes,worker,capabilities,discovery",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the worker node to catalog"
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "register_worker_node",
        "description": "Register a new worker node in the database. Creates or updates a node record with connection details.",
        "handler_path": "mcp_tools_core.tools.jobs.capabilities.register_worker_node",
        "tags": "jobs,nodes,worker,registration",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Unique name for the node (e.g., 'JexidaDroid2')"
                },
                "host": {
                    "type": "string",
                    "description": "Hostname or IP address"
                },
                "user": {
                    "type": "string",
                    "default": "jexida",
                    "description": "SSH username"
                },
                "ssh_port": {
                    "type": "integer",
                    "default": 22,
                    "description": "SSH port"
                },
                "tags": {
                    "type": "string",
                    "default": "ubuntu,worker",
                    "description": "Comma-separated tags"
                },
                "is_active": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether node is active"
                }
            },
            "required": ["name", "host"]
        }
    },
    {
        "name": "provision_worker_node",
        "description": "Provision a worker node for job execution. Sets up jexida user, Python 3, and job directories. Requires existing SSH access.",
        "handler_path": "mcp_tools_core.tools.jobs.capabilities.provision_worker_node",
        "tags": "jobs,nodes,worker,provisioning,setup",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the node to provision"
                },
                "create_user": {
                    "type": "boolean",
                    "default": True,
                    "description": "Create jexida user if missing"
                },
                "install_python": {
                    "type": "boolean",
                    "default": True,
                    "description": "Install Python 3 if missing"
                },
                "create_job_dirs": {
                    "type": "boolean",
                    "default": True,
                    "description": "Create job directories"
                },
                "dry_run": {
                    "type": "boolean",
                    "default": True,
                    "description": "Only show what would be done"
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "get_node_setup_instructions",
        "description": "Get setup instructions for a new worker node including the MCP server's SSH public key and all commands needed to prepare the node.",
        "handler_path": "mcp_tools_core.tools.jobs.capabilities.get_node_setup_instructions",
        "tags": "jobs,nodes,worker,setup,instructions",
        "input_schema": {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "IP address or hostname of the new node"
                },
                "node_name": {
                    "type": "string",
                    "default": "",
                    "description": "Name to use for the node (auto-generated if empty)"
                }
            },
            "required": ["host"]
        }
    }
]


def main():
    print("Registering node capability and provisioning tools...")
    print("=" * 60)

    for tool_data in TOOLS:
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
        print(f"  {action}: {tool.name}")

    print()
    print(f"Registered {len(TOOLS)} tools successfully!")


if __name__ == "__main__":
    main()

