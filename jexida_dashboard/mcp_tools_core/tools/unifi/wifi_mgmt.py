"""UniFi WiFi Management Tools.

Provides tools for creating and updating WiFi networks:
- unifi_wifi_create: Create a new WiFi network/SSID
- unifi_wifi_update: Update existing WiFi configuration
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

from .client import UniFiClient, UniFiConnectionError, UniFiAuthError, UniFiAPIError

import logging
logger = logging.getLogger(__name__)


class UniFiWifiCreateInput(BaseModel):
    """Input schema for unifi_wifi_create tool."""
    
    name: str = Field(description="WiFi network name (SSID)")
    vlan_id: Optional[int] = Field(default=None, description="VLAN ID to assign")
    security: Literal["WPA2", "WPA3", "WPA2-WPA3"] = Field(default="WPA2", description="Security mode")
    password: str = Field(description="WiFi password")
    guest: bool = Field(default=False, description="Is guest network")
    hidden: bool = Field(default=False, description="Hide SSID")
    client_isolation: bool = Field(default=False, description="Enable client isolation (L2 isolation)")
    site_id: Optional[str] = Field(default=None, description="UniFi site ID")


class UniFiWifiCreateOutput(BaseModel):
    """Output schema for unifi_wifi_create tool."""
    
    success: bool = Field(description="Whether the WiFi network was created")
    wlan_id: str = Field(default="", description="Created WLAN ID")
    name: str = Field(default="", description="SSID name")
    error: str = Field(default="", description="Error message if failed")


async def unifi_wifi_create(params: UniFiWifiCreateInput) -> UniFiWifiCreateOutput:
    """Create a new WiFi network/SSID.
    
    Args:
        params: WiFi creation parameters
        
    Returns:
        Creation result with WLAN ID
    """
    logger.info(f"unifi_wifi_create called: {params.name}")
    
    try:
        async with UniFiClient(site=params.site_id) as client:
            # Map security mode to UniFi API format
            security_map = {
                "WPA2": "wpapsk",
                "WPA3": "wpapsk",
                "WPA2-WPA3": "wpapsk",
            }
            
            wpa_mode_map = {
                "WPA2": "wpa2",
                "WPA3": "wpa3",
                "WPA2-WPA3": "wpa2-wpa3",
            }
            
            wlan_config = {
                "name": params.name,
                "enabled": True,
                "hide_ssid": params.hidden,
                "is_guest": params.guest,
                "security": security_map.get(params.security, "wpapsk"),
                "wpa_mode": wpa_mode_map.get(params.security, "wpa2"),
                "x_passphrase": params.password,
                "l2_isolation": params.client_isolation,
            }
            
            if params.vlan_id:
                wlan_config["vlan_enabled"] = True
                wlan_config["vlan"] = params.vlan_id
            
            # Enable WPA3 if specified
            if params.security in ("WPA3", "WPA2-WPA3"):
                wlan_config["wpa3_support"] = True
                if params.security == "WPA2-WPA3":
                    wlan_config["wpa3_transition"] = True
            
            # Create the WLAN
            result = await client.create_wlan(wlan_config)
            
            wlan_id = result.get("data", [{}])[0].get("_id", "") if isinstance(result.get("data"), list) else ""
            
            return UniFiWifiCreateOutput(
                success=True,
                wlan_id=wlan_id,
                name=params.name,
            )
            
    except UniFiConnectionError as e:
        return UniFiWifiCreateOutput(success=False, error=f"Connection error: {e}")
    except UniFiAuthError as e:
        return UniFiWifiCreateOutput(success=False, error=f"Authentication error: {e}")
    except UniFiAPIError as e:
        return UniFiWifiCreateOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        return UniFiWifiCreateOutput(success=False, error=f"Unexpected error: {e}")


class UniFiWifiUpdateInput(BaseModel):
    """Input schema for unifi_wifi_update tool."""
    
    wlan_id: Optional[str] = Field(default=None, description="WLAN ID to update")
    ssid: Optional[str] = Field(default=None, description="SSID name (if ID not provided)")
    password: Optional[str] = Field(default=None, description="New WiFi password")
    vlan_id: Optional[int] = Field(default=None, description="VLAN ID to assign")
    security: Optional[Literal["WPA2", "WPA3", "WPA2-WPA3"]] = Field(default=None, description="Security mode")
    enable_pmf: Optional[bool] = Field(default=None, description="Enable Protected Management Frames")
    disable_legacy_24ghz: Optional[bool] = Field(default=None, description="Disable legacy 2.4 GHz support")
    site_id: Optional[str] = Field(default=None, description="UniFi site ID")


class UniFiWifiUpdateOutput(BaseModel):
    """Output schema for unifi_wifi_update tool."""
    
    success: bool = Field(description="Whether the update succeeded")
    wlan_id: str = Field(default="", description="Updated WLAN ID")
    changes_applied: list[str] = Field(default_factory=list, description="List of changes applied")
    error: str = Field(default="", description="Error message if failed")


async def unifi_wifi_update(params: UniFiWifiUpdateInput) -> UniFiWifiUpdateOutput:
    """Update WiFi network configuration.
    
    Can update:
    - Password
    - VLAN assignment
    - Switch to WPA3-only
    - Enable PMF
    - Disable legacy 2.4 GHz
    
    Args:
        params: Update parameters
        
    Returns:
        Update result
    """
    logger.info(f"unifi_wifi_update called: wlan_id={params.wlan_id}, ssid={params.ssid}")
    
    try:
        async with UniFiClient(site=params.site_id) as client:
            # Find WLAN by ID or name
            wlans = await client.get_wlans()
            wlan = None
            
            if params.wlan_id:
                wlan = next((w for w in wlans if w.get("_id") == params.wlan_id), None)
            elif params.ssid:
                wlan = next((w for w in wlans if w.get("name") == params.ssid), None)
            
            if not wlan:
                return UniFiWifiUpdateOutput(
                    success=False,
                    error=f"WLAN not found: {params.wlan_id or params.ssid}",
                )
            
            wlan_id = wlan.get("_id")
            
            # Build update payload
            updates = {}
            changes = []
            
            if params.password:
                updates["x_passphrase"] = params.password
                changes.append("Password updated")
            
            if params.vlan_id is not None:
                updates["vlan_enabled"] = True
                updates["vlan"] = params.vlan_id
                changes.append(f"VLAN set to {params.vlan_id}")
            
            if params.security:
                security_map = {
                    "WPA2": "wpapsk",
                    "WPA3": "wpapsk",
                    "WPA2-WPA3": "wpapsk",
                }
                wpa_mode_map = {
                    "WPA2": "wpa2",
                    "WPA3": "wpa3",
                    "WPA2-WPA3": "wpa2-wpa3",
                }
                updates["security"] = security_map.get(params.security, "wpapsk")
                updates["wpa_mode"] = wpa_mode_map.get(params.security, "wpa2")
                
                if params.security in ("WPA3", "WPA2-WPA3"):
                    updates["wpa3_support"] = True
                    if params.security == "WPA2-WPA3":
                        updates["wpa3_transition"] = True
                
                changes.append(f"Security mode set to {params.security}")
            
            if params.enable_pmf is not None:
                updates["pmf_mode"] = "required" if params.enable_pmf else "disabled"
                changes.append(f"PMF {'enabled' if params.enable_pmf else 'disabled'}")
            
            if not updates:
                return UniFiWifiUpdateOutput(
                    success=False,
                    wlan_id=wlan_id,
                    error="No updates specified",
                )
            
            # Apply updates
            await client.update_wlan(wlan_id, updates)
            
            return UniFiWifiUpdateOutput(
                success=True,
                wlan_id=wlan_id,
                changes_applied=changes,
            )
            
    except UniFiConnectionError as e:
        return UniFiWifiUpdateOutput(success=False, error=f"Connection error: {e}")
    except UniFiAuthError as e:
        return UniFiWifiUpdateOutput(success=False, error=f"Authentication error: {e}")
    except UniFiAPIError as e:
        return UniFiWifiUpdateOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        return UniFiWifiUpdateOutput(success=False, error=f"Unexpected error: {e}")

