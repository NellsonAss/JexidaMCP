"""Azure tools package.

Contains Azure-related MCP tools:
- azure_cli.run: Execute Azure CLI commands
- azure_cost.get_summary: Get cost summaries
- monitor.http_health_probe: HTTP health checks
"""

# Import tools to trigger registration
from . import cli
from . import cost
from . import monitor

__all__ = ["cli", "cost", "monitor"]

