#!/usr/bin/env python3
"""Register the security_monitor_unifi tool via MCP API.

This script registers the security_monitor_unifi tool using the register_mcp_tool API endpoint.
Run this after deploying the tool code to the server.

Usage:
    python register_security_monitor.py [--api-url http://192.168.1.224:8080]
"""

import argparse
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
        "restart_service": False,
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
    parser = argparse.ArgumentParser(description="Register security_monitor_unifi tool via MCP API")
    parser.add_argument(
        "--api-url",
        default="http://192.168.1.224:8080",
        help="Base URL of the MCP dashboard API"
    )
    args = parser.parse_args()
    
    # Add the jexida_dashboard to path for imports
    sys.path.insert(0, str(Path(__file__).parent / "jexida_dashboard"))
    
    # Import model
    try:
        from mcp_tools_core.tools.unifi.monitoring import SecurityMonitorUnifiInput
    except ImportError as e:
        print(f"Error importing model: {e}")
        print("Make sure you're running from the project root and dependencies are installed.")
        sys.exit(1)
    
    # Register the tool
    input_schema = pydantic_to_json_schema(SecurityMonitorUnifiInput)
    result = register_tool_via_api(
        name="security_monitor_unifi",
        description="Real-time security monitoring for UniFi networks. Monitors unauthorized device joins, rogue APs, port state changes, authentication failures, and WAN attacks/IPS alerts. Supports snapshot mode (one-time check) or watch mode (continuous monitoring).",
        handler_path="mcp_tools_core.tools.unifi.monitoring.security_monitor_unifi",
        input_schema=input_schema,
        tags="unifi,security,monitoring",
        api_url=args.api_url,
    )
    
    if result.get("success"):
        print("\n✓ security_monitor_unifi registered successfully")
        sys.exit(0)
    else:
        print(f"\n✗ Registration failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()

