"""CLI commands for jobs and worker nodes.

Provides handlers for:
- /nodes list - List configured worker nodes
- /nodes check <name> - Check SSH connectivity to a node
- /jobs submit --node <name> --cmd "<cmd>" - Submit a job
- /jobs list - List recent jobs
- /jobs show <id> - Show job details
"""

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..ui.renderer import Renderer
    from ..mcp_client import MCPClient


def handle_nodes_list(renderer: "Renderer", mcp_client: "MCPClient") -> str:
    """Handle /nodes list - list all worker nodes.

    Args:
        renderer: UI renderer
        mcp_client: MCP client for API calls

    Returns:
        "continue" to keep REPL running
    """
    result = mcp_client.execute_tool("list_worker_nodes", {"active_only": False})

    if not result.get("success", False):
        renderer.error(f"Failed to list nodes: {result.get('error', 'Unknown error')}")
        return "continue"

    nodes = result.get("nodes", [])
    if not nodes:
        renderer.info("No worker nodes configured.")
        return "continue"

    # Format nodes table
    lines = [
        "[bold]Worker Nodes[/bold]",
        "",
        f"{'NAME':<20} {'HOST':<18} {'USER':<12} {'PORT':<6} {'ACTIVE':<8} {'LAST SEEN':<20}",
        "─" * 84,
    ]

    for node in nodes:
        name = node.get("name", "?")
        host = node.get("host", "?")
        user = node.get("user", "?")
        port = str(node.get("ssh_port", 22))
        active = "✓" if node.get("is_active") else "✗"
        last_seen = node.get("last_seen", "Never")
        if last_seen and last_seen != "Never":
            # Truncate ISO timestamp
            last_seen = last_seen[:19].replace("T", " ")

        lines.append(f"{name:<20} {host:<18} {user:<12} {port:<6} {active:<8} {last_seen:<20}")

    lines.append("")
    lines.append(f"[dim]Total: {len(nodes)} nodes[/dim]")

    renderer.info("\n".join(lines), title="WORKER NODES")
    return "continue"


def handle_nodes_check(renderer: "Renderer", mcp_client: "MCPClient", node_name: str) -> str:
    """Handle /nodes check <name> - check connectivity to a node.

    Args:
        renderer: UI renderer
        mcp_client: MCP client for API calls
        node_name: Name of node to check

    Returns:
        "continue" to keep REPL running
    """
    if not node_name:
        renderer.error("Usage: /nodes check <node_name>")
        return "continue"

    renderer.info(f"Checking connectivity to [bold]{node_name}[/bold]...")

    result = mcp_client.execute_tool("check_worker_node", {
        "name": node_name,
        "detailed": True,
    })

    if not result.get("success", False):
        renderer.error(f"Check failed: {result.get('error', 'Unknown error')}")
        return "continue"

    reachable = result.get("reachable", False)
    latency = result.get("latency_ms", 0)
    stdout = result.get("stdout", "")
    stderr = result.get("stderr", "")
    error = result.get("error", "")

    if reachable:
        lines = [
            f"[green]✓ Node '{node_name}' is reachable[/green]",
            f"  Latency: {latency}ms",
        ]
        if stdout:
            lines.append("")
            lines.append("[dim]Output:[/dim]")
            for line in stdout.strip().split("\n")[:15]:
                lines.append(f"  {line}")
        renderer.success("\n".join(lines), title="NODE CHECK")
    else:
        lines = [
            f"[red]✗ Node '{node_name}' is unreachable[/red]",
        ]
        if error:
            lines.append(f"  Error: {error}")
        if stderr:
            lines.append("")
            lines.append("[dim]stderr:[/dim]")
            for line in stderr.strip().split("\n")[:5]:
                lines.append(f"  {line}")
        renderer.error("\n".join(lines))

    return "continue"


