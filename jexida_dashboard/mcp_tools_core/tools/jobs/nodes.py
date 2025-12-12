"""Worker node management tools for MCP platform.

Provides tools for managing worker nodes:
- list_worker_nodes: List all configured worker nodes
- get_worker_node: Get details of a specific node
- check_worker_node: Test SSH connectivity to a node
"""

import logging
from typing import Optional, List

from asgiref.sync import sync_to_async
from pydantic import BaseModel, Field

from .executor import WorkerSSHExecutor

logger = logging.getLogger(__name__)


# =============================================================================
# List Worker Nodes Tool
# =============================================================================

class ListWorkerNodesInput(BaseModel):
    """Input schema for list_worker_nodes."""

    active_only: bool = Field(
        default=True,
        description="If True, only return active nodes"
    )
    tag: Optional[str] = Field(
        default=None,
        description="Filter nodes by tag (e.g., 'gpu', 'ubuntu')"
    )


class WorkerNodeInfo(BaseModel):
    """Information about a worker node."""

    name: str = Field(description="Node identifier")
    host: str = Field(description="Hostname or IP address")
    user: str = Field(description="SSH username")
    ssh_port: int = Field(description="SSH port")
    tags: List[str] = Field(default_factory=list, description="Node tags")
    is_active: bool = Field(description="Whether node is active")
    last_seen: Optional[str] = Field(default=None, description="Last contact timestamp")


class ListWorkerNodesOutput(BaseModel):
    """Output schema for list_worker_nodes."""

    success: bool = Field(description="Whether the query succeeded")
    nodes: List[WorkerNodeInfo] = Field(default_factory=list, description="List of worker nodes")
    count: int = Field(default=0, description="Number of nodes returned")
    error: str = Field(default="", description="Error message if failed")


async def list_worker_nodes(params: ListWorkerNodesInput) -> ListWorkerNodesOutput:
    """List all configured worker nodes.

    Use this tool to see available worker nodes for job execution.

    Args:
        params: Filter parameters

    Returns:
        List of worker nodes matching the filter
    """
    logger.info(f"Listing worker nodes: active_only={params.active_only}, tag={params.tag}")

    try:
        from mcp_tools_core.models import WorkerNode

        @sync_to_async
        def query_nodes():
            queryset = WorkerNode.objects.all()

            if params.active_only:
                queryset = queryset.filter(is_active=True)

            nodes = []
            for node in queryset:
                # Filter by tag if specified
                if params.tag:
                    tags_list = node.get_tags_list()
                    if params.tag.lower() not in [t.lower() for t in tags_list]:
                        continue

                nodes.append(WorkerNodeInfo(
                    name=node.name,
                    host=node.host,
                    user=node.user,
                    ssh_port=node.ssh_port,
                    tags=node.get_tags_list(),
                    is_active=node.is_active,
                    last_seen=node.last_seen.isoformat() if node.last_seen else None,
                ))

            return nodes

        nodes = await query_nodes()

        return ListWorkerNodesOutput(
            success=True,
            nodes=nodes,
            count=len(nodes)
        )

    except Exception as e:
        logger.error(f"Failed to list worker nodes: {e}")
        return ListWorkerNodesOutput(
            success=False,
            error=str(e)
        )


# =============================================================================
# Get Worker Node Tool
# =============================================================================

class GetWorkerNodeInput(BaseModel):
    """Input schema for get_worker_node."""

    name: str = Field(
        description="Name of the worker node to retrieve"
    )


class GetWorkerNodeOutput(BaseModel):
    """Output schema for get_worker_node."""

    success: bool = Field(description="Whether the query succeeded")
    node: Optional[WorkerNodeInfo] = Field(default=None, description="Node details")
    error: str = Field(default="", description="Error message if failed")


