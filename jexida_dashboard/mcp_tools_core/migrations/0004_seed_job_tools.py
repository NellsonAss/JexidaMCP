"""Seed migration to register job system MCP tools.

This migration creates Tool records for:
- Worker node management tools
- Job management tools
"""

from django.db import migrations


def seed_job_tools(apps, schema_editor):
    """Create Tool records for job system."""
    Tool = apps.get_model("mcp_tools_core", "Tool")

    job_tools = [
        # Worker Node Tools
        {
            "name": "list_worker_nodes",
            "description": "List all configured worker nodes for job execution. Returns node name, host, user, tags, and status.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "active_only": {
                        "type": "boolean",
                        "description": "If True, only return active nodes",
                        "default": True
                    },
                    "tag": {
                        "type": "string",
                        "description": "Filter nodes by tag (e.g., 'gpu', 'ubuntu')"
                    }
                },
                "required": []
            },
            "handler_path": "mcp_tools_core.tools.jobs.nodes.list_worker_nodes",
            "tags": "jobs,nodes,worker",
        },
        {
            "name": "get_worker_node",
            "description": "Get details of a specific worker node by name.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the worker node to retrieve"
                    }
                },
                "required": ["name"]
            },
            "handler_path": "mcp_tools_core.tools.jobs.nodes.get_worker_node",
            "tags": "jobs,nodes,worker",
        },
        {
            "name": "check_worker_node",
            "description": "Test SSH connectivity to a worker node. Verifies SSH access is working and returns latency and system info.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the worker node to check"
                    },
                    "detailed": {
                        "type": "boolean",
                        "description": "If True, get detailed system information",
                        "default": False
                    }
                },
                "required": ["name"]
            },
            "handler_path": "mcp_tools_core.tools.jobs.nodes.check_worker_node",
            "tags": "jobs,nodes,worker,ssh",
        },
        # Job Management Tools
        {
            "name": "submit_job",
            "description": "Submit and execute a shell command as a job on a worker node. Jobs are executed synchronously and results are stored.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "node_name": {
                        "type": "string",
                        "description": "Name of the worker node to run the job on"
                    },
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute on the worker node"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Command timeout in seconds (default: 5 minutes)",
                        "default": 300
                    }
                },
                "required": ["node_name", "command"]
            },
            "handler_path": "mcp_tools_core.tools.jobs.jobs.submit_job",
            "tags": "jobs,execution,worker",
        },
        {
            "name": "list_jobs",
            "description": "List recent jobs with optional filtering by node or status. Jobs are returned newest first.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "node_name": {
                        "type": "string",
                        "description": "Filter by worker node name"
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by status: queued, running, succeeded, failed"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of jobs to return",
                        "default": 20
                    }
                },
                "required": []
            },
            "handler_path": "mcp_tools_core.tools.jobs.jobs.list_jobs",
            "tags": "jobs,execution,worker",
        },
        {
            "name": "get_job",
            "description": "Get full details of a specific job including complete stdout and stderr output.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "UUID of the job to retrieve"
                    }
                },
                "required": ["job_id"]
            },
            "handler_path": "mcp_tools_core.tools.jobs.jobs.get_job",
            "tags": "jobs,execution,worker",
        },
    ]

    for tool_data in job_tools:
        Tool.objects.update_or_create(
            name=tool_data["name"],
            defaults=tool_data,
        )


def reverse_seed_job_tools(apps, schema_editor):
    """Remove job system Tool records."""
    Tool = apps.get_model("mcp_tools_core", "Tool")
    Tool.objects.filter(handler_path__startswith="mcp_tools_core.tools.jobs.").delete()


class Migration(migrations.Migration):
    """Register job system MCP tools."""

    dependencies = [
        ("mcp_tools_core", "0003_workernode_job"),
    ]

    operations = [
        migrations.RunPython(seed_job_tools, reverse_seed_job_tools),
    ]

