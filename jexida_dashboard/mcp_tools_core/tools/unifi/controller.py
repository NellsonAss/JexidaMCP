"""UniFi Controller Management Tools.

Provides tools for:
- unifi_controller_get_config: Retrieve full controller configuration
- unifi_controller_backup: Create timestamped backups
- unifi_controller_restore: Restore from backup

These tools manage network-wide settings and require access to the UniFi Dream Machine.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .client import UniFiClient, UniFiConnectionError, UniFiAuthError, UniFiAPIError

import logging
logger = logging.getLogger(__name__)


# =============================================================================
# unifi_controller_get_config - Retrieve controller configuration
# =============================================================================

class UniFiControllerGetConfigInput(BaseModel):
    """Input schema for unifi_controller_get_config tool."""
    
    scope: Literal["all", "networks", "wlans", "firewall", "devices", "vlans", "settings"] = Field(
        default="all",
        description="Configuration scope: all, networks, wlans, firewall, devices, vlans, or settings"
    )
    site_id: Optional[str] = Field(
        default=None,
        description="UniFi site ID (defaults to configured site)"
    )


class NetworkConfig(BaseModel):
    """Network/VLAN configuration."""
    id: str
    name: str
    purpose: str
    vlan_enabled: bool
    vlan_id: Optional[int] = None
    subnet: str
    dhcp_enabled: bool
    dhcp_start: str = ""
    dhcp_stop: str = ""


class WlanConfig(BaseModel):
    """WiFi network configuration."""
    id: str
    name: str
    enabled: bool
    security: str
    wpa_mode: str
    wpa3_support: bool
    is_guest: bool
    vlan_enabled: bool
    vlan: str = ""
    hidden: bool
    client_isolation: bool
    pmf_mode: str


class FirewallRuleConfig(BaseModel):
    """Firewall rule configuration."""
    id: str
    name: str
    enabled: bool
    action: str
    protocol: str
    ruleset: str
    rule_index: int


class DeviceConfig(BaseModel):
    """UniFi device configuration."""
    mac: str
    name: str
    model: str
    device_type: str
    ip: str
    firmware: str
    adopted: bool
    upgradable: bool = False


class ControllerSettings(BaseModel):
    """Controller settings summary."""
    upnp_enabled: bool = False
    upnp_nat_pmp_enabled: bool = False
    ids_ips_enabled: bool = False
    ids_ips_mode: str = ""
    dpi_enabled: bool = False
    dns_filtering_enabled: bool = False
    ssh_enabled: bool = False
    cloud_access_enabled: bool = False


class UniFiControllerGetConfigOutput(BaseModel):
    """Output schema for unifi_controller_get_config tool."""
    
    success: bool = Field(description="Whether the operation succeeded")
    scope: str = Field(description="Configuration scope that was retrieved")
    networks: List[NetworkConfig] = Field(default_factory=list)
    wlans: List[WlanConfig] = Field(default_factory=list)
    firewall_rules: List[FirewallRuleConfig] = Field(default_factory=list)
    devices: List[DeviceConfig] = Field(default_factory=list)
    settings: Optional[ControllerSettings] = None
    raw_settings: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Raw settings when scope is 'settings' for detailed inspection"
    )
    error: str = Field(default="", description="Error message if failed")


async def unifi_controller_get_config(
    params: UniFiControllerGetConfigInput
) -> UniFiControllerGetConfigOutput:
    """Retrieve UniFi controller configuration.
    
    Returns network-wide configuration including:
    - Networks and VLANs
    - WiFi SSIDs with security settings
    - Firewall rules
    - Device inventory
    - Controller settings (UPnP, IDS/IPS, DPI, etc.)
    
    Args:
        params: Input parameters with scope and optional site_id
        
    Returns:
        Controller configuration based on requested scope
    """
    logger.info(f"unifi_controller_get_config called with scope={params.scope}")
    
    try:
        async with UniFiClient(site=params.site_id) as client:
            output = UniFiControllerGetConfigOutput(
                success=True,
                scope=params.scope,
            )
            
            # Fetch based on scope
            fetch_all = params.scope == "all"
            
            # Networks / VLANs
            if fetch_all or params.scope in ("networks", "vlans"):
                networks_data = await client.get_networks()
                output.networks = [
                    NetworkConfig(
                        id=n.get("_id", ""),
                        name=n.get("name", ""),
                        purpose=n.get("purpose", ""),
                        vlan_enabled=n.get("vlan_enabled", False),
                        vlan_id=int(n["vlan"]) if n.get("vlan") else None,
                        subnet=n.get("subnet", ""),
                        dhcp_enabled=n.get("dhcp_enabled", False),
                        dhcp_start=n.get("dhcp_start", ""),
                        dhcp_stop=n.get("dhcp_stop", ""),
                    )
                    for n in networks_data
                ]
            
            # WLANs
            if fetch_all or params.scope == "wlans":
                wlans_data = await client.get_wlans()
                output.wlans = [
                    WlanConfig(
                        id=w.get("_id", ""),
                        name=w.get("name", ""),
                        enabled=w.get("enabled", False),
                        security=w.get("security", "open"),
                        wpa_mode=w.get("wpa_mode", ""),
                        wpa3_support=w.get("wpa3_support", False),
                        is_guest=w.get("is_guest", False),
                        vlan_enabled=w.get("vlan_enabled", False),
                        vlan=str(w.get("vlan", "")),
                        hidden=w.get("hide_ssid", False),
                        client_isolation=w.get("l2_isolation", False),
                        pmf_mode=w.get("pmf_mode", "disabled"),
                    )
                    for w in wlans_data
                ]
            
            # Firewall
            if fetch_all or params.scope == "firewall":
                firewall_data = await client.get_firewall_rules()
                rules = []
                for ruleset_name, ruleset_rules in firewall_data.items():
                    for rule in ruleset_rules:
                        rules.append(FirewallRuleConfig(
                            id=rule.get("_id", ""),
                            name=rule.get("name", ""),
                            enabled=rule.get("enabled", True),
                            action=rule.get("action", ""),
                            protocol=rule.get("protocol", "all"),
                            ruleset=ruleset_name,
                            rule_index=rule.get("rule_index", 0),
                        ))
                output.firewall_rules = rules
            
            # Devices
            if fetch_all or params.scope == "devices":
                devices_data = await client.get_devices()
                output.devices = [
                    DeviceConfig(
                        mac=d.mac,
                        name=d.name,
                        model=d.model,
                        device_type=d.device_type,
                        ip=d.ip,
                        firmware=d.firmware,
                        adopted=d.adopted,
                    )
                    for d in devices_data
                ]
            
            # Settings
            if fetch_all or params.scope == "settings":
                upnp = await client.get_upnp_settings()
                mgmt = await client.get_mgmt_settings()
                threat = await client.get_threat_management_settings()
                dpi = await client.get_dpi_settings()
                
                output.settings = ControllerSettings(
                    upnp_enabled=upnp.get("upnp_enabled", False),
                    upnp_nat_pmp_enabled=upnp.get("upnp_nat_pmp_enabled", False),
                    ids_ips_enabled=threat.get("ips_enabled", False),
                    ids_ips_mode=threat.get("ips_mode", "disabled"),
                    dpi_enabled=dpi.get("dpi_enabled", False),
                    dns_filtering_enabled=threat.get("dns_filtering_enabled", False),
                    ssh_enabled=mgmt.get("remote_access_enabled", False),
                    cloud_access_enabled=mgmt.get("unifi_remote_access_enabled", False),
                )
                
                # Include raw settings for detailed scope
                if params.scope == "settings":
                    raw_settings = await client.get_settings()
                    # Sanitize for JSON serialization
                    output.raw_settings = {
                        k: v for k, v in raw_settings.items()
                        if isinstance(v, (dict, list, str, int, float, bool, type(None)))
                    }
            
            logger.info(f"Retrieved config: {len(output.networks)} networks, "
                       f"{len(output.wlans)} wlans, {len(output.firewall_rules)} rules, "
                       f"{len(output.devices)} devices")
            
            return output
            
    except UniFiConnectionError as e:
        logger.error(f"Connection error: {e}")
        return UniFiControllerGetConfigOutput(success=False, scope=params.scope, error=f"Connection error: {e}")
    except UniFiAuthError as e:
        logger.error(f"Auth error: {e}")
        return UniFiControllerGetConfigOutput(success=False, scope=params.scope, error=f"Authentication error: {e}")
    except UniFiAPIError as e:
        logger.error(f"API error: {e}")
        return UniFiControllerGetConfigOutput(success=False, scope=params.scope, error=f"API error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return UniFiControllerGetConfigOutput(success=False, scope=params.scope, error=f"Unexpected error: {e}")


# =============================================================================
# unifi_controller_backup - Create controller backup
# =============================================================================

class UniFiControllerBackupInput(BaseModel):
    """Input schema for unifi_controller_backup tool."""
    
    label: Literal["pre-hardening", "pre-change", "manual", "scheduled"] = Field(
        default="manual",
        description="Backup label/reason"
    )
    site_id: Optional[str] = Field(
        default=None,
        description="UniFi site ID (defaults to configured site)"
    )


class UniFiControllerBackupOutput(BaseModel):
    """Output schema for unifi_controller_backup tool."""
    
    success: bool = Field(description="Whether the backup was created")
    backup_id: str = Field(default="", description="Backup identifier")
    label: str = Field(default="", description="Backup label")
    created_at: str = Field(default="", description="Backup creation timestamp")
    message: str = Field(default="", description="Status message")
    error: str = Field(default="", description="Error message if failed")


async def unifi_controller_backup(
    params: UniFiControllerBackupInput
) -> UniFiControllerBackupOutput:
    """Create a timestamped controller backup.
    
    Backups are stored on the UniFi controller and can be restored later.
    Always create a backup before making significant changes.
    
    Args:
        params: Input parameters with label and optional site_id
        
    Returns:
        Backup creation result with backup_id
    """
    logger.info(f"unifi_controller_backup called with label={params.label}")
    
    try:
        async with UniFiClient(site=params.site_id) as client:
            result = await client.create_backup(label=params.label)
            
            timestamp = datetime.now().isoformat()
            
            return UniFiControllerBackupOutput(
                success=True,
                backup_id=result.get("backup_id", ""),
                label=params.label,
                created_at=result.get("created_at", timestamp),
                message=f"Backup created successfully with label '{params.label}'",
            )
            
    except UniFiConnectionError as e:
        logger.error(f"Connection error: {e}")
        return UniFiControllerBackupOutput(success=False, error=f"Connection error: {e}")
    except UniFiAuthError as e:
        logger.error(f"Auth error: {e}")
        return UniFiControllerBackupOutput(success=False, error=f"Authentication error: {e}")
    except UniFiAPIError as e:
        logger.error(f"API error: {e}")
        return UniFiControllerBackupOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return UniFiControllerBackupOutput(success=False, error=f"Unexpected error: {e}")


# =============================================================================
# unifi_controller_list_backups - List available backups
# =============================================================================

class UniFiControllerListBackupsInput(BaseModel):
    """Input schema for unifi_controller_list_backups tool."""
    
    site_id: Optional[str] = Field(
        default=None,
        description="UniFi site ID (defaults to configured site)"
    )


class BackupInfo(BaseModel):
    """Backup metadata."""
    id: str
    name: str
    datetime: str
    size: int
    version: str


class UniFiControllerListBackupsOutput(BaseModel):
    """Output schema for unifi_controller_list_backups tool."""
    
    success: bool = Field(description="Whether the operation succeeded")
    backups: List[BackupInfo] = Field(default_factory=list)
    count: int = Field(default=0, description="Number of backups available")
    error: str = Field(default="", description="Error message if failed")


async def unifi_controller_list_backups(
    params: UniFiControllerListBackupsInput
) -> UniFiControllerListBackupsOutput:
    """List all available controller backups.
    
    Returns:
        List of backup metadata with IDs for restore operations
    """
    logger.info("unifi_controller_list_backups called")
    
    try:
        async with UniFiClient(site=params.site_id) as client:
            backups_data = await client.list_backups()
            
            backups = [
                BackupInfo(
                    id=b.get("_id", ""),
                    name=b.get("name", ""),
                    datetime=b.get("datetime", ""),
                    size=b.get("size", 0),
                    version=b.get("version", ""),
                )
                for b in backups_data
            ]
            
            return UniFiControllerListBackupsOutput(
                success=True,
                backups=backups,
                count=len(backups),
            )
            
    except UniFiConnectionError as e:
        return UniFiControllerListBackupsOutput(success=False, error=f"Connection error: {e}")
    except UniFiAuthError as e:
        return UniFiControllerListBackupsOutput(success=False, error=f"Authentication error: {e}")
    except UniFiAPIError as e:
        return UniFiControllerListBackupsOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        return UniFiControllerListBackupsOutput(success=False, error=f"Unexpected error: {e}")


# =============================================================================
# unifi_controller_restore - Restore from backup
# =============================================================================

class UniFiControllerRestoreInput(BaseModel):
    """Input schema for unifi_controller_restore tool."""
    
    backup_id: str = Field(
        description="ID of the backup to restore (from list_backups)"
    )
    confirmation_token: str = Field(
        description="Confirmation token: must be 'CONFIRM_RESTORE' to proceed"
    )
    site_id: Optional[str] = Field(
        default=None,
        description="UniFi site ID (defaults to configured site)"
    )


class UniFiControllerRestoreOutput(BaseModel):
    """Output schema for unifi_controller_restore tool."""
    
    success: bool = Field(description="Whether the restore was initiated")
    backup_id: str = Field(default="", description="Backup ID that was restored")
    message: str = Field(default="", description="Status message")
    warning: str = Field(
        default="Controller will restart. All services may be briefly unavailable.",
        description="Important warning about the restore operation"
    )
    error: str = Field(default="", description="Error message if failed")


async def unifi_controller_restore(
    params: UniFiControllerRestoreInput
) -> UniFiControllerRestoreOutput:
    """Restore a controller backup.
    
    ⚠️ WARNING: This operation will restart the controller and may cause
    brief service interruptions. All current configuration will be replaced
    with the backup contents.
    
    Requires confirmation_token="CONFIRM_RESTORE" to proceed.
    
    Args:
        params: Input parameters with backup_id and confirmation token
        
    Returns:
        Restore operation result
    """
    logger.info(f"unifi_controller_restore called for backup_id={params.backup_id}")
    
    # Safety check
    if params.confirmation_token != "CONFIRM_RESTORE":
        return UniFiControllerRestoreOutput(
            success=False,
            backup_id=params.backup_id,
            error="Invalid confirmation token. Set confirmation_token='CONFIRM_RESTORE' to proceed.",
        )
    
    try:
        async with UniFiClient(site=params.site_id) as client:
            result = await client.restore_backup(params.backup_id)
            
            return UniFiControllerRestoreOutput(
                success=True,
                backup_id=params.backup_id,
                message="Backup restoration initiated. Controller will restart.",
            )
            
    except UniFiConnectionError as e:
        return UniFiControllerRestoreOutput(
            success=False, backup_id=params.backup_id, error=f"Connection error: {e}"
        )
    except UniFiAuthError as e:
        return UniFiControllerRestoreOutput(
            success=False, backup_id=params.backup_id, error=f"Authentication error: {e}"
        )
    except UniFiAPIError as e:
        return UniFiControllerRestoreOutput(
            success=False, backup_id=params.backup_id, error=f"API error: {e}"
        )
    except Exception as e:
        return UniFiControllerRestoreOutput(
            success=False, backup_id=params.backup_id, error=f"Unexpected error: {e}"
        )

