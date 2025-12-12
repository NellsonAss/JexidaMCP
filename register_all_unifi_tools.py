#!/usr/bin/env python3
"""Register all UniFi tools via MCP API.

This script registers all UniFi tools created for Phase 1 using the register_mcp_tool API endpoint.
Run this after deploying the tool code to the server.

Usage:
    python register_all_unifi_tools.py [--api-url http://192.168.1.224:8080]
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
    """Register a tool via the MCP API."""
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
    parser = argparse.ArgumentParser(description="Register all UniFi tools via MCP API")
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
        from mcp_tools_core.tools.unifi.topology import (
            UniFiNetworkTopologyInput,
        )
        from mcp_tools_core.tools.unifi.monitoring import (
            SecurityMonitorUnifiInput,
        )
        from mcp_tools_core.tools.unifi.vlan_mgmt import (
            UniFiVlanCreateInput,
            UniFiVlanUpdateInput,
        )
        from mcp_tools_core.tools.unifi.wifi_mgmt import (
            UniFiWifiCreateInput,
            UniFiWifiUpdateInput,
        )
        from mcp_tools_core.tools.unifi.firewall_mgmt import (
            UniFiFirewallCreateRuleInput,
            UniFiFirewallUpdateRuleInput,
            UniFiFirewallValidateInput,
        )
        from mcp_tools_core.tools.unifi.ssh_tools import (
            SSHUnifiDeviceRunInput,
            SSHUnifiDeviceInfoInput,
            SSHUnifiDeviceAdoptInput,
        )
        from mcp_tools_core.tools.unifi.config_mgmt import (
            UniFiConfigExportInput,
            UniFiConfigDiffInput,
            UniFiConfigDriftMonitorInput,
        )
    except ImportError as e:
        print(f"Error importing models: {e}")
        print("Make sure you're running from the project root and dependencies are installed.")
        sys.exit(1)
    
    # Define all tools to register
    tools = [
        # Controller tools
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
        # Topology
        {
            "name": "unifi_network_topology",
            "description": "Build a graph representation of the network including switch-to-AP connections, port usage, VLAN assignments, and PoE state",
            "handler_path": "mcp_tools_core.tools.unifi.topology.unifi_network_topology",
            "tags": "unifi,network,topology",
            "input_model": UniFiNetworkTopologyInput,
        },
        # Security monitoring
        {
            "name": "security_monitor_unifi",
            "description": "Real-time or periodic monitoring of security events including unauthorized device joins, rogue APs, port state changes, authentication failures, and WAN attacks/IPS alerts",
            "handler_path": "mcp_tools_core.tools.unifi.monitoring.security_monitor_unifi",
            "tags": "unifi,security,monitoring",
            "input_model": SecurityMonitorUnifiInput,
        },
        # VLAN management
        {
            "name": "unifi_vlan_create",
            "description": "Create a new VLAN/network with subnet validation and DHCP pool configuration",
            "handler_path": "mcp_tools_core.tools.unifi.vlan_mgmt.unifi_vlan_create",
            "tags": "unifi,vlan,network",
            "input_model": UniFiVlanCreateInput,
        },
        {
            "name": "unifi_vlan_update",
            "description": "Update VLAN/network configuration including DHCP settings and subnet",
            "handler_path": "mcp_tools_core.tools.unifi.vlan_mgmt.unifi_vlan_update",
            "tags": "unifi,vlan,network",
            "input_model": UniFiVlanUpdateInput,
        },
        # WiFi management
        {
            "name": "unifi_wifi_create",
            "description": "Create a new WiFi network/SSID with security settings, VLAN assignment, and guest network options",
            "handler_path": "mcp_tools_core.tools.unifi.wifi_mgmt.unifi_wifi_create",
            "tags": "unifi,wifi,wlan",
            "input_model": UniFiWifiCreateInput,
        },
        {
            "name": "unifi_wifi_update",
            "description": "Update WiFi network configuration including password, VLAN, security mode, PMF, and legacy 2.4 GHz settings",
            "handler_path": "mcp_tools_core.tools.unifi.wifi_mgmt.unifi_wifi_update",
            "tags": "unifi,wifi,wlan",
            "input_model": UniFiWifiUpdateInput,
        },
        # Firewall management
        {
            "name": "unifi_firewall_create_rule",
            "description": "Create a new firewall rule with source/destination networks, protocol, and port specifications",
            "handler_path": "mcp_tools_core.tools.unifi.firewall_mgmt.unifi_firewall_create_rule",
            "tags": "unifi,firewall,security",
            "input_model": UniFiFirewallCreateRuleInput,
        },
        {
            "name": "unifi_firewall_update_rule",
            "description": "Update existing firewall rule configuration safely",
            "handler_path": "mcp_tools_core.tools.unifi.firewall_mgmt.unifi_firewall_update_rule",
            "tags": "unifi,firewall,security",
            "input_model": UniFiFirewallUpdateRuleInput,
        },
        {
            "name": "unifi_firewall_validate",
            "description": "Validate firewall rules for issues including rule reordering, redundancy, broken segmentation, and guest network isolation failures",
            "handler_path": "mcp_tools_core.tools.unifi.firewall_mgmt.unifi_firewall_validate",
            "tags": "unifi,firewall,security,validation",
            "input_model": UniFiFirewallValidateInput,
        },
        # SSH tools
        {
            "name": "ssh_unifi_device_run",
            "description": "Run arbitrary SSH commands on UniFi devices for troubleshooting, firmware checks, and deep metrics gathering",
            "handler_path": "mcp_tools_core.tools.unifi.ssh_tools.ssh_unifi_device_run",
            "tags": "unifi,ssh,device",
            "input_model": SSHUnifiDeviceRunInput,
        },
        {
            "name": "ssh_unifi_device_info",
            "description": "Run predefined safe diagnostic commands to collect CPU, memory, radio status, PoE power, firmware, and uptime information",
            "handler_path": "mcp_tools_core.tools.unifi.ssh_tools.ssh_unifi_device_info",
            "tags": "unifi,ssh,device,diagnostics",
            "input_model": SSHUnifiDeviceInfoInput,
        },
        {
            "name": "ssh_unifi_device_adopt",
            "description": "Force device adoption via SSH by running set-inform command. Used for adoption issues when devices won't adopt through the UI.",
            "handler_path": "mcp_tools_core.tools.unifi.ssh_tools.ssh_unifi_device_adopt",
            "tags": "unifi,ssh,device,adoption",
            "input_model": SSHUnifiDeviceAdoptInput,
        },
        # Config management
        {
            "name": "unifi_config_export",
            "description": "Export controller configuration in JSON + diff-friendly format",
            "handler_path": "mcp_tools_core.tools.unifi.config_mgmt.unifi_config_export",
            "tags": "unifi,config,export",
            "input_model": UniFiConfigExportInput,
        },
        {
            "name": "unifi_config_diff",
            "description": "Compare two configurations or current config vs backup and return structured differences",
            "handler_path": "mcp_tools_core.tools.unifi.config_mgmt.unifi_config_diff",
            "tags": "unifi,config,diff",
            "input_model": UniFiConfigDiffInput,
        },
        {
            "name": "unifi_config_drift_monitor",
            "description": "Monitor for configuration drift outside automation. Compares current configuration to baseline and alerts if unauthorized changes detected",
            "handler_path": "mcp_tools_core.tools.unifi.config_mgmt.unifi_config_drift_monitor",
            "tags": "unifi,config,drift,monitoring",
            "input_model": UniFiConfigDriftMonitorInput,
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
    print(f"\n{'='*60}")
    print(f"Registered {success_count}/{len(results)} tools")
    print(f"{'='*60}")
    
    if success_count < len(results):
        print("\nFailed registrations:")
        for name, result in results:
            if not result.get("success"):
                print(f"  - {name}: {result.get('error', 'Unknown error')}")
        sys.exit(1)
    else:
        print("\nAll tools registered successfully!")
        print("\nNext step: Restart the service if needed:")
        print("  ssh jexida@192.168.1.224 'sudo systemctl restart jexida-mcp.service'")


if __name__ == "__main__":
    main()