def handle_jobs_submit(
    renderer: "Renderer",
    mcp_client: "MCPClient",
    node_name: str,
    command: str,
    timeout: int = 300,
) -> str:
    """Handle /jobs submit - submit a job to a node.

    Args:
        renderer: UI renderer
        mcp_client: MCP client for API calls
        node_name: Target node name
        command: Command to execute
        timeout: Timeout in seconds

    Returns:
        "continue" to keep REPL running
    """
    if not node_name or not command:
        renderer.error("Usage: /jobs submit --node <name> --cmd \"<command>\"")
        return "continue"

    renderer.info(f"Submitting job to [bold]{node_name}[/bold]...")
    renderer.console.print(f"[dim]Command: {command[:100]}{'...' if len(command) > 100 else ''}[/dim]")

    result = mcp_client.execute_tool("submit_job", {
        "node_name": node_name,
        "command": command,
        "timeout": timeout,
    })

    if not result.get("success", False):
        error = result.get("error", "Unknown error")
        renderer.error(f"Job failed: {error}")
        return "continue"

    job = result.get("job", {})
    job_id = job.get("id", "?")
    status = job.get("status", "?")
    exit_code = job.get("exit_code")
    duration = job.get("duration_ms")
    stdout = job.get("stdout", "")
    stderr = job.get("stderr", "")

    # Show result
    if status == "succeeded":
        lines = [
            f"[green]✓ Job completed successfully[/green]",
            f"  Job ID: {job_id}",
            f"  Exit code: {exit_code}",
            f"  Duration: {duration}ms" if duration else "",
        ]
        if stdout:
            lines.append("")
            lines.append("[dim]Output:[/dim]")
            # Show up to 30 lines
            for line in stdout.strip().split("\n")[:30]:
                lines.append(f"  {line}")
            if len(stdout.split("\n")) > 30:
                lines.append(f"  [dim]... ({len(stdout.split(chr(10)))} total lines)[/dim]")

        renderer.success("\n".join([l for l in lines if l]), title="JOB RESULT")
    else:
        lines = [
            f"[red]✗ Job failed[/red]",
            f"  Job ID: {job_id}",
            f"  Exit code: {exit_code}",
        ]
        if stderr:
            lines.append("")
            lines.append("[dim]Error output:[/dim]")
            for line in stderr.strip().split("\n")[:20]:
                lines.append(f"  {line}")

        renderer.error("\n".join([l for l in lines if l]))

    return "continue"


def handle_jobs_list(
    renderer: "Renderer",
    mcp_client: "MCPClient",
    node_name: str = None,
    status: str = None,
    limit: int = 20,
) -> str:
    """Handle /jobs list - list recent jobs.

    Args:
        renderer: UI renderer
        mcp_client: MCP client for API calls
        node_name: Optional filter by node
        status: Optional filter by status
        limit: Max jobs to return

    Returns:
        "continue" to keep REPL running
    """
    params = {"limit": limit}
    if node_name:
        params["node_name"] = node_name
    if status:
        params["status"] = status

    result = mcp_client.execute_tool("list_jobs", params)

    if not result.get("success", False):
        renderer.error(f"Failed to list jobs: {result.get('error', 'Unknown error')}")
        return "continue"

    jobs = result.get("jobs", [])
    if not jobs:
        renderer.info("No jobs found.")
        return "continue"

    # Format jobs table
    lines = [
        "[bold]Recent Jobs[/bold]",
        "",
        f"{'ID':<10} {'NODE':<16} {'STATUS':<12} {'EXIT':<6} {'DURATION':<10} {'COMMAND':<30}",
        "─" * 84,
    ]

    for job in jobs:
        job_id = job.get("id", "?")[:8]
        node = job.get("node_name", "?")
        status = job.get("status", "?")
        exit_code = job.get("exit_code")
        exit_str = str(exit_code) if exit_code is not None else "-"
        duration = job.get("duration_ms")
        duration_str = f"{duration}ms" if duration else "-"
        command = job.get("command", "")[:28]

        # Color status
        if status == "succeeded":
            status_display = "[green]succeeded[/green]"
        elif status == "failed":
            status_display = "[red]failed[/red]"
        elif status == "running":
            status_display = "[blue]running[/blue]"
        else:
            status_display = status

        lines.append(f"{job_id:<10} {node:<16} {status_display:<12} {exit_str:<6} {duration_str:<10} {command:<30}")

    lines.append("")
    lines.append(f"[dim]Total: {len(jobs)} jobs[/dim]")
    lines.append("[dim]Use '/jobs show <id>' for full details[/dim]")

    renderer.info("\n".join(lines), title="JOBS")
    return "continue"


