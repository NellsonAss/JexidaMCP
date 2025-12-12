"""UniFi network management tools package.

Contains MCP tools for managing and hardening UniFi networks:
- Controller tools: get_config, backup, restore
- Device discovery: list_devices, network_scan, topology
- Security: comprehensive audit, hardening, monitoring
- Management: VLAN, WiFi, Firewall create/update
- SSH tools: device diagnostics and adoption
- Config management: export, diff, drift_monitor

Security Hardening Checklist (9 Sections):
- Section 1: VLAN & Network Architecture
- Section 2: WiFi Hardening
- Section 3: Firewall Hardening
- Section 4: Threat Management (IDS/IPS)
- Section 5: DNS/DHCP Protection
- Section 6: Switch, PoE, & AP Hardening
- Section 7: Remote Access & Admin Hardening
- Section 8: Backups & Drift Protection
- Section 9: Audit Output Format
"""

# Import tools to trigger registration
from . import devices
from . import clients
from . import security
from . import changes
from . import network_scan
from . import audit
from . import hardening
from . import controller
from . import topology
from . import monitoring
from . import vlan_mgmt
from . import wifi_mgmt
from . import firewall_mgmt
from . import ssh_tools
from . import config_mgmt

# Import new comprehensive security tools
from . import security_audit
from . import security_harden

# Import client for external use
from .client import (
    UniFiClient,
    UniFiAuthError,
    UniFiConnectionError,
    UniFiAPIError,
    UniFiDevice,
)

# Import main security functions for direct access
from .security_audit import security_audit_unifi, SecurityAuditUniFiInput, SecurityAuditUniFiOutput
from .security_harden import security_harden_unifi, SecurityHardenUniFiInput, SecurityHardenUniFiOutput

__all__ = [
    # Tools modules
    "devices",
    "clients",
    "security",
    "changes",
    "network_scan",
    "audit",
    "hardening",
    "controller",
    "topology",
    "monitoring",
    "vlan_mgmt",
    "wifi_mgmt",
    "firewall_mgmt",
    "ssh_tools",
    "config_mgmt",
    "security_audit",
    "security_harden",
    # Client classes
    "UniFiClient",
    "UniFiAuthError",
    "UniFiConnectionError",
    "UniFiAPIError",
    "UniFiDevice",
    # Main security functions
    "security_audit_unifi",
    "SecurityAuditUniFiInput",
    "SecurityAuditUniFiOutput",
    "security_harden_unifi",
    "SecurityHardenUniFiInput",
    "SecurityHardenUniFiOutput",
]

