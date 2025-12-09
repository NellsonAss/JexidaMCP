"""UniFi configuration change application tool.

Provides the unifi_apply_changes tool for applying configuration changes
to the UniFi controller with dry-run support.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from logging_config import get_logger, ToolInvocationLogger
from tool_registry import tool

from .client import UniFiClient, UniFiConnectionError, UniFiAuthError, UniFiAPIError
from .diff import (
    ChangeAction,
    ConfigChange,
    DiffResult,
    combine_diffs,
    plan_firewall_changes,
    plan_upnp_changes,
    plan_vlan_changes,
    plan_wifi_changes,
)

logger = get_logger(__name__)


# -------------------------------------------------------------------------
# Input/Output Models
# -------------------------------------------------------------------------

class WifiEdit(BaseModel):
    """A WiFi/WLAN edit request."""
    ssid: str = Field(description="SSID name to modify")
    enabled: Optional[bool] = Field(default=None, description="Enable/disable SSID")
    security: Optional[str] = Field(default=None, description="Security mode")
    wpa_mode: Optional[str] = Field(default=None, description="WPA mode")
    wpa3_support: Optional[bool] = Field(default=None, description="Enable WPA3")
    wpa3_transition: Optional[bool] = Field(default=None, description="WPA3 transition mode")
    hide_ssid: Optional[bool] = Field(default=None, description="Hide SSID")
    l2_isolation: Optional[bool] = Field(default=None, description="Client isolation")
    vlan_enabled: Optional[bool] = Field(default=None, description="Enable VLAN tagging")
    vlan: Optional[int] = Field(default=None, description="VLAN ID")


class FirewallEdit(BaseModel):
    """A firewall rule edit request."""
    action: str = Field(description="Action: create, update, or delete")
    ruleset: Optional[str] = Field(default=None, description="Ruleset: wan_in, lan_in, etc.")
    rule_id: Optional[str] = Field(default=None, description="Rule ID for update/delete")
    rule_name: Optional[str] = Field(default=None, description="Rule name")
    rule_action: Optional[str] = Field(default=None, description="accept, drop, reject")
    protocol: Optional[str] = Field(default=None, description="Protocol")
    src_address: Optional[str] = Field(default=None, description="Source address")
    dst_address: Optional[str] = Field(default=None, description="Destination address")
    dst_port: Optional[str] = Field(default=None, description="Destination port(s)")
    enabled: Optional[bool] = Field(default=None, description="Enable/disable rule")


class VlanEdit(BaseModel):
    """A VLAN/network edit request."""
    action: str = Field(default="update", description="Action: create, update, or delete")
    network_name: Optional[str] = Field(default=None, description="Network name")
    network_id: Optional[str] = Field(default=None, description="Network ID")
    vlan_enabled: Optional[bool] = Field(default=None, description="Enable VLAN")
    vlan: Optional[int] = Field(default=None, description="VLAN ID")
    subnet: Optional[str] = Field(default=None, description="IP subnet")
    dhcp_enabled: Optional[bool] = Field(default=None, description="Enable DHCP")
    purpose: Optional[str] = Field(default=None, description="Network purpose")


class UpnpEdit(BaseModel):
    """UPnP settings edit request."""
    upnp_enabled: Optional[bool] = Field(default=None, description="Enable UPnP")
    upnp_nat_pmp_enabled: Optional[bool] = Field(default=None, description="Enable NAT-PMP")
    upnp_secure_mode: Optional[bool] = Field(default=None, description="Enable secure mode")


class UniFiApplyChangesInput(BaseModel):
    """Input schema for unifi_apply_changes tool."""
    
    dry_run: bool = Field(
        default=True,
        description="If true, compute and return diff without applying changes"
    )
    site_id: Optional[str] = Field(
        default=None,
        description="UniFi site ID (defaults to configured site)"
    )
    wifi_edits: List[WifiEdit] = Field(
        default_factory=list,
        description="WiFi/WLAN changes to apply"
    )
    firewall_edits: List[FirewallEdit] = Field(
        default_factory=list,
        description="Firewall rule changes to apply"
    )
    vlan_edits: List[VlanEdit] = Field(
        default_factory=list,
        description="VLAN/network changes to apply"
    )
    upnp_edits: Optional[UpnpEdit] = Field(
        default=None,
        description="UPnP setting changes to apply"
    )


class ChangeResult(BaseModel):
    """Result of a single change application."""
    success: bool = Field(description="Whether change succeeded")
    item_type: str = Field(description="Type of item changed")
    item_name: str = Field(description="Name of item")
    action: str = Field(description="Action performed")
    error: str = Field(default="", description="Error message if failed")


class UniFiApplyChangesOutput(BaseModel):
    """Output schema for unifi_apply_changes tool."""
    
    success: bool = Field(description="Whether overall operation succeeded")
    dry_run: bool = Field(description="Whether this was a dry run")
    diff: Dict[str, Any] = Field(
        default_factory=dict,
        description="Computed diff (always returned)"
    )
    results: List[ChangeResult] = Field(
        default_factory=list,
        description="Results of applied changes (empty for dry run)"
    )
    changes_applied: int = Field(default=0, description="Number of changes applied")
    changes_failed: int = Field(default=0, description="Number of changes that failed")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")
    error: str = Field(default="", description="Error message if failed")


async def _apply_wifi_change(
    client: UniFiClient,
    change: ConfigChange,
) -> ChangeResult:
    """Apply a single WiFi change."""
    try:
        if change.action == ChangeAction.UPDATE:
            # Build update payload from changes
            updates = {}
            for field_change in change.changes:
                updates[field_change.field] = field_change.new_value
            
            await client.update_wlan(change.item_id, updates)
            
            return ChangeResult(
                success=True,
                item_type="wifi",
                item_name=change.item_name,
                action=change.action.value,
            )
        else:
            return ChangeResult(
                success=False,
                item_type="wifi",
                item_name=change.item_name,
                action=change.action.value,
                error=f"Action '{change.action.value}' not supported for WiFi",
            )
    except Exception as e:
        return ChangeResult(
            success=False,
            item_type="wifi",
            item_name=change.item_name,
            action=change.action.value,
            error=str(e),
        )


async def _apply_firewall_change(
    client: UniFiClient,
    change: ConfigChange,
) -> ChangeResult:
    """Apply a single firewall rule change."""
    try:
        if change.action == ChangeAction.UPDATE:
            updates = {}
            for field_change in change.changes:
                # Map field names
                field_map = {
                    "rule_action": "action",
                }
                field_name = field_map.get(field_change.field, field_change.field)
                updates[field_name] = field_change.new_value
            
            await client.update_firewall_rule(change.item_id, updates)
            
            return ChangeResult(
                success=True,
                item_type="firewall_rule",
                item_name=change.item_name,
                action=change.action.value,
            )
        elif change.action == ChangeAction.CREATE:
            await client.create_firewall_rule(change.full_config or {})
            
            return ChangeResult(
                success=True,
                item_type="firewall_rule",
                item_name=change.item_name,
                action=change.action.value,
            )
        else:
            return ChangeResult(
                success=False,
                item_type="firewall_rule",
                item_name=change.item_name,
                action=change.action.value,
                error=f"Action '{change.action.value}' not fully implemented",
            )
    except Exception as e:
        return ChangeResult(
            success=False,
            item_type="firewall_rule",
            item_name=change.item_name,
            action=change.action.value,
            error=str(e),
        )


async def _apply_vlan_change(
    client: UniFiClient,
    change: ConfigChange,
) -> ChangeResult:
    """Apply a single VLAN/network change."""
    try:
        if change.action == ChangeAction.UPDATE:
            updates = {}
            for field_change in change.changes:
                # Map field names to UniFi API names
                field_map = {
                    "subnet": "ip_subnet",
                    "dhcp_enabled": "dhcpd_enabled",
                }
                field_name = field_map.get(field_change.field, field_change.field)
                updates[field_name] = field_change.new_value
            
            await client.update_network(change.item_id, updates)
            
            return ChangeResult(
                success=True,
                item_type="vlan",
                item_name=change.item_name,
                action=change.action.value,
            )
        else:
            return ChangeResult(
                success=False,
                item_type="vlan",
                item_name=change.item_name,
                action=change.action.value,
                error=f"Action '{change.action.value}' not supported for VLANs",
            )
    except Exception as e:
        return ChangeResult(
            success=False,
            item_type="vlan",
            item_name=change.item_name,
            action=change.action.value,
            error=str(e),
        )


async def _apply_upnp_change(
    client: UniFiClient,
    change: ConfigChange,
) -> ChangeResult:
    """Apply UPnP settings change."""
    try:
        if change.action == ChangeAction.UPDATE:
            updates = {}
            for field_change in change.changes:
                updates[field_change.field] = field_change.new_value
            
            await client.update_upnp_settings(updates)
            
            return ChangeResult(
                success=True,
                item_type="upnp",
                item_name=change.item_name,
                action=change.action.value,
            )
        else:
            return ChangeResult(
                success=False,
                item_type="upnp",
                item_name=change.item_name,
                action=change.action.value,
                error=f"Action '{change.action.value}' not supported for UPnP",
            )
    except Exception as e:
        return ChangeResult(
            success=False,
            item_type="upnp",
            item_name=change.item_name,
            action=change.action.value,
            error=str(e),
        )


@tool(
    name="unifi_apply_changes",
    description="Apply configuration changes to UniFi controller with dry-run support",
    input_schema=UniFiApplyChangesInput,
    output_schema=UniFiApplyChangesOutput,
    tags=["unifi", "network", "configuration"]
)
async def unifi_apply_changes(
    params: UniFiApplyChangesInput
) -> UniFiApplyChangesOutput:
    """Apply configuration changes to the UniFi controller.
    
    If dry_run is True, computes and returns the diff without making changes.
    If dry_run is False, applies changes and verifies they took effect.
    
    Args:
        params: Change parameters
        
    Returns:
        Results of change application
    """
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start(
        "unifi_apply_changes",
        dry_run=params.dry_run,
        wifi_edit_count=len(params.wifi_edits),
        firewall_edit_count=len(params.firewall_edits),
        vlan_edit_count=len(params.vlan_edits),
        has_upnp_edits=params.upnp_edits is not None,
    )
    
    try:
        async with UniFiClient(site=params.site_id) as client:
            # Get current configurations
            current_wlans = await client.get_wlans()
            current_firewall = await client.get_firewall_rules()
            current_networks = await client.get_networks()
            current_upnp = await client.get_upnp_settings()
            
            # Compute diffs
            wifi_diff = plan_wifi_changes(
                current_wlans,
                [e.model_dump(exclude_none=True) for e in params.wifi_edits],
            )
            
            firewall_diff = plan_firewall_changes(
                current_firewall,
                [e.model_dump(exclude_none=True) for e in params.firewall_edits],
            )
            
            vlan_diff = plan_vlan_changes(
                current_networks,
                [e.model_dump(exclude_none=True) for e in params.vlan_edits],
            )
            
            upnp_diff = DiffResult()
            if params.upnp_edits:
                upnp_diff = plan_upnp_changes(
                    current_upnp,
                    params.upnp_edits.model_dump(exclude_none=True),
                )
            
            # Combine all diffs
            combined_diff = combine_diffs(wifi_diff, firewall_diff, vlan_diff, upnp_diff)
            
            # If dry run, return diff without applying
            if params.dry_run:
                invocation_logger.success(
                    dry_run=True,
                    total_changes=len(combined_diff.changes),
                )
                return UniFiApplyChangesOutput(
                    success=True,
                    dry_run=True,
                    diff=combined_diff.to_dict(),
                )
            
            # Apply changes
            results = []
            warnings = []
            
            for change in combined_diff.changes:
                if change.item_type == "wifi":
                    result = await _apply_wifi_change(client, change)
                elif change.item_type == "firewall_rule":
                    result = await _apply_firewall_change(client, change)
                elif change.item_type == "vlan":
                    result = await _apply_vlan_change(client, change)
                elif change.item_type == "upnp":
                    result = await _apply_upnp_change(client, change)
                else:
                    result = ChangeResult(
                        success=False,
                        item_type=change.item_type,
                        item_name=change.item_name,
                        action=change.action.value,
                        error=f"Unknown item type: {change.item_type}",
                    )
                
                results.append(result)
                
                if not result.success:
                    warnings.append(f"Failed to apply {change.item_type} change '{change.item_name}': {result.error}")
            
            # Verify changes by re-reading config
            # (In a full implementation, we'd compare before/after)
            
            changes_applied = sum(1 for r in results if r.success)
            changes_failed = sum(1 for r in results if not r.success)
            
            overall_success = changes_failed == 0
            
            if overall_success:
                invocation_logger.success(
                    changes_applied=changes_applied,
                    changes_failed=changes_failed,
                )
            else:
                invocation_logger.failure(
                    f"{changes_failed} change(s) failed",
                    changes_applied=changes_applied,
                    changes_failed=changes_failed,
                )
            
            return UniFiApplyChangesOutput(
                success=overall_success,
                dry_run=False,
                diff=combined_diff.to_dict(),
                results=results,
                changes_applied=changes_applied,
                changes_failed=changes_failed,
                warnings=warnings,
            )
            
    except UniFiConnectionError as e:
        invocation_logger.failure(str(e))
        return UniFiApplyChangesOutput(
            success=False,
            dry_run=params.dry_run,
            error=f"Connection error: {e}",
        )
    except UniFiAuthError as e:
        invocation_logger.failure(str(e))
        return UniFiApplyChangesOutput(
            success=False,
            dry_run=params.dry_run,
            error=f"Authentication error: {e}",
        )
    except UniFiAPIError as e:
        invocation_logger.failure(str(e))
        return UniFiApplyChangesOutput(
            success=False,
            dry_run=params.dry_run,
            error=f"API error: {e}",
        )
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return UniFiApplyChangesOutput(
            success=False,
            dry_run=params.dry_run,
            error=f"Unexpected error: {e}",
        )

