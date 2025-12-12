"""n8n automation platform integration tools.

This package provides MCP tools for:
- Deploying n8n to worker nodes
- Managing workflows via REST API
- Triggering webhooks and executions
- SSH-based administration (restart, backup)
"""

from .api import (
    n8n_health_check,
    n8n_list_workflows,
    n8n_get_workflow,
    n8n_run_workflow,
    n8n_get_execution,
    n8n_trigger_webhook,
)
from .admin import (
    n8n_restart_stack,
    n8n_backup,
    n8n_restore_backup,
)
from .deploy import (
    n8n_deploy_stack,
)

__all__ = [
    # API tools
    "n8n_health_check",
    "n8n_list_workflows",
    "n8n_get_workflow",
    "n8n_run_workflow",
    "n8n_get_execution",
    "n8n_trigger_webhook",
    # Admin tools
    "n8n_restart_stack",
    "n8n_backup",
    "n8n_restore_backup",
    # Deployment
    "n8n_deploy_stack",
]

