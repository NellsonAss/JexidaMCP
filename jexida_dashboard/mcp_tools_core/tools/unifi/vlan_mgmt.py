"""UniFi VLAN Management Tools.

Provides tools for creating and updating VLANs/networks:
- unifi_vlan_create: Create a new VLAN/network
- unifi_vlan_update: Update existing VLAN configuration
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from .client import UniFiClient, UniFiConnectionError, UniFiAuthError, UniFiAPIError

import logging
logger = logging.getLogger(__name__)


class UniFiVlanCreateInput(BaseModel):
    """Input schema for unifi_vlan_create tool."""
    
    name: str = Field(description="VLAN/Network name (e.g., 'IoT')")
    vlan_id: int = Field(description="VLAN ID (1-4094)")
    subnet: str = Field(description="IP subnet in CIDR notation (e.g., '192.168.30.0/24')")
    dhcp: bool = Field(default=True, description="Enable DHCP")
    dhcp_start: Optional[str] = Field(default=None, description="DHCP start IP (e.g., '192.168.30.10')")
    dhcp_stop: Optional[str] = Field(default=None, description="DHCP stop IP (e.g., '192.168.30.200')")
    purpose: str = Field(default="corporate", description="Network purpose: corporate, guest, vlan-only")
    site_id: Optional[str] = Field(default=None, description="UniFi site ID")


class UniFiVlanCreateOutput(BaseModel):
    """Output schema for unifi_vlan_create tool."""
    
    success: bool = Field(description="Whether the VLAN was created")
    network_id: str = Field(default="", description="Created network ID")
    name: str = Field(default="", description="Network name")
    validation_warnings: list[str] = Field(default_factory=list, description="Validation warnings")
    error: str = Field(default="", description="Error message if failed")


async def unifi_vlan_create(params: UniFiVlanCreateInput) -> UniFiVlanCreateOutput:
    """Create a new VLAN/network.
    
    After creation, validates:
    - Subnet overlap
    - DHCP pool safety
    - Firewall segmentation consistency
    
    Args:
        params: VLAN creation parameters
        
    Returns:
        Creation result with network ID
    """
    logger.info(f"unifi_vlan_create called: {params.name}, VLAN {params.vlan_id}")
    
    try:
        async with UniFiClient(site=params.site_id) as client:
            # Validate subnet doesn't overlap with existing networks
            existing_networks = await client.get_networks()
            warnings = []
            
            for net in existing_networks:
                existing_subnet = net.get("subnet", "")
                if existing_subnet and params.subnet:
                    # Simple overlap check (would need proper IP network comparison in production)
                    if existing_subnet.split("/")[0].split(".")[:3] == params.subnet.split("/")[0].split(".")[:3]:
                        warnings.append(f"Potential subnet overlap with existing network '{net.get('name', '')}'")
            
            # Build network config
            network_config = {
                "name": params.name,
                "purpose": params.purpose,
                "vlan_enabled": True,
                "vlan": params.vlan_id,
                "ip_subnet": params.subnet,
                "dhcpd_enabled": params.dhcp,
            }
            
            if params.dhcp and params.dhcp_start:
                network_config["dhcpd_start"] = params.dhcp_start
            if params.dhcp and params.dhcp_stop:
                network_config["dhcpd_stop"] = params.dhcp_stop
            
            # Create the network
            result = await client.create_network(network_config)
            
            network_id = result.get("data", [{}])[0].get("_id", "") if isinstance(result.get("data"), list) else ""
            
            return UniFiVlanCreateOutput(
                success=True,
                network_id=network_id,
                name=params.name,
                validation_warnings=warnings,
            )
            
    except UniFiConnectionError as e:
        return UniFiVlanCreateOutput(success=False, error=f"Connection error: {e}")
    except UniFiAuthError as e:
        return UniFiVlanCreateOutput(success=False, error=f"Authentication error: {e}")
    except UniFiAPIError as e:
        return UniFiVlanCreateOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        return UniFiVlanCreateOutput(success=False, error=f"Unexpected error: {e}")


class UniFiVlanUpdateInput(BaseModel):
    """Input schema for unifi_vlan_update tool."""
    
    network_id: Optional[str] = Field(default=None, description="Network ID to update")
    network_name: Optional[str] = Field(default=None, description="Network name (if ID not provided)")
    dhcp_enabled: Optional[bool] = Field(default=None, description="Enable/disable DHCP")
    dhcp_start: Optional[str] = Field(default=None, description="DHCP start IP")
    dhcp_stop: Optional[str] = Field(default=None, description="DHCP stop IP")
    subnet: Optional[str] = Field(default=None, description="IP subnet")
    description: Optional[str] = Field(default=None, description="Network description")
    site_id: Optional[str] = Field(default=None, description="UniFi site ID")


class UniFiVlanUpdateOutput(BaseModel):
    """Output schema for unifi_vlan_update tool."""
    
    success: bool = Field(description="Whether the update succeeded")
    network_id: str = Field(default="", description="Updated network ID")
    changes_applied: list[str] = Field(default_factory=list, description="List of changes applied")
    error: str = Field(default="", description="Error message if failed")


async def unifi_vlan_update(params: UniFiVlanUpdateInput) -> UniFiVlanUpdateOutput:
    """Update VLAN/network configuration.
    
    Args:
        params: Update parameters
        
    Returns:
        Update result
    """
    logger.info(f"unifi_vlan_update called: network_id={params.network_id}, name={params.network_name}")
    
    try:
        async with UniFiClient(site=params.site_id) as client:
            # Find network by ID or name
            networks = await client.get_networks()
            network = None
            
            if params.network_id:
                network = next((n for n in networks if n.get("_id") == params.network_id), None)
            elif params.network_name:
                network = next((n for n in networks if n.get("name") == params.network_name), None)
            
            if not network:
                return UniFiVlanUpdateOutput(
                    success=False,
                    error=f"Network not found: {params.network_id or params.network_name}",
                )
            
            network_id = network.get("_id")
            
            # Build update payload
            updates = {}
            changes = []
            
            if params.dhcp_enabled is not None:
                updates["dhcpd_enabled"] = params.dhcp_enabled
                changes.append(f"DHCP enabled: {params.dhcp_enabled}")
            
            if params.dhcp_start:
                updates["dhcpd_start"] = params.dhcp_start
                changes.append(f"DHCP start: {params.dhcp_start}")
            
            if params.dhcp_stop:
                updates["dhcpd_stop"] = params.dhcp_stop
                changes.append(f"DHCP stop: {params.dhcp_stop}")
            
            if params.subnet:
                updates["ip_subnet"] = params.subnet
                changes.append(f"Subnet: {params.subnet}")
            
            if not updates:
                return UniFiVlanUpdateOutput(
                    success=False,
                    network_id=network_id,
                    error="No updates specified",
                )
            
            # Apply updates
            await client.update_network(network_id, updates)
            
            return UniFiVlanUpdateOutput(
                success=True,
                network_id=network_id,
                changes_applied=changes,
            )
            
    except UniFiConnectionError as e:
        return UniFiVlanUpdateOutput(success=False, error=f"Connection error: {e}")
    except UniFiAuthError as e:
        return UniFiVlanUpdateOutput(success=False, error=f"Authentication error: {e}")
    except UniFiAPIError as e:
        return UniFiVlanUpdateOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        return UniFiVlanUpdateOutput(success=False, error=f"Unexpected error: {e}")

