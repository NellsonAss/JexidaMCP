"""Store UniFi Security Tools documentation in MCP Knowledge Base.

This script stores comprehensive documentation about the security audit
and hardening tools in the MCP knowledge base for LLM reference.
"""

import json
import sys

try:
    import httpx
except ImportError:
    print("httpx not installed. Run: pip install httpx")
    sys.exit(1)


API_URL = "http://192.168.1.224:8080"


def store_knowledge(key: str, value: dict, source: str = "tool_documentation") -> dict:
    """Store knowledge via the MCP API."""
    payload = {
        "key": key,
        "value": value,
        "source": source,
    }
    
    url = f"{API_URL}/tools/api/tools/store_mcp_knowledge/run/"
    
    try:
        response = httpx.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Knowledge Documents
# =============================================================================

KNOWLEDGE_ITEMS = [
    {
        "key": "unifi.security.audit.overview",
        "value": {
            "title": "UniFi Security Audit Tool Overview",
            "description": "Comprehensive security audit for UniFi networks with finding codes and risk scoring",
            "tool_name": "security_audit_unifi",
            "handler": "mcp_tools_core.tools.unifi.security_audit.security_audit_unifi",
            "features": [
                "8 security sections evaluated (VLAN, WiFi, Firewall, IDS/IPS, DNS/DHCP, Switch/AP, Remote Access, Backups)",
                "Stable finding codes for machine-actionable mapping",
                "Risk scoring 0-100 with letter grades (A+ to F)",
                "Policy profiles: baseline, paranoid, lab",
                "Network summary with VLAN/SSID/firewall counts",
                "Patches marked with auto_apply_safe flag",
            ],
            "usage_example": {
                "quick_audit": {"depth": "quick", "profile": "baseline"},
                "full_paranoid": {"depth": "full", "profile": "paranoid"},
                "lab_mode": {"depth": "full", "profile": "lab"},
            },
        },
    },
    {
        "key": "unifi.security.finding_codes",
        "value": {
            "title": "UniFi Security Finding Codes Reference",
            "description": "Complete list of stable finding codes for machine-actionable patch mapping",
            "codes": {
                "VLAN_Architecture": [
                    "MISSING_NETWORK_SEGMENTATION - Required VLANs not found",
                    "GUEST_NOT_ISOLATED - Guest network not properly isolated",
                    "IOT_CAN_REACH_LAN - IoT VLAN can access LAN",
                    "GUEST_CAN_REACH_LAN - Guest VLAN can access LAN",
                    "CAMERAS_CAN_REACH_LAN - Camera VLAN can access LAN",
                ],
                "WiFi": [
                    "OPEN_WIFI - WiFi network has no encryption",
                    "NO_WPA3 - WPA3 not enabled",
                    "NO_PMF - Protected Management Frames not enabled",
                    "IOT_WIFI_NO_VLAN - IoT WiFi not on dedicated VLAN",
                    "WEAK_WIFI_SECURITY - Weak encryption (WPA1)",
                    "GUEST_NO_CLIENT_ISOLATION - Guest lacks client isolation",
                ],
                "Firewall": [
                    "MISSING_DENY_IOT_TO_LAN - No deny rule for IoT → LAN",
                    "MISSING_DENY_GUEST_TO_LAN - No deny rule for Guest → LAN",
                    "MISSING_DENY_CAMERAS_TO_LAN - No deny rule for Cameras → LAN",
                    "OVERLY_PERMISSIVE_RULE - Accept-all rule detected",
                    "SHADOWED_RULE - Rule shadowed by earlier rule",
                ],
                "Threat_Management": [
                    "IDS_DISABLED - IDS/IPS completely disabled",
                    "IPS_NOT_ENABLED - IDS mode but IPS recommended",
                    "THREAT_CATEGORIES_MISSING - Key threat categories disabled",
                ],
                "DNS_DHCP": [
                    "UPNP_ENABLED - UPnP is enabled (security risk)",
                    "NAT_PMP_ENABLED - NAT-PMP is enabled",
                    "UNTRUSTED_DNS - Non-trusted DNS servers",
                    "WIDE_DHCP_RANGE - DHCP pool too large",
                ],
                "Remote_Access": [
                    "SSH_ENABLED - SSH enabled on devices",
                    "SSH_PASSWORD_AUTH - Password auth enabled for SSH",
                    "CLOUD_ACCESS_ENABLED - UniFi cloud access enabled",
                    "WAN_UI_ENABLED - WAN UI access enabled",
                    "NO_MFA - MFA not enabled for admin",
                ],
                "Backups": [
                    "NO_RECENT_BACKUP - No recent backup found",
                    "CONFIG_DRIFT - Configuration drift detected",
                ],
            },
        },
    },
    {
        "key": "unifi.security.harden.overview",
        "value": {
            "title": "UniFi Security Hardening Tool Overview",
            "description": "Apply security patches from audit with filtering and safety controls",
            "tool_name": "security_harden_unifi",
            "handler": "mcp_tools_core.tools.unifi.security_harden.security_harden_unifi",
            "features": [
                "Generates patches from stable finding codes",
                "Filter by severity: critical, high, medium, low",
                "Filter by area: vlan, wifi, firewall, dns_dhcp, remote, settings",
                "apply_auto_safe_only for conservative hardening",
                "Phased rollout with connectivity checks",
                "Automatic backup before changes",
                "Dry-run mode for preview",
            ],
            "phases": {
                "1": "Low-risk changes (UPnP, PMF, client isolation)",
                "2": "Firewall rules (deny rules for VLAN isolation)",
                "3": "VLAN and network segmentation (high impact)",
            },
            "safety_requirements": {
                "dry_run": "Default true - preview only",
                "confirmation_token": "Set to 'CONFIRM_HARDEN' to apply",
                "auto_apply_safe": "Only patches marked safe are auto-applied",
            },
        },
    },
    {
        "key": "unifi.security.profiles",
        "value": {
            "title": "UniFi Security Policy Profiles",
            "description": "Pre-configured security profiles for different use cases",
            "profiles": {
                "baseline": {
                    "name": "Baseline",
                    "description": "Balanced security for home/small office",
                    "characteristics": [
                        "Cloud access allowed (low severity)",
                        "WPA3 recommended but not required",
                        "Standard auto-apply threshold",
                    ],
                    "use_case": "Most home and small business networks",
                },
                "paranoid": {
                    "name": "Paranoid",
                    "description": "Maximum security for high-risk environments",
                    "characteristics": [
                        "Cloud access flagged as high severity",
                        "WPA3 required (high severity)",
                        "SSH flagged as high severity",
                        "More aggressive auto-apply",
                    ],
                    "use_case": "High-security environments, sensitive data",
                },
                "lab": {
                    "name": "Lab/Development",
                    "description": "Minimal restrictions for testing",
                    "characteristics": [
                        "UPnP findings are low severity",
                        "SSH allowed without warnings",
                        "Only critical issues flagged",
                    ],
                    "use_case": "Development, testing, lab environments",
                },
            },
        },
    },
    {
        "key": "unifi.security.workflow",
        "value": {
            "title": "UniFi Security Hardening Workflow",
            "description": "Recommended workflow for security auditing and hardening",
            "steps": [
                {
                    "step": 1,
                    "action": "Run security audit",
                    "command": "security_audit_unifi depth='full' profile='baseline'",
                    "description": "Get comprehensive audit with findings and risk score",
                },
                {
                    "step": 2,
                    "action": "Review findings",
                    "description": "Review findings by severity and area, note risk score",
                },
                {
                    "step": 3,
                    "action": "Dry-run hardening",
                    "command": "security_harden_unifi dry_run=true apply_auto_safe_only=true",
                    "description": "Preview safe patches without applying",
                },
                {
                    "step": 4,
                    "action": "Apply Phase 1 (low-risk)",
                    "command": "security_harden_unifi dry_run=false phases=[1] confirmation_token='CONFIRM_HARDEN'",
                    "description": "Apply low-risk changes (UPnP, PMF, etc.)",
                },
                {
                    "step": 5,
                    "action": "Verify connectivity",
                    "description": "Test network connectivity after Phase 1",
                },
                {
                    "step": 6,
                    "action": "Apply Phase 2 (firewall)",
                    "command": "security_harden_unifi dry_run=false phases=[2] confirmation_token='CONFIRM_HARDEN'",
                    "description": "Apply firewall deny rules",
                },
                {
                    "step": 7,
                    "action": "Re-run audit",
                    "command": "security_audit_unifi depth='full'",
                    "description": "Verify improvements in risk score",
                },
            ],
            "tips": [
                "Always run dry-run first",
                "Apply phases incrementally",
                "Backups are created automatically",
                "Use apply_auto_safe_only for conservative approach",
                "Check connectivity between phases",
            ],
        },
    },
    {
        "key": "unifi.security.risk_scoring",
        "value": {
            "title": "UniFi Security Risk Scoring",
            "description": "How risk scores are calculated and interpreted",
            "scale": "0-100 (lower is better)",
            "weights": {
                "critical": 15,
                "high": 8,
                "medium": 3,
                "low": 1,
            },
            "grades": {
                "A+": {"range": "0-10", "rating": "excellent", "description": "No significant issues"},
                "A": {"range": "11-25", "rating": "good", "description": "Minor issues only"},
                "B": {"range": "26-40", "rating": "fair", "description": "Some hardening recommended"},
                "C": {"range": "41-60", "rating": "needs_work", "description": "Multiple issues to address"},
                "D": {"range": "61-80", "rating": "poor", "description": "Significant security gaps"},
                "F": {"range": "81-100", "rating": "critical", "description": "Major vulnerabilities"},
            },
        },
    },
]


def main():
    """Store all knowledge items."""
    print("Storing UniFi Security Tools Documentation...")
    print("=" * 60)
    
    results = []
    for item in KNOWLEDGE_ITEMS:
        print(f"\nStoring: {item['key']}")
        result = store_knowledge(
            key=item["key"],
            value=item["value"],
            source="tool_documentation",
        )
        results.append((item["key"], result))
        
        if result.get("success"):
            print(f"  ✓ Stored successfully")
        else:
            print(f"  ✗ Failed: {result.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 60)
    success_count = sum(1 for _, r in results if r.get("success"))
    print(f"Stored {success_count}/{len(results)} knowledge items")
    
    return success_count == len(results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

