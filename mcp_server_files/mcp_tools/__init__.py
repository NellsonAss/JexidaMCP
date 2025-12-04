"""MCP Tools package.

Contains all tool implementations organized by category.
"""

# Import tool packages to trigger registration
from . import azure
from . import unifi
from . import synology

__all__ = ["azure", "unifi", "synology"]
