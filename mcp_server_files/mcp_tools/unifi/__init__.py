"""UniFi network management tools package.

Contains MCP tools for managing and hardening UniFi networks:
- unifi_list_devices: Inventory all UniFi devices
- unifi_get_security_settings: Get security configuration
- unifi_apply_changes: Apply configuration changes with dry-run support
- network_scan_local: Run nmap scans from MCP server
- network_hardening_audit: Audit configuration against security policy
- network_apply_hardening_plan: Apply hardening recommendations in phases
"""

# Import tools to trigger registration
from . import devices
from . import security
from . import changes
from . import network_scan
from . import audit
from . import hardening

# Import client for external use
from .client import (
    UniFiClient,
    UniFiAuthError,
    UniFiConnectionError,
    UniFiAPIError,
    UniFiDevice,
)

__all__ = [
    # Tools modules
    "devices",
    "security",
    "changes",
    "network_scan",
    "audit",
    "hardening",
    # Client classes
    "UniFiClient",
    "UniFiAuthError",
    "UniFiConnectionError",
    "UniFiAPIError",
    "UniFiDevice",
]

