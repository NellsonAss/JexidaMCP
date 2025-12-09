"""Diff and plan helpers for UniFi configuration changes.

Pure functions that compute differences between current and desired
configurations without making any API calls.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ChangeAction(str, Enum):
    """Type of change action."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    NO_CHANGE = "no_change"


@dataclass
class FieldChange:
    """A single field change within a configuration."""
    field: str
    old_value: Any
    new_value: Any
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "old_value": self.old_value,
            "new_value": self.new_value,
        }


@dataclass
class ConfigChange:
    """A change to a single configuration item."""
    action: ChangeAction
    item_type: str  # "wifi", "firewall_rule", "vlan", "upnp", etc.
    item_id: Optional[str]  # ID of existing item (None for create)
    item_name: str  # Human-readable name
    changes: List[FieldChange] = field(default_factory=list)
    full_config: Optional[Dict[str, Any]] = None  # For creates, the full config
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "action": self.action.value,
            "item_type": self.item_type,
            "item_id": self.item_id,
            "item_name": self.item_name,
            "changes": [c.to_dict() for c in self.changes],
        }
        if self.full_config:
            result["full_config"] = self.full_config
        return result


@dataclass
class DiffResult:
    """Result of computing a diff between configurations."""
    changes: List[ConfigChange] = field(default_factory=list)
    has_changes: bool = False
    summary: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "has_changes": self.has_changes,
            "change_count": len(self.changes),
            "summary": self.summary,
            "changes": [c.to_dict() for c in self.changes],
        }


# -------------------------------------------------------------------------
# WiFi Change Planning
# -------------------------------------------------------------------------

def plan_wifi_changes(
    current_wlans: List[Dict[str, Any]],
    desired_changes: List[Dict[str, Any]],
) -> DiffResult:
    """Plan changes to WiFi/WLAN configurations.
    
    Args:
        current_wlans: Current WLAN configurations from controller
        desired_changes: List of desired changes, each with:
            - ssid: Name of SSID to modify (required)
            - enabled: Optional bool
            - security: Optional security mode
            - wpa_mode: Optional WPA version
            - hide_ssid: Optional bool
            - l2_isolation: Optional bool (client isolation)
            - vlan: Optional VLAN ID
            - vlan_enabled: Optional bool
            
    Returns:
        DiffResult with planned changes
    """
    changes = []
    
    # Build lookup by name
    current_by_name = {w.get("name", ""): w for w in current_wlans}
    
    for desired in desired_changes:
        ssid_name = desired.get("ssid") or desired.get("name")
        if not ssid_name:
            continue
        
        current = current_by_name.get(ssid_name)
        
        if current is None:
            # SSID doesn't exist - this would be a create, but typically
            # we modify existing SSIDs rather than create new ones
            changes.append(ConfigChange(
                action=ChangeAction.CREATE,
                item_type="wifi",
                item_id=None,
                item_name=ssid_name,
                full_config=desired,
            ))
            continue
        
        # Compare fields
        field_changes = []
        fields_to_check = [
            ("enabled", "enabled"),
            ("security", "security"),
            ("wpa_mode", "wpa_mode"),
            ("wpa3_support", "wpa3_support"),
            ("wpa3_transition", "wpa3_transition"),
            ("hide_ssid", "hide_ssid"),
            ("l2_isolation", "l2_isolation"),
            ("vlan_enabled", "vlan_enabled"),
            ("vlan", "vlan"),
            ("mac_filter_enabled", "mac_filter_enabled"),
            ("pmf_mode", "pmf_mode"),
        ]
        
        for desired_key, current_key in fields_to_check:
            if desired_key in desired:
                old_val = current.get(current_key)
                new_val = desired[desired_key]
                if old_val != new_val:
                    field_changes.append(FieldChange(
                        field=desired_key,
                        old_value=old_val,
                        new_value=new_val,
                    ))
        
        if field_changes:
            changes.append(ConfigChange(
                action=ChangeAction.UPDATE,
                item_type="wifi",
                item_id=current.get("_id"),
                item_name=ssid_name,
                changes=field_changes,
            ))
    
    has_changes = len(changes) > 0
    summary = f"{len(changes)} WiFi change(s) planned" if has_changes else "No WiFi changes needed"
    
    return DiffResult(
        changes=changes,
        has_changes=has_changes,
        summary=summary,
    )


# -------------------------------------------------------------------------
# Firewall Change Planning
# -------------------------------------------------------------------------

