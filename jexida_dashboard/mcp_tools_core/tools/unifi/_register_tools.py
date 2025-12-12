"""Helper script to register UniFi tools via MCP API.

This script registers all UniFi tools using the register_mcp_tool API endpoint.
Run this after deploying new tool code to the server.
"""

import json
import sys
from typing import Any, Dict, Type

import httpx
from pydantic import BaseModel


def pydantic_to_json_schema(model: Type[BaseModel]) -> Dict[str, Any]:
    """Convert a Pydantic model to JSON Schema."""
    schema = model.model_json_schema()
    # Clean up the schema for JSON Schema compatibility
    if "definitions" in schema:
        # Flatten definitions into properties if needed
        pass
    return {
        "type": "object",
        "properties": schema.get("properties", {}),
        "required": schema.get("required", []),
    }


def register_tool_via_api(
    name: str,
    description: str,
    handler_path: str,
    input_model: Type[BaseModel],
    tags: str = "",
    api_url: str = "http://192.168.1.224:8080",
) -> Dict[str, Any]:
    """Register a tool via the MCP API.
    
    Args:
        name: Tool name
        description: Tool description
        handler_path: Python import path to handler
        input_model: Pydantic input model
        tags: Comma-separated tags
        api_url: Base URL of the MCP dashboard
        
    Returns:
        Registration result
    """
    input_schema = pydantic_to_json_schema(input_model)
    
    payload = {
        "name": name,
        "description": description,
        "handler_path": handler_path,
        "tags": tags,
        "input_schema": input_schema,
        "is_active": True,
        "restart_service": False,  # Don't restart until all tools are registered
    }
    
    url = f"{api_url}/tools/api/tools/register_mcp_tool/run/"
    
    try:
        response = httpx.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"success": False, "error": str(e), "payload": payload}


# Tool registration definitions
TOOLS_TO_REGISTER = [
    {
        "name": "unifi_controller_get_config",
        "description": "Retrieve full UniFi controller configuration including networks, WLANs, firewall rules, devices, and settings",
        "handler_path": "mcp_tools_core.tools.unifi.controller.unifi_controller_get_config",
        "tags": "unifi,controller,config",
        "input_model": None,  # Will be imported
    },
    {
        "name": "unifi_controller_backup",
        "description": "Create a timestamped controller backup. Always create a backup before making significant changes.",
        "handler_path": "mcp_tools_core.tools.unifi.controller.unifi_controller_backup",
        "tags": "unifi,controller,backup",
        "input_model": None,
    },
    {
        "name": "unifi_controller_list_backups",
        "description": "List all available controller backups with metadata",
        "handler_path": "mcp_tools_core.tools.unifi.controller.unifi_controller_list_backups",
        "tags": "unifi,controller,backup",
        "input_model": None,
    },
    {
        "name": "unifi_controller_restore",
        "description": "Restore a controller backup. WARNING: This will restart the controller and replace all current configuration. Requires confirmation_token='CONFIRM_RESTORE'.",
        "handler_path": "mcp_tools_core.tools.unifi.controller.unifi_controller_restore",
        "tags": "unifi,controller,backup,restore",
        "input_model": None,
    },
]


if __name__ == "__main__":
    # Import models dynamically
    from .controller import (
        UniFiControllerGetConfigInput,
        UniFiControllerBackupInput,
        UniFiControllerListBackupsInput,
        UniFiControllerRestoreInput,
    )
    
    # Update tool definitions with models
    TOOLS_TO_REGISTER[0]["input_model"] = UniFiControllerGetConfigInput
    TOOLS_TO_REGISTER[1]["input_model"] = UniFiControllerBackupInput
    TOOLS_TO_REGISTER[2]["input_model"] = UniFiControllerListBackupsInput
    TOOLS_TO_REGISTER[3]["input_model"] = UniFiControllerRestoreInput
    
    # Register all tools
    results = []
    for tool_def in TOOLS_TO_REGISTER:
        print(f"Registering {tool_def['name']}...")
        result = register_tool_via_api(
            name=tool_def["name"],
            description=tool_def["description"],
            handler_path=tool_def["handler_path"],
            input_model=tool_def["input_model"],
            tags=tool_def["tags"],
        )
        results.append((tool_def["name"], result))
        if result.get("success"):
            print(f"  ✓ {tool_def['name']} registered successfully")
        else:
            print(f"  ✗ {tool_def['name']} failed: {result.get('error', 'Unknown error')}")
    
    # Summary
    success_count = sum(1 for _, r in results if r.get("success"))
    print(f"\nRegistered {success_count}/{len(results)} tools")
    
    if success_count < len(results):
        sys.exit(1)

