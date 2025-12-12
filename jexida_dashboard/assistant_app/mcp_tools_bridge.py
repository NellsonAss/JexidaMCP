"""Bridge between AI Assistant and MCP Tools database.

This module connects the AI assistant to the MCP tools registry,
allowing the LLM to discover and execute tools dynamically.

Key features:
- Fetches tool definitions from the database in OpenAI function format
- Executes tools via the MCP executor
- Identifies dangerous tools that require user confirmation
"""

import logging
from typing import Any, Dict, List, Optional

from mcp_tools_core.models import Tool
from mcp_tools_core.executor import execute_tool

logger = logging.getLogger(__name__)

# Tags that indicate a tool modifies state and requires confirmation
DANGEROUS_TAGS = {
    "modify", "delete", "apply", "harden", "create", "update",
    "restart", "reboot", "write", "remove", "disable", "enable",
}

# Tool name patterns that indicate safe read-only operations
SAFE_PATTERNS = {
    "list", "get", "show", "check", "audit", "scan", "status",
    "health", "info", "describe", "query", "search", "find",
}


def get_mcp_tool_definitions(
    tag_filter: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Get OpenAI function definitions from MCP tools database.
    
    Fetches all active tools from the database and converts them to
    OpenAI-compatible function definitions for use in chat completions.
    
    Args:
        tag_filter: Optional tag to filter tools by
        limit: Optional limit on number of tools to return
        
    Returns:
        List of function definitions in OpenAI format
    """
    queryset = Tool.objects.filter(is_active=True)
    
    if tag_filter:
        queryset = queryset.filter(tags__icontains=tag_filter)
    
    if limit:
        queryset = queryset[:limit]
    
    definitions = []
    for tool in queryset:
        # Build the function definition
        func_def = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or f"Execute {tool.name}",
                "parameters": tool.input_schema or {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        }
        definitions.append(func_def)
    
    logger.debug(f"Loaded {len(definitions)} MCP tool definitions")
    return definitions


def get_tool_by_name(name: str) -> Optional[Tool]:
    """Get a tool by its name.
    
    Args:
        name: Tool name
        
    Returns:
        Tool instance or None if not found
    """
    try:
        return Tool.objects.get(name=name, is_active=True)
    except Tool.DoesNotExist:
        return None


def is_dangerous_tool(tool: Tool) -> bool:
    """Determine if a tool requires user confirmation before execution.
    
    A tool is considered dangerous if:
    - It has tags that indicate state modification
    - Its name doesn't match safe read-only patterns
    
    Args:
        tool: Tool instance to check
        
    Returns:
        True if tool requires confirmation, False otherwise
    """
    tool_name = tool.name.lower()
    tags = set(t.lower().strip() for t in tool.get_tags_list())
    
    # Check if any dangerous tags are present
    if tags & DANGEROUS_TAGS:
        return True
    
    # Check if tool name indicates a safe operation
    for pattern in SAFE_PATTERNS:
        if pattern in tool_name:
            return False
    
    # Default to requiring confirmation for unknown tools
    # This is the safer default
    return True


def get_tool_risk_level(tool: Tool) -> str:
    """Get the risk level of a tool for UI display.
    
    Args:
        tool: Tool instance
        
    Returns:
        Risk level: "safe", "moderate", or "dangerous"
    """
    tool_name = tool.name.lower()
    tags = set(t.lower().strip() for t in tool.get_tags_list())
    
    # Check for explicitly dangerous operations
    dangerous_indicators = {"delete", "remove", "harden", "apply", "reboot", "restart"}
    if tags & dangerous_indicators or any(ind in tool_name for ind in dangerous_indicators):
        return "dangerous"
    
    # Check for modifying operations
    modify_indicators = {"create", "update", "modify", "write", "enable", "disable"}
    if tags & modify_indicators or any(ind in tool_name for ind in modify_indicators):
        return "moderate"
    
    # Everything else is considered safe
    return "safe"


async def execute_mcp_tool(
    name: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute an MCP tool and return the result.
    
    This is a thin wrapper around the MCP executor that handles
    tool execution and result formatting.
    
    Args:
        name: Tool name to execute
        params: Parameters to pass to the tool
        
    Returns:
        Dictionary with execution result including:
        - success: bool
        - result: Any (the tool's return value)
        - error: str (if failed)
    """
    try:
        result = await execute_tool(name, params)
        return {
            "success": True,
            "result": result,
            "tool_name": name,
        }
    except Exception as e:
        logger.exception(f"MCP tool execution failed: {name}")
        return {
            "success": False,
            "error": str(e),
            "tool_name": name,
        }


def get_tools_summary() -> Dict[str, Any]:
    """Get a summary of available MCP tools.
    
    Returns:
        Dictionary with tool counts by category
    """
    tools = Tool.objects.filter(is_active=True)
    total = tools.count()
    
    # Count by tag category
    categories = {}
    for tool in tools:
        for tag in tool.get_tags_list():
            tag = tag.lower().strip()
            if tag:
                categories[tag] = categories.get(tag, 0) + 1
    
    # Sort by count descending
    sorted_categories = sorted(
        categories.items(),
        key=lambda x: x[1],
        reverse=True,
    )
    
    return {
        "total": total,
        "categories": dict(sorted_categories[:10]),  # Top 10 categories
    }


def build_tools_context_prompt() -> str:
    """Build a context prompt describing available tools.
    
    This can be injected into the system prompt to give the LLM
    awareness of what tools are available.
    
    Returns:
        String describing available tool categories
    """
    summary = get_tools_summary()
    
    if summary["total"] == 0:
        return "No MCP tools are currently available."
    
    lines = [
        f"You have access to {summary['total']} MCP tools for automation.",
        "Tool categories:",
    ]
    
    for category, count in summary["categories"].items():
        lines.append(f"  - {category}: {count} tools")
    
    lines.append("\nUse these tools to help users manage their infrastructure.")
    
    return "\n".join(lines)

