"""UniFi device inventory tool.

Provides the unifi_list_devices tool for retrieving all UniFi devices.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from logging_config import get_logger, ToolInvocationLogger
from tool_registry import tool

from .client import UniFiClient, UniFiConnectionError, UniFiAuthError, UniFiAPIError

logger = get_logger(__name__)


class UniFiListDevicesInput(BaseModel):
    """Input schema for unifi_list_devices tool."""
    
    site_id: Optional[str] = Field(
        default=None,
        description="UniFi site ID (defaults to configured site)"
    )


class UniFiDeviceInfo(BaseModel):
    """Single device information."""
    
    name: str = Field(description="Device name")
    model: str = Field(description="Device model")
    type: str = Field(description="Device type: gateway, switch, ap, or other")
    ip: str = Field(description="Device IP address")
    mac: str = Field(description="Device MAC address")
    firmware: str = Field(description="Firmware version")
    adopted: bool = Field(description="Whether device is adopted")
    uptime_seconds: int = Field(description="Uptime in seconds")


class UniFiListDevicesOutput(BaseModel):
    """Output schema for unifi_list_devices tool."""
    
    success: bool = Field(description="Whether the operation succeeded")
    devices: List[UniFiDeviceInfo] = Field(
        default_factory=list,
        description="List of UniFi devices"
    )
    device_count: int = Field(default=0, description="Total number of devices")
    error: str = Field(default="", description="Error message if failed")


@tool(
    name="unifi_list_devices",
    description="List all UniFi devices (gateways, switches, access points) from the controller",
    input_schema=UniFiListDevicesInput,
    output_schema=UniFiListDevicesOutput,
    tags=["unifi", "network", "inventory"]
)
async def unifi_list_devices(params: UniFiListDevicesInput) -> UniFiListDevicesOutput:
    """List all UniFi devices from the controller.
    
    Args:
        params: Input parameters with optional site_id
        
    Returns:
        List of devices with their details
    """
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("unifi_list_devices", site_id=params.site_id)
    
    try:
        async with UniFiClient(site=params.site_id) as client:
            devices = await client.get_devices()
            
            device_list = [
                UniFiDeviceInfo(
                    name=dev.name,
                    model=dev.model,
                    type=dev.device_type,
                    ip=dev.ip,
                    mac=dev.mac,
                    firmware=dev.firmware,
                    adopted=dev.adopted,
                    uptime_seconds=dev.uptime_seconds,
                )
                for dev in devices
            ]
            
            invocation_logger.success(device_count=len(device_list))
            
            return UniFiListDevicesOutput(
                success=True,
                devices=device_list,
                device_count=len(device_list),
            )
            
    except UniFiConnectionError as e:
        invocation_logger.failure(str(e))
        return UniFiListDevicesOutput(
            success=False,
            error=f"Connection error: {e}",
        )
    except UniFiAuthError as e:
        invocation_logger.failure(str(e))
        return UniFiListDevicesOutput(
            success=False,
            error=f"Authentication error: {e}",
        )
    except UniFiAPIError as e:
        invocation_logger.failure(str(e))
        return UniFiListDevicesOutput(
            success=False,
            error=f"API error: {e}",
        )
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return UniFiListDevicesOutput(
            success=False,
            error=f"Unexpected error: {e}",
        )

