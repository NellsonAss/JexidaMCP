#!/usr/bin/env python3
"""Register n8n MCP tools in the database.

Run this on the MCP server after deploying the n8n tools module.
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
    # Deployment
    {
        "name": "n8n_deploy_stack",
        "description": "Deploy n8n automation platform to a worker node. Installs Docker, creates directories, and starts n8n container with provided credentials.",
        "handler_path": "mcp_tools_core.tools.n8n.deploy.n8n_deploy_stack",
        "tags": "n8n,automation,deployment,docker",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_name": {
                    "type": "string",
                    "description": "Name of the worker node to deploy to (must be registered)"
                },
                "n8n_user": {
                    "type": "string",
                    "default": "admin",
                    "description": "Username for n8n web UI basic auth"
                },
                "n8n_password": {
                    "type": "string",
                    "description": "Password for n8n web UI basic auth"
                },
                "encryption_key": {
                    "type": "string",
                    "default": "auto",
                    "description": "32-byte hex encryption key, or 'auto' to generate"
                },
                "force_reinstall": {
                    "type": "boolean",
                    "default": False,
                    "description": "Force reinstall even if n8n is already running"
                }
            },
            "required": ["node_name", "n8n_password"]
        }
    },
    # Health Check
    {
        "name": "n8n_health_check",
        "description": "Check n8n instance health status. Verifies the n8n server is running and responsive.",
        "handler_path": "mcp_tools_core.tools.n8n.api.n8n_health_check",
        "tags": "n8n,automation,health,monitoring",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    # List Workflows
    {
        "name": "n8n_list_workflows",
        "description": "List all n8n workflows. Retrieves the list of workflows from the n8n instance.",
        "handler_path": "mcp_tools_core.tools.n8n.api.n8n_list_workflows",
        "tags": "n8n,automation,workflows",
        "input_schema": {
            "type": "object",
            "properties": {
                "active_only": {
                    "type": "boolean",
                    "default": False,
                    "description": "Only return active workflows"
                }
            },
            "required": []
        }
    },
    # Get Workflow
    {
        "name": "n8n_get_workflow",
        "description": "Get details of a specific n8n workflow including nodes and connections.",
        "handler_path": "mcp_tools_core.tools.n8n.api.n8n_get_workflow",
        "tags": "n8n,automation,workflows",
        "input_schema": {
            "type": "object",
            "properties": {
                "workflow_id": {
                    "type": "string",
                    "description": "ID of the workflow to retrieve"
                }
            },
            "required": ["workflow_id"]
        }
    },
    # Run Workflow
    {
        "name": "n8n_run_workflow",
        "description": "Execute an n8n workflow. Triggers a workflow execution and returns the execution ID for tracking.",
        "handler_path": "mcp_tools_core.tools.n8n.api.n8n_run_workflow",
        "tags": "n8n,automation,workflows,execution",
        "input_schema": {
            "type": "object",
            "properties": {
                "workflow_id": {
                    "type": "string",
                    "description": "ID of the workflow to run"
                },
                "payload": {
                    "type": "object",
                    "default": {},
                    "description": "Optional input data for the workflow"
                }
            },
            "required": ["workflow_id"]
        }
    },
    # Get Execution
    {
        "name": "n8n_get_execution",
        "description": "Get details of a workflow execution including status and results.",
        "handler_path": "mcp_tools_core.tools.n8n.api.n8n_get_execution",
        "tags": "n8n,automation,execution",
        "input_schema": {
            "type": "object",
            "properties": {
                "execution_id": {
                    "type": "string",
                    "description": "ID of the execution to retrieve"
                }
            },
            "required": ["execution_id"]
        }
    },
    # Trigger Webhook
    {
        "name": "n8n_trigger_webhook",
        "description": "Trigger an n8n webhook endpoint. Sends a POST request to the specified webhook path.",
        "handler_path": "mcp_tools_core.tools.n8n.api.n8n_trigger_webhook",
        "tags": "n8n,automation,webhooks",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Webhook path (after /webhook/)"
                },
                "payload": {
                    "type": "object",
                    "default": {},
                    "description": "JSON payload to send to the webhook"
                }
            },
            "required": ["path"]
        }
    },
    # Restart Stack
    {
        "name": "n8n_restart_stack",
        "description": "Restart the n8n Docker stack via SSH. Executes docker compose restart on the n8n host.",
        "handler_path": "mcp_tools_core.tools.n8n.admin.n8n_restart_stack",
        "tags": "n8n,automation,admin,docker",
        "input_schema": {
            "type": "object",
            "properties": {
                "force": {
                    "type": "boolean",
                    "default": False,
                    "description": "Force restart even if n8n appears unhealthy"
                }
            },
            "required": []
        }
    },
    # Backup
    {
        "name": "n8n_backup",
        "description": "Create a backup of n8n data. Creates a tarball of /opt/n8n/data and stores it in /opt/n8n/backups/.",
        "handler_path": "mcp_tools_core.tools.n8n.admin.n8n_backup",
        "tags": "n8n,automation,admin,backup",
        "input_schema": {
            "type": "object",
            "properties": {
                "backup_name": {
                    "type": "string",
                    "description": "Custom backup name (defaults to timestamp)"
                }
            },
            "required": []
        }
    },
    # Restore Backup
    {
        "name": "n8n_restore_backup",
        "description": "Restore n8n data from a backup file. Restores data from a tarball backup.",
        "handler_path": "mcp_tools_core.tools.n8n.admin.n8n_restore_backup",
        "tags": "n8n,automation,admin,backup,restore",
        "input_schema": {
            "type": "object",
            "properties": {
                "backup_file": {
                    "type": "string",
                    "description": "Path to backup file (e.g., /opt/n8n/backups/n8n_backup_20241210.tar.gz)"
                },
                "stop_n8n": {
                    "type": "boolean",
                    "default": True,
                    "description": "Stop n8n before restoring (recommended)"
                }
            },
            "required": ["backup_file"]
        }
    },
]


def main():
    print("Registering n8n MCP tools...")
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
    print(f"Registered {len(TOOLS)} n8n tools successfully!")


if __name__ == "__main__":
    main()

