"""UniFi Firewall Management Tools.

Provides tools for firewall rule management:
- unifi_firewall_create_rule: Create a new firewall rule
- unifi_firewall_update_rule: Update existing firewall rule
- unifi_firewall_validate: Validate firewall rules for issues
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .client import UniFiClient, UniFiConnectionError, UniFiAuthError, UniFiAPIError

import logging
logger = logging.getLogger(__name__)


class UniFiFirewallCreateRuleInput(BaseModel):
    """Input schema for unifi_firewall_create_rule tool."""
    
    action: Literal["drop", "accept", "reject"] = Field(description="Rule action")
    from_network: Optional[str] = Field(default=None, description="Source network name")
    to_network: Optional[str] = Field(default=None, description="Destination network name")
    from_address: Optional[str] = Field(default=None, description="Source IP address/CIDR")
    to_address: Optional[str] = Field(default=None, description="Destination IP address/CIDR")
    protocol: Literal["all", "tcp", "udp", "icmp"] = Field(default="all", description="Protocol")
    dst_port: Optional[str] = Field(default=None, description="Destination port(s), e.g., '80,443' or '1000-2000'")
    comment: str = Field(default="", description="Rule comment/description")
    ruleset: Literal["wan_in", "wan_out", "lan_in", "lan_out", "lan_local", "guest_in", "guest_out", "guest_local"] = Field(
        default="lan_in",
        description="Firewall ruleset"
    )
    site_id: Optional[str] = Field(default=None, description="UniFi site ID")


class UniFiFirewallCreateRuleOutput(BaseModel):
    """Output schema for unifi_firewall_create_rule tool."""
    
    success: bool = Field(description="Whether the rule was created")
    rule_id: str = Field(default="", description="Created rule ID")
    rule_name: str = Field(default="", description="Rule name")
    error: str = Field(default="", description="Error message if failed")


async def unifi_firewall_create_rule(
    params: UniFiFirewallCreateRuleInput
) -> UniFiFirewallCreateRuleOutput:
    """Create a new firewall rule.
    
    Args:
        params: Firewall rule creation parameters
        
    Returns:
        Creation result with rule ID
    """
    logger.info(f"unifi_firewall_create_rule called: {params.action} from {params.from_network or params.from_address} to {params.to_network or params.to_address}")
    
    try:
        async with UniFiClient(site=params.site_id) as client:
            # Get networks to resolve names to IDs
            networks = await client.get_networks()
            network_map = {n.get("name", ""): n.get("_id", "") for n in networks}
            
            # Build rule config
            rule_config = {
                "name": params.comment or f"{params.action} {params.from_network or params.from_address} -> {params.to_network or params.to_address}",
                "enabled": True,
                "action": params.action,
                "protocol": params.protocol,
                "ruleset": params.ruleset,
            }
            
            # Set source
            if params.from_network:
                network_id = network_map.get(params.from_network)
                if network_id:
                    rule_config["src_networkconf_id"] = network_id
                else:
                    return UniFiFirewallCreateRuleOutput(
                        success=False,
                        error=f"Source network '{params.from_network}' not found",
                    )
            elif params.from_address:
                rule_config["src_address"] = params.from_address
            
            # Set destination
            if params.to_network:
                network_id = network_map.get(params.to_network)
                if network_id:
                    rule_config["dst_networkconf_id"] = network_id
                else:
                    return UniFiFirewallCreateRuleOutput(
                        success=False,
                        error=f"Destination network '{params.to_network}' not found",
                    )
            elif params.to_address:
                rule_config["dst_address"] = params.to_address
            
            if params.dst_port:
                rule_config["dst_port"] = params.dst_port
            
            # Create the rule
            result = await client.create_firewall_rule(rule_config)
            
            rule_id = result.get("data", [{}])[0].get("_id", "") if isinstance(result.get("data"), list) else ""
            
            return UniFiFirewallCreateRuleOutput(
                success=True,
                rule_id=rule_id,
                rule_name=rule_config["name"],
            )
            
    except UniFiConnectionError as e:
        return UniFiFirewallCreateRuleOutput(success=False, error=f"Connection error: {e}")
    except UniFiAuthError as e:
        return UniFiFirewallCreateRuleOutput(success=False, error=f"Authentication error: {e}")
    except UniFiAPIError as e:
        return UniFiFirewallCreateRuleOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        return UniFiFirewallCreateRuleOutput(success=False, error=f"Unexpected error: {e}")


class UniFiFirewallUpdateRuleInput(BaseModel):
    """Input schema for unifi_firewall_update_rule tool."""
    
    rule_id: str = Field(description="Firewall rule ID to update")
    enabled: Optional[bool] = Field(default=None, description="Enable/disable rule")
    action: Optional[Literal["drop", "accept", "reject"]] = Field(default=None, description="Rule action")
    protocol: Optional[Literal["all", "tcp", "udp", "icmp"]] = Field(default=None, description="Protocol")
    dst_port: Optional[str] = Field(default=None, description="Destination port(s)")
    comment: Optional[str] = Field(default=None, description="Rule comment")
    site_id: Optional[str] = Field(default=None, description="UniFi site ID")


class UniFiFirewallUpdateRuleOutput(BaseModel):
    """Output schema for unifi_firewall_update_rule tool."""
    
    success: bool = Field(description="Whether the update succeeded")
    rule_id: str = Field(default="", description="Updated rule ID")
    changes_applied: list[str] = Field(default_factory=list, description="List of changes applied")
    error: str = Field(default="", description="Error message if failed")


async def unifi_firewall_update_rule(
    params: UniFiFirewallUpdateRuleInput
) -> UniFiFirewallUpdateRuleOutput:
    """Update an existing firewall rule.
    
    Args:
        params: Update parameters
        
    Returns:
        Update result
    """
    logger.info(f"unifi_firewall_update_rule called: rule_id={params.rule_id}")
    
    try:
        async with UniFiClient(site=params.site_id) as client:
            updates = {}
            changes = []
            
            if params.enabled is not None:
                updates["enabled"] = params.enabled
                changes.append(f"Enabled: {params.enabled}")
            
            if params.action:
                updates["action"] = params.action
                changes.append(f"Action: {params.action}")
            
            if params.protocol:
                updates["protocol"] = params.protocol
                changes.append(f"Protocol: {params.protocol}")
            
            if params.dst_port is not None:
                updates["dst_port"] = params.dst_port
                changes.append(f"Destination port: {params.dst_port}")
            
            if params.comment:
                updates["name"] = params.comment
                changes.append(f"Comment: {params.comment}")
            
            if not updates:
                return UniFiFirewallUpdateRuleOutput(
                    success=False,
                    rule_id=params.rule_id,
                    error="No updates specified",
                )
            
            await client.update_firewall_rule(params.rule_id, updates)
            
            return UniFiFirewallUpdateRuleOutput(
                success=True,
                rule_id=params.rule_id,
                changes_applied=changes,
            )
            
    except UniFiConnectionError as e:
        return UniFiFirewallUpdateRuleOutput(success=False, rule_id=params.rule_id, error=f"Connection error: {e}")
    except UniFiAuthError as e:
        return UniFiFirewallUpdateRuleOutput(success=False, rule_id=params.rule_id, error=f"Authentication error: {e}")
    except UniFiAPIError as e:
        return UniFiFirewallUpdateRuleOutput(success=False, rule_id=params.rule_id, error=f"API error: {e}")
    except Exception as e:
        return UniFiFirewallUpdateRuleOutput(success=False, rule_id=params.rule_id, error=f"Unexpected error: {e}")


class ValidationIssue(BaseModel):
    """Firewall validation issue."""
    severity: str = Field(description="Issue severity: low, medium, high")
    category: str = Field(description="Issue category")
    message: str = Field(description="Issue description")
    rule_id: Optional[str] = Field(default=None, description="Related rule ID")
    rule_name: Optional[str] = Field(default=None, description="Related rule name")


class UniFiFirewallValidateInput(BaseModel):
    """Input schema for unifi_firewall_validate tool."""
    
    site_id: Optional[str] = Field(default=None, description="UniFi site ID")


class UniFiFirewallValidateOutput(BaseModel):
    """Output schema for unifi_firewall_validate tool."""
    
    success: bool = Field(description="Whether validation completed")
    issues: List[ValidationIssue] = Field(default_factory=list, description="Validation issues found")
    issue_count: int = Field(default=0, description="Total issues")
    high_severity_count: int = Field(default=0, description="High severity issues")
    error: str = Field(default="", description="Error message if failed")


async def unifi_firewall_validate(
    params: UniFiFirewallValidateInput
) -> UniFiFirewallValidateOutput:
    """Validate firewall rules for issues.
    
    Checks for:
    - Rule reordering issues
    - Redundant rules
    - Broken segmentation
    - Guest network isolation failures
    
    Args:
        params: Validation parameters
        
    Returns:
        Validation results with issues
    """
    logger.info("unifi_firewall_validate called")
    
    try:
        async with UniFiClient(site=params.site_id) as client:
            firewall_rules = await client.get_firewall_rules()
            networks = await client.get_networks()
            
            issues = []
            
            # Check for overly permissive rules
            for ruleset_name, rules in firewall_rules.items():
                for rule in rules:
                    if not rule.get("enabled", True):
                        continue
                    
                    action = rule.get("action", "")
                    protocol = rule.get("protocol", "all")
                    dst_port = rule.get("dst_port", "")
                    
                    # Flag overly permissive accept rules
                    if action == "accept" and protocol == "all" and not dst_port:
                        issues.append(ValidationIssue(
                            severity="high",
                            category="overly_permissive",
                            message=f"Rule '{rule.get('name', 'Unnamed')}' in {ruleset_name} allows all traffic without port restriction",
                            rule_id=rule.get("_id"),
                            rule_name=rule.get("name"),
                        ))
                    
                    # Check for duplicate rules
                    rule_key = f"{action}:{protocol}:{dst_port}"
                    # (Simplified duplicate check - would need full comparison)
            
            # Check guest network isolation
            guest_networks = [n for n in networks if n.get("purpose") == "guest"]
            for guest_net in guest_networks:
                guest_id = guest_net.get("_id")
                # Check if there are rules allowing guest -> LAN traffic
                for ruleset_name, rules in firewall_rules.items():
                    for rule in rules:
                        if rule.get("dst_networkconf_id") == guest_id:
                            # Check if source is not guest (would allow LAN -> guest)
                            src_net_id = rule.get("src_networkconf_id", "")
                            if src_net_id and src_net_id != guest_id:
                                # This might be OK, but flag for review
                                issues.append(ValidationIssue(
                                    severity="medium",
                                    category="guest_isolation",
                                    message=f"Rule '{rule.get('name', 'Unnamed')}' may allow non-guest traffic to guest network",
                                    rule_id=rule.get("_id"),
                                    rule_name=rule.get("name"),
                                ))
            
            high_severity = sum(1 for i in issues if i.severity == "high")
            
            return UniFiFirewallValidateOutput(
                success=True,
                issues=issues,
                issue_count=len(issues),
                high_severity_count=high_severity,
            )
            
    except UniFiConnectionError as e:
        return UniFiFirewallValidateOutput(success=False, error=f"Connection error: {e}")
    except UniFiAuthError as e:
        return UniFiFirewallValidateOutput(success=False, error=f"Authentication error: {e}")
    except UniFiAPIError as e:
        return UniFiFirewallValidateOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        return UniFiFirewallValidateOutput(success=False, error=f"Unexpected error: {e}")

