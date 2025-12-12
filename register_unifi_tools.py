#!/usr/bin/env python3
"""Register UniFi tools via MCP API.

This script registers all UniFi tools using the register_mcp_tool API endpoint.
Run this after deploying new tool code to the server.

Usage:
    python register_unifi_tools.py [--api-url http://192.168.1.224:8080]
"""

import argparse
import json
import sys
from pathlib import Path

import httpx
from pydantic import BaseModel


def pydantic_to_json_schema(model: type[BaseModel]) -> dict:
    """Convert a Pydantic model to JSON Schema."""
    schema = model.model_json_schema()
    return {
        "type": "object",
        "properties": schema.get("properties", {}),
        "required": schema.get("required", []),
    }


def register_tool_via_api(
    name: str,
    description: str,
    handler_path: str,
    input_schema: dict,
    tags: str = "",
    api_url: str = "http://192.168.1.224:8080",
) -> dict:
    """Register a tool via the MCP API.
    
    Args:
        name: Tool name
        description: Tool description
        handler_path: Python import path to handler
        input_schema: JSON Schema for input
        tags: Comma-separated tags
        api_url: Base URL of the MCP dashboard
        
    Returns:
        Registration result
    """
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
        print(f"Registering {name}...")
        response = httpx.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        if result.get("success"):
            print(f"  ✓ {name} registered successfully")
        else:
            print(f"  ✗ {name} failed: {result.get('error', 'Unknown error')}")
        return result
    except Exception as e:
        print(f"  ✗ {name} failed: {e}")
        return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Register UniFi tools via MCP API")
    parser.add_argument(
        "--api-url",
        default="http://192.168.1.224:8080",
        help="Base URL of the MCP dashboard API"
    )
    args = parser.parse_args()
    
    # Add the jexida_dashboard to path for imports
    sys.path.insert(0, str(Path(__file__).parent / "jexida_dashboard"))
    
    # Import models
    try:
        from mcp_tools_core.tools.unifi.controller import (
            UniFiControllerGetConfigInput,
            UniFiControllerBackupInput,
            UniFiControllerListBackupsInput,
            UniFiControllerRestoreInput,
        )
    except ImportError as e:
        print(f"Error importing models: {e}")
        print("Make sure you're running from the project root and dependencies are installed.")
        sys.exit(1)
    
    # Define tools to register
    tools = [
        {
            "name": "unifi_controller_get_config",
            "description": "Retrieve full UniFi controller configuration including networks, WLANs, firewall rules, devices, and settings",
            "handler_path": "mcp_tools_core.tools.unifi.controller.unifi_controller_get_config",
            "tags": "unifi,controller,config",
            "input_model": UniFiControllerGetConfigInput,
        },
        {
            "name": "unifi_controller_backup",
            "description": "Create a timestamped controller backup. Always create a backup before making significant changes.",
            "handler_path": "mcp_tools_core.tools.unifi.controller.unifi_controller_backup",
            "tags": "unifi,controller,backup",
            "input_model": UniFiControllerBackupInput,
        },
        {
            "name": "unifi_controller_list_backups",
            "description": "List all available controller backups with metadata",
            "handler_path": "mcp_tools_core.tools.unifi.controller.unifi_controller_list_backups",
            "tags": "unifi,controller,backup",
            "input_model": UniFiControllerListBackupsInput,
        },
        {
            "name": "unifi_controller_restore",
            "description": "Restore a controller backup. WARNING: This will restart the controller and replace all current configuration. Requires confirmation_token='CONFIRM_RESTORE'.",
            "handler_path": "mcp_tools_core.tools.unifi.controller.unifi_controller_restore",
            "tags": "unifi,controller,backup,restore",
            "input_model": UniFiControllerRestoreInput,
        },
    ]
    
    # Register all tools
    results = []
    for tool_def in tools:
        input_schema = pydantic_to_json_schema(tool_def["input_model"])
        result = register_tool_via_api(
            name=tool_def["name"],
            description=tool_def["description"],
            handler_path=tool_def["handler_path"],
            input_schema=input_schema,
            tags=tool_def["tags"],
            api_url=args.api_url,
        )
        results.append((tool_def["name"], result))
    
    # Summary
    success_count = sum(1 for _, r in results if r.get("success"))
    print(f"\nRegistered {success_count}/{len(results)} tools")
    
    if success_count < len(results):
        print("\nFailed registrations:")
        for name, result in results:
            if not result.get("success"):
                print(f"  - {name}: {result.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()