def plan_firewall_changes(
    current_rules: Dict[str, List[Dict[str, Any]]],
    desired_changes: List[Dict[str, Any]],
) -> DiffResult:
    """Plan changes to firewall rules.
    
    Args:
        current_rules: Current firewall rules by ruleset (wan_in, lan_in, etc.)
        desired_changes: List of desired changes, each with:
            - ruleset: Which ruleset (wan_in, lan_in, etc.)
            - action: "create", "update", or "delete"
            - rule_id: ID of rule to modify (for update/delete)
            - rule_name: Name for new/existing rule
            - rule_action: accept, drop, reject
            - protocol: all, tcp, udp, etc.
            - src_address: Source address
            - dst_address: Destination address
            - dst_port: Destination port(s)
            - enabled: Whether rule is enabled
            
    Returns:
        DiffResult with planned changes
    """
    changes = []
    
    # Flatten all rules with their ruleset for lookup
    all_rules = {}
    for ruleset_name, rules in current_rules.items():
        for rule in rules:
            rule_id = rule.get("_id")
            if rule_id:
                all_rules[rule_id] = {**rule, "_ruleset": ruleset_name}
    
    for desired in desired_changes:
        action = desired.get("action", "update").lower()
        rule_id = desired.get("rule_id")
        rule_name = desired.get("rule_name", desired.get("name", "Unnamed Rule"))
        
        if action == "create":
            changes.append(ConfigChange(
                action=ChangeAction.CREATE,
                item_type="firewall_rule",
                item_id=None,
                item_name=rule_name,
                full_config=desired,
            ))
            continue
        
        if action == "delete":
            if rule_id:
                current = all_rules.get(rule_id, {})
                changes.append(ConfigChange(
                    action=ChangeAction.DELETE,
                    item_type="firewall_rule",
                    item_id=rule_id,
                    item_name=current.get("name", rule_name),
                ))
            continue
        
        # Update existing rule
        if not rule_id:
            # Try to find by name in the specified ruleset
            ruleset = desired.get("ruleset", "")
            ruleset_rules = current_rules.get(ruleset, [])
            for rule in ruleset_rules:
                if rule.get("name") == rule_name:
                    rule_id = rule.get("_id")
                    break
        
        if not rule_id:
            # Can't find rule, treat as create
            changes.append(ConfigChange(
                action=ChangeAction.CREATE,
                item_type="firewall_rule",
                item_id=None,
                item_name=rule_name,
                full_config=desired,
            ))
            continue
        
        current = all_rules.get(rule_id, {})
        field_changes = []
        
        fields_to_check = [
            ("enabled", "enabled"),
            ("rule_action", "action"),
            ("protocol", "protocol"),
            ("src_address", "src_address"),
            ("dst_address", "dst_address"),
            ("dst_port", "dst_port"),
        ]
        
        for desired_key, current_key in fields_to_check:
            if desired_key in desired:
                old_val = current.get(current_key)
                new_val = desired[desired_key]
                if old_val != new_val:
                    field_changes.append(FieldChange(
                        field=desired_key,
                        old_value=old_val,
                        new_value=new_val,
                    ))
        
        if field_changes:
            changes.append(ConfigChange(
                action=ChangeAction.UPDATE,
                item_type="firewall_rule",
                item_id=rule_id,
                item_name=current.get("name", rule_name),
                changes=field_changes,
            ))
    
    has_changes = len(changes) > 0
    summary = f"{len(changes)} firewall rule change(s) planned" if has_changes else "No firewall changes needed"
    
    return DiffResult(
        changes=changes,
        has_changes=has_changes,
        summary=summary,
    )


# -------------------------------------------------------------------------
# VLAN/Network Change Planning
# -------------------------------------------------------------------------

