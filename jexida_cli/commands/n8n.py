"""n8n CLI command handlers.

Provides CLI commands for interacting with n8n via MCP tools.
"""

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..ui.renderer import Renderer
    from ..mcp_client import MCPClient


def handle_n8n_help(renderer: "Renderer") -> str:
    """Show n8n command help."""
    help_text = """
[bold]n8n Automation Commands[/bold]

[cyan]/n8n health[/cyan]              Check n8n instance health
[cyan]/n8n list[/cyan]                List all workflows
[cyan]/n8n list --active[/cyan]       List active workflows only
[cyan]/n8n get <id>[/cyan]            Get workflow details
[cyan]/n8n run <id>[/cyan]            Run a workflow
[cyan]/n8n run <id> <json>[/cyan]     Run workflow with payload
[cyan]/n8n exec <id>[/cyan]           Get execution details
[cyan]/n8n webhook <path>[/cyan]      Trigger a webhook
[cyan]/n8n webhook <path> <json>[/cyan] Trigger webhook with payload
[cyan]/n8n restart[/cyan]             Restart n8n Docker stack
[cyan]/n8n backup[/cyan]              Create n8n data backup
[cyan]/n8n backup <name>[/cyan]       Create named backup

[dim]Examples:[/dim]
  /n8n run 5 {"input": "test"}
  /n8n webhook my-hook {"action": "trigger"}
"""
    renderer.info(help_text.strip(), title="N8N COMMANDS")
    return "continue"


def handle_n8n_health(renderer: "Renderer", mcp_client: "MCPClient") -> str:
    """Handle /n8n health - check n8n health."""
    renderer.info("Checking n8n health...", title="N8N")
    
    result = mcp_client.run_tool("n8n_health_check", {})
    
    if result.get("success"):
        inner = result.get("result", {})
        if inner.get("healthy"):
            renderer.success(
                f"n8n is healthy!\n\n"
                f"URL: {inner.get('base_url', 'unknown')}\n"
                f"Status: HTTP {inner.get('status_code', 0)}",
                title="HEALTH CHECK"
            )
        else:
            renderer.error(
                f"n8n is not healthy\n\n"
                f"URL: {inner.get('base_url', 'unknown')}\n"
                f"Error: {inner.get('error', 'Unknown')}",
            )
    else:
        renderer.error(f"Health check failed: {result.get('error', 'Unknown error')}")
    
    return "continue"


def handle_n8n_list(renderer: "Renderer", mcp_client: "MCPClient", active_only: bool = False) -> str:
    """Handle /n8n list - list workflows."""
    renderer.info("Fetching workflows...", title="N8N")
    
    result = mcp_client.run_tool("n8n_list_workflows", {"active_only": active_only})
    
    if result.get("success"):
        inner = result.get("result", {})
        if inner.get("success"):
            workflows = inner.get("workflows", [])
            if not workflows:
                renderer.info("No workflows found.")
            else:
                lines = [f"Found {len(workflows)} workflow(s):\n"]
                for wf in workflows:
                    status = "[green]●[/green]" if wf.get("active") else "[dim]○[/dim]"
                    lines.append(f"  {status} [{wf.get('id')}] {wf.get('name')}")
                renderer.info("\n".join(lines), title="WORKFLOWS")
        else:
            renderer.error(f"Failed: {inner.get('error', 'Unknown')}")
    else:
        renderer.error(f"Request failed: {result.get('error', 'Unknown error')}")
    
    return "continue"


def handle_n8n_get(renderer: "Renderer", mcp_client: "MCPClient", workflow_id: str) -> str:
    """Handle /n8n get <id> - get workflow details."""
    renderer.info(f"Fetching workflow {workflow_id}...", title="N8N")
    
    result = mcp_client.run_tool("n8n_get_workflow", {"workflow_id": workflow_id})
    
    if result.get("success"):
        inner = result.get("result", {})
        if inner.get("success"):
            workflow = inner.get("workflow", {})
            # Format nicely
            info = [
                f"Name: {workflow.get('name', 'Unknown')}",
                f"ID: {workflow.get('id', workflow_id)}",
                f"Active: {workflow.get('active', False)}",
                f"Nodes: {len(workflow.get('nodes', []))}",
            ]
            if workflow.get("nodes"):
                info.append("\nNodes:")
                for node in workflow.get("nodes", []):
                    info.append(f"  • {node.get('name', 'Unknown')} ({node.get('type', 'unknown')})")
            renderer.info("\n".join(info), title=f"WORKFLOW {workflow_id}")
        else:
            renderer.error(f"Failed: {inner.get('error', 'Unknown')}")
    else:
        renderer.error(f"Request failed: {result.get('error', 'Unknown error')}")
    
    return "continue"


