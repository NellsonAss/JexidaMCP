"""Register UniFi Security Audit and Hardening Tools with MCP.

This script registers the enhanced security tools:
- security_audit_unifi: Comprehensive security audit with finding codes, risk scoring, and profiles
- security_harden_unifi: Apply hardening patches with filtering and auto-safe options

Run this script to register the tools via the MCP API.
"""

import json
import sys
from typing import Any, Dict

try:
    import httpx
except ImportError:
    print("httpx not installed. Run: pip install httpx")
    sys.exit(1)


API_URL = "http://192.168.1.224:8080"


def register_tool(
    name: str,
    description: str,
    handler_path: str,
    input_schema: Dict[str, Any],
    tags: str,
) -> Dict[str, Any]:
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
    
    url = f"{API_URL}/tools/api/tools/register_mcp_tool/run/"
    
    try:
        response = httpx.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Tool Definitions
# =============================================================================

SECURITY_AUDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "depth": {
            "type": "string",
            "description": "Audit depth: 'quick' for essential checks only, 'full' for comprehensive audit",
            "default": "full",
            "enum": ["quick", "full"]
        },
        "profile": {
            "type": "string",
            "description": "Security profile: 'baseline' (balanced), 'paranoid' (maximum), 'lab' (minimal)",
            "default": "baseline",
            "enum": ["baseline", "paranoid", "lab"]
        },
        "site_id": {
            "type": "string",
            "description": "UniFi site ID (defaults to configured site)"
        },
        "policy_path": {
            "type": "string",
            "description": "Path to custom security policy JSON file"
        },
        "include_patches": {
            "type": "boolean",
            "description": "Include recommended remediation patches in output",
            "default": True
        }
    },
    "required": []
}

SECURITY_HARDEN_SCHEMA = {
    "type": "object",
    "properties": {
        "dry_run": {
            "type": "boolean",
            "description": "If true, preview changes without applying (default: true for safety)",
            "default": True
        },
        "phases": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "Which phases to apply: 1=low-risk, 2=firewall, 3=vlan",
            "default": [1, 2, 3]
        },
        "include_severities": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Filter by finding severity: critical, high, medium, low",
            "default": ["critical", "high", "medium", "low"]
        },
        "include_areas": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Filter by area: vlan, wifi, firewall, dns_dhcp, remote, settings",
            "default": ["vlan", "wifi", "firewall", "dns_dhcp", "remote", "settings"]
        },
        "apply_auto_safe_only": {
            "type": "boolean",
            "description": "Only apply patches marked as auto_apply_safe=True (conservative mode)",
            "default": False
        },
        "profile": {
            "type": "string",
            "description": "Security profile for audit: baseline, paranoid, lab",
            "default": "baseline"
        },
        "stop_on_failure": {
            "type": "boolean",
            "description": "Stop if a phase fails",
            "default": True
        },
        "create_backup": {
            "type": "boolean",
            "description": "Create backup before applying changes",
            "default": True
        },
        "site_id": {
            "type": "string",
            "description": "UniFi site ID (defaults to configured site)"
        },
        "confirmation_token": {
            "type": "string",
            "description": "Set to 'CONFIRM_HARDEN' to apply changes (required when dry_run=false)"
        }
    },
    "required": []
}

TOOLS = [
    {
        "name": "security_audit_unifi",
        "description": """Comprehensive UniFi security audit with finding codes, risk scoring, and profiles.

Features:
- Evaluates 8 security sections (VLAN, WiFi, Firewall, IDS/IPS, DNS/DHCP, Switch/AP, Remote Access, Backups)
- Stable finding codes for machine-actionable patch mapping
- Risk scoring on 0-100 scale with letter grades (A+ to F)
- Policy profiles: baseline (balanced), paranoid (maximum), lab (minimal)
- Network summary with VLAN/SSID counts
- Patches marked as auto_apply_safe for safe automation

Finding codes include: OPEN_WIFI, UPNP_ENABLED, IDS_DISABLED, MISSING_DENY_IOT_TO_LAN, etc.
Use with security_harden_unifi to apply recommended patches.""",
        "handler_path": "mcp_tools_core.tools.unifi.security_audit.security_audit_unifi",
        "input_schema": SECURITY_AUDIT_SCHEMA,
        "tags": "unifi,security,audit,hardening",
    },
    {
        "name": "security_harden_unifi",
        "description": """Apply security hardening patches to UniFi network with filtering and safety controls.

Features:
- Runs audit and generates patches from stable finding codes
- Filter patches by severity (critical, high, medium, low)
- Filter patches by area (vlan, wifi, firewall, dns_dhcp, remote, settings)
- apply_auto_safe_only mode for conservative hardening
- Dry-run mode for previewing changes
- Phased rollout: Phase 1 (low-risk), Phase 2 (firewall), Phase 3 (VLAN)
- Automatic backup creation before changes
- Connectivity checks between phases

Safety:
- dry_run=true by default (preview only)
- Requires confirmation_token='CONFIRM_HARDEN' to apply changes
- Auto-safe patches are marked for safe automation""",
        "handler_path": "mcp_tools_core.tools.unifi.security_harden.security_harden_unifi",
        "input_schema": SECURITY_HARDEN_SCHEMA,
        "tags": "unifi,security,hardening,automation",
    },
]


def main():
    """Register all security tools."""
    print("Registering UniFi Security Tools...")
    print("=" * 60)
    
    results = []
    for tool in TOOLS:
        print(f"\nRegistering: {tool['name']}")
        result = register_tool(
            name=tool["name"],
            description=tool["description"],
            handler_path=tool["handler_path"],
            input_schema=tool["input_schema"],
            tags=tool["tags"],
        )
        results.append((tool["name"], result))
        
        if result.get("success"):
            print(f"  ✓ Registered successfully")
        else:
            print(f"  ✗ Failed: {result.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 60)
    success_count = sum(1 for _, r in results if r.get("success"))
    print(f"Registered {success_count}/{len(results)} tools")
    
    if success_count == len(results):
        print("\n✓ All tools registered! Restart the MCP service to load them:")
        print("  ssh jexida@192.168.1.224 'sudo systemctl restart jexida-mcp.service'")
    
    return success_count == len(results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