def plan_vlan_changes(
    current_networks: List[Dict[str, Any]],
    desired_changes: List[Dict[str, Any]],
) -> DiffResult:
    """Plan changes to VLAN/network configurations.
    
    Args:
        current_networks: Current network configurations
        desired_changes: List of desired changes, each with:
            - network_name: Name of network to modify
            - action: "create", "update", or "delete"
            - network_id: ID for update/delete
            - vlan_enabled: Whether VLAN is enabled
            - vlan: VLAN ID
            - subnet: IP subnet
            - dhcp_enabled: DHCP enabled
            - purpose: Network purpose
            
    Returns:
        DiffResult with planned changes
    """
    changes = []
    
    current_by_name = {n.get("name", ""): n for n in current_networks}
    current_by_id = {n.get("_id", ""): n for n in current_networks}
    
    for desired in desired_changes:
        action = desired.get("action", "update").lower()
        network_name = desired.get("network_name", desired.get("name", ""))
        network_id = desired.get("network_id")
        
        if action == "create":
            changes.append(ConfigChange(
                action=ChangeAction.CREATE,
                item_type="vlan",
                item_id=None,
                item_name=network_name,
                full_config=desired,
            ))
            continue
        
        if action == "delete":
            current = current_by_id.get(network_id) or current_by_name.get(network_name)
            if current:
                changes.append(ConfigChange(
                    action=ChangeAction.DELETE,
                    item_type="vlan",
                    item_id=current.get("_id"),
                    item_name=current.get("name", network_name),
                ))
            continue
        
        # Update
        current = current_by_id.get(network_id) or current_by_name.get(network_name)
        if not current:
            # Network doesn't exist, treat as create
            changes.append(ConfigChange(
                action=ChangeAction.CREATE,
                item_type="vlan",
                item_id=None,
                item_name=network_name,
                full_config=desired,
            ))
            continue
        
        field_changes = []
        fields_to_check = [
            ("vlan_enabled", "vlan_enabled"),
            ("vlan", "vlan"),
            ("subnet", "ip_subnet"),
            ("dhcp_enabled", "dhcpd_enabled"),
            ("purpose", "purpose"),
            ("igmp_snooping", "igmp_snooping"),
        ]
        
        for desired_key, current_key in fields_to_check:
            if desired_key in desired:
                old_val = current.get(current_key)
                new_val = desired[desired_key]
                if old_val != new_val:
                    field_changes.append(FieldChange(
                        field=desired_key,
                        old_value=old_val,
                        new_value=new_val,
                    ))
        
        if field_changes:
            changes.append(ConfigChange(
                action=ChangeAction.UPDATE,
                item_type="vlan",
                item_id=current.get("_id"),
                item_name=current.get("name", network_name),
                changes=field_changes,
            ))
    
    has_changes = len(changes) > 0
    summary = f"{len(changes)} VLAN/network change(s) planned" if has_changes else "No VLAN changes needed"
    
    return DiffResult(
        changes=changes,
        has_changes=has_changes,
        summary=summary,
    )


# -------------------------------------------------------------------------
# UPnP Change Planning
# -------------------------------------------------------------------------

def plan_upnp_changes(
    current_settings: Dict[str, Any],
    desired_changes: Dict[str, Any],
) -> DiffResult:
    """Plan changes to UPnP settings.
    
    Args:
        current_settings: Current UPnP settings (upnp_enabled, etc.)
        desired_changes: Desired UPnP settings
            
    Returns:
        DiffResult with planned changes
    """
    changes = []
    field_changes = []
    
    fields_to_check = [
        "upnp_enabled",
        "upnp_nat_pmp_enabled",
        "upnp_secure_mode",
    ]
    
    for field_name in fields_to_check:
        if field_name in desired_changes:
            old_val = current_settings.get(field_name)
            new_val = desired_changes[field_name]
            if old_val != new_val:
                field_changes.append(FieldChange(
                    field=field_name,
                    old_value=old_val,
                    new_value=new_val,
                ))
    
    if field_changes:
        changes.append(ConfigChange(
            action=ChangeAction.UPDATE,
            item_type="upnp",
            item_id="usg_settings",
            item_name="UPnP Settings",
            changes=field_changes,
        ))
    
    has_changes = len(changes) > 0
    summary = "UPnP changes planned" if has_changes else "No UPnP changes needed"
    
    return DiffResult(
        changes=changes,
        has_changes=has_changes,
        summary=summary,
    )


# -------------------------------------------------------------------------
# Combined Diff
# -------------------------------------------------------------------------

def combine_diffs(*diffs: DiffResult) -> DiffResult:
    """Combine multiple diff results into one.
    
    Args:
        *diffs: DiffResult objects to combine
        
    Returns:
        Combined DiffResult
    """
    all_changes = []
    summaries = []
    
    for diff in diffs:
        all_changes.extend(diff.changes)
        if diff.has_changes:
            summaries.append(diff.summary)
    
    has_changes = len(all_changes) > 0
    summary = "; ".join(summaries) if summaries else "No changes needed"
    
    return DiffResult(
        changes=all_changes,
        has_changes=has_changes,
        summary=summary,
    )

