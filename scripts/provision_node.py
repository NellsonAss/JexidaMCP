#!/usr/bin/env python3
"""Helper script to verify a worker node is ready for JexidaMCP.

This script checks:
1. SSH connectivity from MCP server to the worker node
2. Required directories exist
3. Python 3 is installed
4. Basic system information

Usage:
    python scripts/provision_node.py <node_name>
    
Example:
    python scripts/provision_node.py node-ubuntu-0
"""

import sys
import json

try:
    import httpx
except ImportError:
    print("Error: httpx is required. Install with: pip install httpx")
    sys.exit(1)


MCP_SERVER = "http://192.168.1.224:8080"


def check_node(node_name: str) -> dict:
    """Check a worker node using the MCP API.
    
    Args:
        node_name: Name of the worker node to check
        
    Returns:
        Check result dictionary
    """
    url = f"{MCP_SERVER}/tools/api/tools/check_worker_node/run/"
    
    try:
        response = httpx.post(
            url,
            json={"name": node_name, "detailed": True},
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        return {"success": False, "error": f"HTTP error: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_nodes() -> dict:
    """List all worker nodes."""
    url = f"{MCP_SERVER}/tools/api/tools/list_worker_nodes/run/"
    
    try:
        response = httpx.post(
            url,
            json={"active_only": False},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        return {"success": False, "error": f"HTTP error: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def print_check_result(result: dict) -> None:
    """Pretty print the check result."""
    print()
    print("=" * 60)
    print("WORKER NODE PROVISIONING CHECK")
    print("=" * 60)
    print()
    
    # Get nested result if present
    if "result" in result:
        result = result["result"]
    
    if not result.get("success", False):
        print(f"❌ Check failed: {result.get('error', 'Unknown error')}")
        return
    
    node = result.get("node", {})
    reachable = result.get("reachable", False)
    stdout = result.get("stdout", "")
    latency = result.get("latency_ms", 0)
    
    print(f"Node: {node.get('name', 'Unknown')}")
    print(f"Host: {node.get('host', 'Unknown')}")
    print(f"User: {node.get('user', 'Unknown')}")
    print(f"Port: {node.get('ssh_port', 22)}")
    print(f"Tags: {', '.join(node.get('tags', [])) or 'None'}")
    print(f"Active: {'Yes' if node.get('is_active') else 'No'}")
    print()
    
    if reachable:
        print(f"✅ SSH CONNECTIVITY: Reachable (latency: {latency}ms)")
    else:
        print(f"❌ SSH CONNECTIVITY: Unreachable")
        print(f"   Error: {result.get('error', 'Unknown')}")
        print()
        return
    
    print()
    print("-" * 60)
    print("SYSTEM INFORMATION")
    print("-" * 60)
    print()
    print(stdout)
    
    # Parse and show checklist
    print()
    print("-" * 60)
    print("PROVISIONING CHECKLIST")
    print("-" * 60)
    print()
    
    checks = [
        ("SSH connectivity", reachable),
        ("Python 3 installed", "Python" in stdout and "not found" not in stdout.lower()),
        ("/opt/jexida-jobs exists", "/opt/jexida-jobs" in stdout and "does not exist" not in stdout),
        ("/var/log/jexida-jobs exists", "/var/log/jexida-jobs" in stdout and "does not exist" not in stdout),
    ]
    
    all_passed = True
    for check_name, passed in checks:
        status = "✅" if passed else "❌"
        print(f"  {status} {check_name}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("✅ Node is fully provisioned and ready for jobs!")
    else:
        print("⚠️  Some checks failed. See docs/worker_nodes.md for setup instructions.")


def main():
    if len(sys.argv) < 2:
        # List available nodes
        print("Usage: python scripts/provision_node.py <node_name>")
        print()
        print("Available nodes:")
        result = list_nodes()
        
        if "result" in result:
            result = result["result"]
        
        nodes = result.get("nodes", [])
        if not nodes:
            print("  (no nodes configured)")
        else:
            for node in nodes:
                status = "active" if node.get("is_active") else "inactive"
                print(f"  - {node.get('name')} ({node.get('host')}) [{status}]")
        
        sys.exit(0)
    
    node_name = sys.argv[1]
    print(f"Checking worker node: {node_name}...")
    
    result = check_node(node_name)
    print_check_result(result)


if __name__ == "__main__":
    main()

