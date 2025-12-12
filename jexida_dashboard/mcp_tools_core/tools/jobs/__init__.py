"""MCP tools for the job system.

This package provides tools for:
- Managing worker nodes (list, get, check connectivity)
- Managing jobs (submit, list, get details)
- Node capability discovery and provisioning
"""

from .nodes import (
    list_worker_nodes,
    get_worker_node,
    check_worker_node,
)
from .jobs import (
    submit_job,
    list_jobs,
    get_job,
)
from .capabilities import (
    catalog_node_capabilities,
    register_worker_node,
    provision_worker_node,
    get_node_setup_instructions,
)

__all__ = [
    "list_worker_nodes",
    "get_worker_node",
    "check_worker_node",
    "submit_job",
    "list_jobs",
    "get_job",
    "catalog_node_capabilities",
    "register_worker_node",
    "provision_worker_node",
    "get_node_setup_instructions",
]

