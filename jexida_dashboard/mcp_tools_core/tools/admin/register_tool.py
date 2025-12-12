"""Tool for registering new MCP tools via API.

Provides the register_mcp_tool tool for adding new tools to the database
without requiring SSH access.
"""

import subprocess
import logging
from typing import Optional, Dict, Any, List

from asgiref.sync import sync_to_async
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RegisterMCPToolInput(BaseModel):
    """Input schema for register_mcp_tool."""
    
    name: str = Field(
        description="Unique tool name (e.g., 'unifi_list_clients')"
    )
    description: str = Field(
        description="Human-readable description of what the tool does"
    )
    handler_path: str = Field(
        description="Python import path to handler function (e.g., 'mcp_tools_core.tools.unifi.clients.unifi_list_clients')"
    )
    tags: str = Field(
        default="",
        description="Comma-separated tags for categorization (e.g., 'unifi,network,clients')"
    )
    input_schema: Dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}, "required": []},
        description="JSON Schema defining the tool's input parameters"
    )
    is_active: bool = Field(
        default=True,
        description="Whether the tool should be active immediately"
    )
    restart_service: bool = Field(
        default=False,
        description="Whether to restart the jexida-mcp service after registration (requires code to be deployed)"
    )


class RegisterMCPToolOutput(BaseModel):
    """Output schema for register_mcp_tool."""
    
    success: bool = Field(description="Whether the registration succeeded")
    created: bool = Field(default=False, description="True if new tool was created, False if updated")
    tool_name: str = Field(default="", description="Name of the registered tool")
    service_restarted: bool = Field(default=False, description="Whether the service was restarted")
    message: str = Field(default="", description="Status message")
    error: str = Field(default="", description="Error message if failed")


async def register_mcp_tool(params: RegisterMCPToolInput) -> RegisterMCPToolOutput:
    """Register a new MCP tool in the database.
    
    This tool allows registering new tools via the API without SSH access.
    Note: The tool's Python code must already be deployed to the server.
    
    Args:
        params: Tool registration parameters
        
    Returns:
        Registration result with success status
    """
    logger.info(f"Registering MCP tool: {params.name}")
    
    try:
        # Import Django models (deferred to avoid circular imports)
        from mcp_tools_core.models import Tool
        
        # Validate handler path format
        if not params.handler_path or "." not in params.handler_path:
            return RegisterMCPToolOutput(
                success=False,
                error=f"Invalid handler_path format: {params.handler_path}. Expected format: 'module.submodule.function'"
            )
        
        # Try to import the handler to validate it exists
        try:
            parts = params.handler_path.rsplit(".", 1)
            if len(parts) == 2:
                import importlib
                module = importlib.import_module(parts[0])
                if not hasattr(module, parts[1]):
                    return RegisterMCPToolOutput(
                        success=False,
                        error=f"Handler function '{parts[1]}' not found in module '{parts[0]}'. Make sure the code is deployed."
                    )
        except ImportError as e:
            return RegisterMCPToolOutput(
                success=False,
                error=f"Could not import handler module: {e}. Make sure the code is deployed."
            )
        
        # Register or update the tool
        @sync_to_async
        def save_tool():
            return Tool.objects.update_or_create(
                name=params.name,
                defaults={
                    "description": params.description,
                    "handler_path": params.handler_path,
                    "tags": params.tags,
                    "input_schema": params.input_schema,
                    "is_active": params.is_active,
                }
            )
        
        tool, created = await save_tool()
        action = "created" if created else "updated"
        logger.info(f"Tool {action}: {tool.name}")
        
        # Optionally restart the service
        service_restarted = False
        if params.restart_service:
            try:
                result = subprocess.run(
                    ["sudo", "systemctl", "restart", "jexida-mcp.service"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                service_restarted = result.returncode == 0
                if not service_restarted:
                    logger.warning(f"Service restart failed: {result.stderr}")
            except Exception as e:
                logger.warning(f"Could not restart service: {e}")
        
        return RegisterMCPToolOutput(
            success=True,
            created=created,
            tool_name=tool.name,
            service_restarted=service_restarted,
            message=f"Tool '{params.name}' {action} successfully" + 
                    (" and service restarted" if service_restarted else "")
        )
        
    except Exception as e:
        logger.error(f"Failed to register tool: {e}")
        return RegisterMCPToolOutput(
            success=False,
            error=f"Registration failed: {e}"
        )