async def get_worker_node(params: GetWorkerNodeInput) -> GetWorkerNodeOutput:
    """Get details of a specific worker node by name.

    Args:
        params: Node name to retrieve

    Returns:
        Node details if found
    """
    logger.info(f"Getting worker node: {params.name}")

    try:
        from mcp_tools_core.models import WorkerNode

        @sync_to_async
        def get_node():
            try:
                node = WorkerNode.objects.get(name=params.name)
                return WorkerNodeInfo(
                    name=node.name,
                    host=node.host,
                    user=node.user,
                    ssh_port=node.ssh_port,
                    tags=node.get_tags_list(),
                    is_active=node.is_active,
                    last_seen=node.last_seen.isoformat() if node.last_seen else None,
                )
            except WorkerNode.DoesNotExist:
                return None

        node_info = await get_node()

        if node_info is None:
            return GetWorkerNodeOutput(
                success=False,
                error=f"Worker node '{params.name}' not found"
            )

        return GetWorkerNodeOutput(
            success=True,
            node=node_info
        )

    except Exception as e:
        logger.error(f"Failed to get worker node: {e}")
        return GetWorkerNodeOutput(
            success=False,
            error=str(e)
        )


# =============================================================================
# Check Worker Node Tool
# =============================================================================

class CheckWorkerNodeInput(BaseModel):
    """Input schema for check_worker_node."""

    name: str = Field(
        description="Name of the worker node to check"
    )
    detailed: bool = Field(
        default=False,
        description="If True, get detailed system information"
    )


class CheckWorkerNodeOutput(BaseModel):
    """Output schema for check_worker_node."""

    success: bool = Field(description="Whether the check succeeded")
    reachable: bool = Field(default=False, description="Whether the node is reachable via SSH")
    node: Optional[WorkerNodeInfo] = Field(default=None, description="Node details")
    stdout: str = Field(default="", description="Output from connectivity check")
    stderr: str = Field(default="", description="Error output if any")
    latency_ms: int = Field(default=0, description="SSH round-trip time in milliseconds")
    error: str = Field(default="", description="Error message if failed")


async def check_worker_node(params: CheckWorkerNodeInput) -> CheckWorkerNodeOutput:
    """Test SSH connectivity to a worker node.

    Runs a simple command on the worker node to verify:
    - SSH connectivity is working
    - Authentication is successful
    - The node is responsive

    If detailed=True, also retrieves system information.

    Args:
        params: Node name and options

    Returns:
        Connectivity check results
    """
    logger.info(f"Checking worker node: {params.name}, detailed={params.detailed}")

    try:
        from mcp_tools_core.models import WorkerNode
        from django.utils import timezone

        @sync_to_async
        def get_node():
            try:
                return WorkerNode.objects.get(name=params.name)
            except WorkerNode.DoesNotExist:
                return None

        @sync_to_async
        def update_last_seen(node):
            node.last_seen = timezone.now()
            node.save(update_fields=["last_seen"])

        node = await get_node()

        if node is None:
            return CheckWorkerNodeOutput(
                success=False,
                error=f"Worker node '{params.name}' not found"
            )

        # Run connectivity check
        executor = WorkerSSHExecutor(timeout=30)

        if params.detailed:
            result = executor.get_node_info(node)
        else:
            result = executor.check_connectivity(node)

        node_info = WorkerNodeInfo(
            name=node.name,
            host=node.host,
            user=node.user,
            ssh_port=node.ssh_port,
            tags=node.get_tags_list(),
            is_active=node.is_active,
            last_seen=node.last_seen.isoformat() if node.last_seen else None,
        )

        if result.success:
            # Update last_seen timestamp
            await update_last_seen(node)

            return CheckWorkerNodeOutput(
                success=True,
                reachable=True,
                node=node_info,
                stdout=result.stdout,
                stderr=result.stderr,
                latency_ms=result.duration_ms,
            )
        else:
            return CheckWorkerNodeOutput(
                success=True,  # The check completed, but node is not reachable
                reachable=False,
                node=node_info,
                stdout=result.stdout,
                stderr=result.stderr,
                latency_ms=result.duration_ms,
                error=f"Node not reachable: {result.stderr}"
            )

    except Exception as e:
        logger.error(f"Failed to check worker node: {e}")
        return CheckWorkerNodeOutput(
            success=False,
            error=str(e)
        )