def handle_jobs_show(renderer: "Renderer", mcp_client: "MCPClient", job_id: str) -> str:
    """Handle /jobs show <id> - show job details.

    Args:
        renderer: UI renderer
        mcp_client: MCP client for API calls
        job_id: Job ID to show

    Returns:
        "continue" to keep REPL running
    """
    if not job_id:
        renderer.error("Usage: /jobs show <job_id>")
        return "continue"

    result = mcp_client.execute_tool("get_job", {"job_id": job_id})

    if not result.get("success", False):
        renderer.error(f"Failed to get job: {result.get('error', 'Unknown error')}")
        return "continue"

    job = result.get("job", {})
    if not job:
        renderer.error(f"Job '{job_id}' not found.")
        return "continue"

    # Format job details
    status = job.get("status", "?")
    if status == "succeeded":
        status_display = "[green]succeeded[/green]"
    elif status == "failed":
        status_display = "[red]failed[/red]"
    elif status == "running":
        status_display = "[blue]running[/blue]"
    else:
        status_display = status

    lines = [
        f"[bold]Job Details[/bold]",
        "",
        f"  ID:        {job.get('id', '?')}",
        f"  Node:      {job.get('node_name', '?')}",
        f"  Status:    {status_display}",
        f"  Exit code: {job.get('exit_code', '-')}",
        f"  Duration:  {job.get('duration_ms', '-')}ms" if job.get('duration_ms') else "  Duration:  -",
        f"  Created:   {job.get('created_at', '?')}",
        f"  Updated:   {job.get('updated_at', '?')}",
        "",
        "[bold]Command:[/bold]",
        f"  {job.get('command', '')}",
    ]

    stdout = job.get("stdout", "")
    stderr = job.get("stderr", "")

    if stdout:
        lines.append("")
        lines.append("[bold]stdout:[/bold]")
        for line in stdout.split("\n")[:50]:
            lines.append(f"  {line}")
        if len(stdout.split("\n")) > 50:
            lines.append(f"  [dim]... ({len(stdout.split(chr(10)))} total lines)[/dim]")

    if stderr:
        lines.append("")
        lines.append("[bold red]stderr:[/bold red]")
        for line in stderr.split("\n")[:30]:
            lines.append(f"  [red]{line}[/red]")

    renderer.info("\n".join(lines), title="JOB DETAILS")
    return "continue"


def parse_jobs_submit_args(args: str) -> tuple:
    """Parse /jobs submit arguments.

    Supports: --node <name> --cmd "<command>" [--timeout <secs>]

    Args:
        args: Argument string

    Returns:
        Tuple of (node_name, command, timeout)
    """
    node_name = None
    command = None
    timeout = 300

    # Simple parsing
    parts = args.split("--")
    for part in parts:
        part = part.strip()
        if part.startswith("node "):
            node_name = part[5:].strip().strip('"').strip("'")
        elif part.startswith("cmd "):
            # Command can contain spaces, get everything after "cmd "
            command = part[4:].strip().strip('"').strip("'")
        elif part.startswith("timeout "):
            try:
                timeout = int(part[8:].strip())
            except ValueError:
                pass

    return node_name, command, timeout