def handle_n8n_run(renderer: "Renderer", mcp_client: "MCPClient", workflow_id: str, payload_str: str = "") -> str:
    """Handle /n8n run <id> [payload] - run a workflow."""
    # Parse payload if provided
    payload = {}
    if payload_str:
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError as e:
            renderer.error(f"Invalid JSON payload: {e}")
            return "continue"
    
    renderer.info(f"Running workflow {workflow_id}...", title="N8N")
    
    result = mcp_client.run_tool("n8n_run_workflow", {
        "workflow_id": workflow_id,
        "payload": payload,
    })
    
    if result.get("success"):
        inner = result.get("result", {})
        if inner.get("success"):
            exec_id = inner.get("execution_id", "unknown")
            renderer.success(
                f"Workflow started!\n\n"
                f"Execution ID: {exec_id}\n\n"
                f"Use [cyan]/n8n exec {exec_id}[/cyan] to check status.",
                title="WORKFLOW STARTED"
            )
        else:
            renderer.error(f"Failed: {inner.get('error', 'Unknown')}")
    else:
        renderer.error(f"Request failed: {result.get('error', 'Unknown error')}")
    
    return "continue"


def handle_n8n_exec(renderer: "Renderer", mcp_client: "MCPClient", execution_id: str) -> str:
    """Handle /n8n exec <id> - get execution details."""
    renderer.info(f"Fetching execution {execution_id}...", title="N8N")
    
    result = mcp_client.run_tool("n8n_get_execution", {"execution_id": execution_id})
    
    if result.get("success"):
        inner = result.get("result", {})
        if inner.get("success"):
            status = inner.get("status", "unknown")
            finished = inner.get("finished", False)
            status_icon = "[green]✓[/green]" if status == "success" else "[red]✗[/red]" if status == "error" else "[yellow]…[/yellow]"
            
            info = [
                f"Execution ID: {execution_id}",
                f"Status: {status_icon} {status}",
                f"Finished: {finished}",
            ]
            renderer.info("\n".join(info), title="EXECUTION")
        else:
            renderer.error(f"Failed: {inner.get('error', 'Unknown')}")
    else:
        renderer.error(f"Request failed: {result.get('error', 'Unknown error')}")
    
    return "continue"


def handle_n8n_webhook(renderer: "Renderer", mcp_client: "MCPClient", path: str, payload_str: str = "") -> str:
    """Handle /n8n webhook <path> [payload] - trigger webhook."""
    # Parse payload if provided
    payload = {}
    if payload_str:
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError as e:
            renderer.error(f"Invalid JSON payload: {e}")
            return "continue"
    
    renderer.info(f"Triggering webhook: {path}...", title="N8N")
    
    result = mcp_client.run_tool("n8n_trigger_webhook", {
        "path": path,
        "payload": payload,
    })
    
    if result.get("success"):
        inner = result.get("result", {})
        if inner.get("success"):
            status = inner.get("status_code", 0)
            response = inner.get("response", "")
            renderer.success(
                f"Webhook triggered!\n\n"
                f"Status: HTTP {status}\n"
                f"Response: {json.dumps(response, indent=2) if isinstance(response, dict) else response}",
                title="WEBHOOK RESPONSE"
            )
        else:
            renderer.error(f"Failed: {inner.get('error', 'Unknown')}")
    else:
        renderer.error(f"Request failed: {result.get('error', 'Unknown error')}")
    
    return "continue"


def handle_n8n_restart(renderer: "Renderer", mcp_client: "MCPClient") -> str:
    """Handle /n8n restart - restart n8n stack."""
    renderer.info("Restarting n8n Docker stack...", title="N8N")
    
    result = mcp_client.run_tool("n8n_restart_stack", {})
    
    if result.get("success"):
        inner = result.get("result", {})
        if inner.get("success"):
            renderer.success("n8n stack restarted successfully!", title="RESTART")
            if inner.get("stdout"):
                renderer.info(inner.get("stdout"))
        else:
            renderer.error(f"Restart failed: {inner.get('error', 'Unknown')}")
    else:
        renderer.error(f"Request failed: {result.get('error', 'Unknown error')}")
    
    return "continue"


def handle_n8n_backup(renderer: "Renderer", mcp_client: "MCPClient", backup_name: str = "") -> str:
    """Handle /n8n backup [name] - create backup."""
    renderer.info("Creating n8n backup...", title="N8N")
    
    params = {}
    if backup_name:
        params["backup_name"] = backup_name
    
    result = mcp_client.run_tool("n8n_backup", params)
    
    if result.get("success"):
        inner = result.get("result", {})
        if inner.get("success"):
            backup_file = inner.get("backup_file", "unknown")
            size = inner.get("size_bytes", 0)
            size_mb = size / (1024 * 1024) if size else 0
            renderer.success(
                f"Backup created!\n\n"
                f"File: {backup_file}\n"
                f"Size: {size_mb:.2f} MB",
                title="BACKUP COMPLETE"
            )
        else:
            renderer.error(f"Backup failed: {inner.get('error', 'Unknown')}")
    else:
        renderer.error(f"Request failed: {result.get('error', 'Unknown error')}")
    
    return "continue"

