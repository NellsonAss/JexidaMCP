"""Admin tools for MCP platform management.

Contains tools for self-management of the MCP platform:
- register_mcp_tool: Register a new tool in the database
- get_mcp_knowledge: Retrieve stored knowledge
- store_mcp_knowledge: Store new knowledge for future reference
"""

from . import register_tool
from . import knowledge

__all__ = [
    "register_tool",
    "knowledge",
]

