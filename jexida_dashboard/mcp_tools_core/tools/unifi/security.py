"""UniFi security settings tool.

Provides the unifi_get_security_settings tool for collecting all
security-relevant configuration from the UniFi controller.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from logging_config import get_logger, ToolInvocationLogger
from tool_registry import tool

from .client import UniFiClient, UniFiConnectionError, UniFiAuthError, UniFiAPIError

logger = get_logger(__name__)


# -------------------------------------------------------------------------
# WiFi Settings Models
# -------------------------------------------------------------------------

class WifiNetworkInfo(BaseModel):
    """WiFi network (SSID) security information."""
    
    id: str = Field(description="Internal ID")
    name: str = Field(description="Network/SSID name")
    enabled: bool = Field(description="Whether network is enabled")
    security: str = Field(description="Security mode (open, wpa, etc.)")
    wpa_mode: str = Field(description="WPA mode (wpa2, wpa3, etc.)")
    wpa3_support: bool = Field(description="WPA3 support enabled")
    wpa3_transition: bool = Field(description="WPA3 transition mode enabled")
    hide_ssid: bool = Field(description="Whether SSID is hidden")
    is_guest: bool = Field(description="Whether this is a guest network")
    vlan_enabled: bool = Field(description="Whether VLAN tagging is enabled")
    vlan: str = Field(description="VLAN ID if enabled")
    client_isolation: bool = Field(description="L2 isolation enabled")
    mac_filter_enabled: bool = Field(description="MAC filtering enabled")
    pmf_mode: str = Field(description="Protected Management Frames mode")


class WifiSettings(BaseModel):
    """All WiFi-related security settings."""
    
    networks: List[WifiNetworkInfo] = Field(
        default_factory=list,
        description="List of WiFi networks"
    )


# -------------------------------------------------------------------------
# VLAN/Network Settings Models
# -------------------------------------------------------------------------

class VlanInfo(BaseModel):
    """VLAN/Network configuration."""
    
    id: str = Field(description="Internal ID")
    name: str = Field(description="Network name")
    purpose: str = Field(description="Network purpose (corporate, guest, wan, vlan-only)")
    vlan_enabled: bool = Field(description="Whether VLAN is enabled")
    vlan_id: Optional[int] = Field(default=None, description="VLAN ID")
    subnet: str = Field(description="IP subnet")
    dhcp_enabled: bool = Field(description="Whether DHCP is enabled")
    igmp_snooping: bool = Field(description="IGMP snooping enabled")


class VlanSettings(BaseModel):
    """All VLAN/Network settings."""
    
    networks: List[VlanInfo] = Field(
        default_factory=list,
        description="List of networks/VLANs"
    )


# -------------------------------------------------------------------------
# Firewall Settings Models
# -------------------------------------------------------------------------

class FirewallRuleInfo(BaseModel):
    """Firewall rule information."""
    
    id: str = Field(description="Internal ID")
    name: str = Field(description="Rule name")
    enabled: bool = Field(description="Whether rule is enabled")
    action: str = Field(description="Action: accept, drop, reject")
    protocol: str = Field(description="Protocol: all, tcp, udp, etc.")
    source: str = Field(description="Source address/network/group")
    destination: str = Field(description="Destination address/network/group")
    dst_port: str = Field(description="Destination port(s)")
    rule_index: int = Field(description="Rule order/priority")


class FirewallRuleset(BaseModel):
    """Firewall rules for a specific direction."""
    
    rules: List[FirewallRuleInfo] = Field(
        default_factory=list,
        description="List of firewall rules"
    )


class FirewallGroupInfo(BaseModel):
    """Firewall group (address/port group) information."""
    
    id: str = Field(description="Internal ID")
    name: str = Field(description="Group name")
    group_type: str = Field(description="Group type: address-group, port-group")
    members: List[str] = Field(default_factory=list, description="Group members")


class FirewallSettings(BaseModel):
    """All firewall settings."""
    
    wan_in: FirewallRuleset = Field(default_factory=FirewallRuleset)
    wan_out: FirewallRuleset = Field(default_factory=FirewallRuleset)
    wan_local: FirewallRuleset = Field(default_factory=FirewallRuleset)
    lan_in: FirewallRuleset = Field(default_factory=FirewallRuleset)
    lan_out: FirewallRuleset = Field(default_factory=FirewallRuleset)
    lan_local: FirewallRuleset = Field(default_factory=FirewallRuleset)
    guest_in: FirewallRuleset = Field(default_factory=FirewallRuleset)
    guest_out: FirewallRuleset = Field(default_factory=FirewallRuleset)
    guest_local: FirewallRuleset = Field(default_factory=FirewallRuleset)
    groups: List[FirewallGroupInfo] = Field(
        default_factory=list,
        description="Firewall groups"
    )


# -------------------------------------------------------------------------
# Remote Access Settings Models
# -------------------------------------------------------------------------

class RemoteAccessSettings(BaseModel):
    """Remote access and management settings."""
    
    upnp_enabled: bool = Field(description="UPnP enabled")
    upnp_nat_pmp_enabled: bool = Field(description="NAT-PMP enabled")
    upnp_secure_mode: bool = Field(description="UPnP secure mode enabled")
    ssh_enabled: bool = Field(description="SSH access enabled")
    ssh_password_auth: bool = Field(description="SSH password auth enabled")
    cloud_access_enabled: bool = Field(description="UniFi cloud access enabled")


# -------------------------------------------------------------------------
# Threat Management Settings Models
# -------------------------------------------------------------------------

class ThreatManagementSettings(BaseModel):
    """IDS/IPS and threat management settings."""
    
    ids_ips_enabled: bool = Field(description="IDS/IPS enabled")
    mode: str = Field(description="Mode: disabled, ids, ips")
    dns_filtering_enabled: bool = Field(description="DNS filtering enabled")
    honeypot_enabled: bool = Field(description="Honeypot enabled")
    dpi_enabled: bool = Field(description="Deep Packet Inspection enabled")
    dpi_restrictions_enabled: bool = Field(description="DPI restrictions enabled")


# -------------------------------------------------------------------------
# Main Input/Output Models
# -------------------------------------------------------------------------

class UniFiSecuritySettingsInput(BaseModel):
    """Input schema for unifi_get_security_settings tool."""
    
    site_id: Optional[str] = Field(
        default=None,
        description="UniFi site ID (defaults to configured site)"
    )
    include_firewall_rules: bool = Field(
        default=True,
        description="Include detailed firewall rules"
    )


class UniFiSecuritySettingsOutput(BaseModel):
    """Output schema for unifi_get_security_settings tool."""
    
    success: bool = Field(description="Whether the operation succeeded")
    wifi: Optional[WifiSettings] = Field(default=None, description="WiFi settings")
    vlans: Optional[VlanSettings] = Field(default=None, description="VLAN settings")
    firewall: Optional[FirewallSettings] = Field(default=None, description="Firewall settings")
    remote_access: Optional[RemoteAccessSettings] = Field(default=None, description="Remote access settings")
    threat_management: Optional[ThreatManagementSettings] = Field(default=None, description="Threat management settings")
    error: str = Field(default="", description="Error message if failed")


def _format_source_or_dest(
    address: str,
    network_id: str,
    network_type: str,
    group_ids: List[str],
) -> str:
    """Format source or destination for display."""
    parts = []
    if address:
        parts.append(address)
    if network_id:
        parts.append(f"network:{network_id}")
    if network_type:
        parts.append(f"type:{network_type}")
    if group_ids:
        parts.append(f"groups:{','.join(group_ids)}")
    return " ".join(parts) if parts else "any"


@tool(
    name="unifi_get_security_settings",
    description="Get comprehensive security settings from UniFi controller including WiFi, VLANs, firewall rules, remote access, and threat management",
    input_schema=UniFiSecuritySettingsInput,
    output_schema=UniFiSecuritySettingsOutput,
    tags=["unifi", "network", "security", "audit"]
)
async def unifi_get_security_settings(
    params: UniFiSecuritySettingsInput
) -> UniFiSecuritySettingsOutput:
    """Get all security-relevant settings from UniFi controller.
    
    Args:
        params: Input parameters
        
    Returns:
        Comprehensive security settings
    """
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("unifi_get_security_settings", site_id=params.site_id)
    
    try:
        async with UniFiClient(site=params.site_id) as client:
            # Gather all settings in parallel
            wlans_data = await client.get_wlans()
            networks_data = await client.get_networks()
            upnp_data = await client.get_upnp_settings()
            mgmt_data = await client.get_mgmt_settings()
            threat_data = await client.get_threat_management_settings()
            dpi_data = await client.get_dpi_settings()
            
            # Get firewall data if requested
            firewall_rules_data = {}
            firewall_groups_data = []
            if params.include_firewall_rules:
                firewall_rules_data = await client.get_firewall_rules()
                firewall_groups_data = await client.get_firewall_groups()
            
            # Build WiFi settings
            wifi_networks = [
                WifiNetworkInfo(
                    id=w.get("_id", ""),
                    name=w.get("name", ""),
                    enabled=w.get("enabled", False),
                    security=w.get("security", "open"),
                    wpa_mode=w.get("wpa_mode", ""),
                    wpa3_support=w.get("wpa3_support", False),
                    wpa3_transition=w.get("wpa3_transition", False),
                    hide_ssid=w.get("hide_ssid", False),
                    is_guest=w.get("is_guest", False),
                    vlan_enabled=w.get("vlan_enabled", False),
                    vlan=str(w.get("vlan", "")),
                    client_isolation=w.get("l2_isolation", False),
                    mac_filter_enabled=w.get("mac_filter_enabled", False),
                    pmf_mode=w.get("pmf_mode", "disabled"),
                )
                for w in wlans_data
            ]
            wifi = WifiSettings(networks=wifi_networks)
            
            # Build VLAN settings
            vlan_list = [
                VlanInfo(
                    id=n.get("_id", ""),
                    name=n.get("name", ""),
                    purpose=n.get("purpose", ""),
                    vlan_enabled=n.get("vlan_enabled", False),
                    vlan_id=int(n["vlan"]) if n.get("vlan") else None,
                    subnet=n.get("subnet", ""),
                    dhcp_enabled=n.get("dhcp_enabled", False),
                    igmp_snooping=n.get("igmp_snooping", False),
                )
                for n in networks_data
            ]
            vlans = VlanSettings(networks=vlan_list)
            
            # Build firewall settings
            def build_ruleset(rules: List[Dict[str, Any]]) -> FirewallRuleset:
                return FirewallRuleset(rules=[
                    FirewallRuleInfo(
                        id=r.get("_id", ""),
                        name=r.get("name", ""),
                        enabled=r.get("enabled", True),
                        action=r.get("action", ""),
                        protocol=r.get("protocol", "all"),
                        source=_format_source_or_dest(
                            r.get("src_address", ""),
                            r.get("src_networkconf_id", ""),
                            r.get("src_networkconf_type", ""),
                            r.get("src_firewallgroup_ids", []),
                        ),
                        destination=_format_source_or_dest(
                            r.get("dst_address", ""),
                            r.get("dst_networkconf_id", ""),
                            r.get("dst_networkconf_type", ""),
                            r.get("dst_firewallgroup_ids", []),
                        ),
                        dst_port=r.get("dst_port", ""),
                        rule_index=r.get("rule_index", 0),
                    )
                    for r in rules
                ])
            
            firewall_groups = [
                FirewallGroupInfo(
                    id=g.get("_id", ""),
                    name=g.get("name", ""),
                    group_type=g.get("group_type", ""),
                    members=g.get("group_members", []),
                )
                for g in firewall_groups_data
            ]
            
            firewall = FirewallSettings(
                wan_in=build_ruleset(firewall_rules_data.get("wan_in", [])),
                wan_out=build_ruleset(firewall_rules_data.get("wan_out", [])),
                wan_local=build_ruleset(firewall_rules_data.get("wan_local", [])),
                lan_in=build_ruleset(firewall_rules_data.get("lan_in", [])),
                lan_out=build_ruleset(firewall_rules_data.get("lan_out", [])),
                lan_local=build_ruleset(firewall_rules_data.get("lan_local", [])),
                guest_in=build_ruleset(firewall_rules_data.get("guest_in", [])),
                guest_out=build_ruleset(firewall_rules_data.get("guest_out", [])),
                guest_local=build_ruleset(firewall_rules_data.get("guest_local", [])),
                groups=firewall_groups,
            )
            
            # Build remote access settings
            remote_access = RemoteAccessSettings(
                upnp_enabled=upnp_data.get("upnp_enabled", False),
                upnp_nat_pmp_enabled=upnp_data.get("upnp_nat_pmp_enabled", False),
                upnp_secure_mode=upnp_data.get("upnp_secure_mode", False),
                ssh_enabled=mgmt_data.get("remote_access_enabled", False),
                ssh_password_auth=mgmt_data.get("ssh_auth_password_enabled", False),
                cloud_access_enabled=mgmt_data.get("unifi_remote_access_enabled", False),
            )
            
            # Build threat management settings
            threat_management = ThreatManagementSettings(
                ids_ips_enabled=threat_data.get("ips_enabled", False),
                mode=threat_data.get("ips_mode", "disabled"),
                dns_filtering_enabled=threat_data.get("dns_filtering_enabled", False),
                honeypot_enabled=threat_data.get("honeypot_enabled", False),
                dpi_enabled=dpi_data.get("dpi_enabled", False),
                dpi_restrictions_enabled=dpi_data.get("dpi_restrictions_enabled", False),
            )
            
            invocation_logger.success(
                wifi_count=len(wifi_networks),
                vlan_count=len(vlan_list),
            )
            
            return UniFiSecuritySettingsOutput(
                success=True,
                wifi=wifi,
                vlans=vlans,
                firewall=firewall,
                remote_access=remote_access,
                threat_management=threat_management,
            )
            
    except UniFiConnectionError as e:
        invocation_logger.failure(str(e))
        return UniFiSecuritySettingsOutput(
            success=False,
            error=f"Connection error: {e}",
        )
    except UniFiAuthError as e:
        invocation_logger.failure(str(e))
        return UniFiSecuritySettingsOutput(
            success=False,
            error=f"Authentication error: {e}",
        )
    except UniFiAPIError as e:
        invocation_logger.failure(str(e))
        return UniFiSecuritySettingsOutput(
            success=False,
            error=f"API error: {e}",
        )
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return UniFiSecuritySettingsOutput(
            success=False,
            error=f"Unexpected error: {e}",
        )

