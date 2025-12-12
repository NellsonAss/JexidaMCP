"""UniFi connected clients tool.

Provides the unifi_list_clients tool for retrieving all connected WiFi and wired clients.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from logging_config import get_logger, ToolInvocationLogger
from tool_registry import tool

from .client import UniFiClient, UniFiConnectionError, UniFiAuthError, UniFiAPIError

logger = get_logger(__name__)


class UniFiListClientsInput(BaseModel):
    """Input schema for unifi_list_clients tool."""
    
    site_id: Optional[str] = Field(
        default=None,
        description="UniFi site ID (defaults to configured site)"
    )
    wifi_only: bool = Field(
        default=False,
        description="Only return WiFi clients (exclude wired)"
    )


class UniFiClientInfo(BaseModel):
    """Single client device information."""
    
    name: str = Field(description="Device name or hostname")
    hostname: str = Field(default="", description="Hostname")
    mac: str = Field(description="MAC address")
    ip: str = Field(description="IP address")
    is_wired: bool = Field(description="True if wired, False if WiFi")
    network: str = Field(default="", description="WiFi network name (SSID) or network")
    signal: int = Field(default=0, description="Signal strength (dBm)")
    uptime_seconds: int = Field(default=0, description="Connection uptime in seconds")


class UniFiListClientsOutput(BaseModel):
    """Output schema for unifi_list_clients tool."""
    
    success: bool = Field(description="Whether the operation succeeded")
    clients: List[UniFiClientInfo] = Field(
        default_factory=list,
        description="List of connected clients"
    )
    total_count: int = Field(default=0, description="Total number of clients")
    wifi_count: int = Field(default=0, description="Number of WiFi clients")
    wired_count: int = Field(default=0, description="Number of wired clients")
    error: str = Field(default="", description="Error message if failed")


@tool(
    name="unifi_list_clients",
    description="List all connected client devices (WiFi and wired) from the UniFi controller",
    input_schema=UniFiListClientsInput,
    output_schema=UniFiListClientsOutput,
    tags=["unifi", "network", "clients", "wifi"]
)
async def unifi_list_clients(params: UniFiListClientsInput) -> UniFiListClientsOutput:
    """List all connected clients from the UniFi controller.
    
    Args:
        params: Input parameters with optional site_id and wifi_only flag
        
    Returns:
        List of connected client devices with their details
    """
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("unifi_list_clients", site_id=params.site_id, wifi_only=params.wifi_only)
    
    try:
        async with UniFiClient(site=params.site_id) as client:
            clients = await client.get_clients()
            
            wifi_clients = [c for c in clients if not c.get("is_wired", False)]
            wired_clients = [c for c in clients if c.get("is_wired", False)]
            
            if params.wifi_only:
                clients = wifi_clients
            
            client_list = [
                UniFiClientInfo(
                    name=c["name"],
                    hostname=c.get("hostname", ""),
                    mac=c["mac"],
                    ip=c.get("ip", ""),
                    is_wired=c.get("is_wired", False),
                    network=c.get("network", ""),
                    signal=c.get("signal", 0),
                    uptime_seconds=c.get("uptime_seconds", 0),
                )
                for c in clients
            ]
            
            invocation_logger.success(
                total_count=len(client_list),
                wifi_count=len(wifi_clients),
                wired_count=len(wired_clients),
            )
            
            return UniFiListClientsOutput(
                success=True,
                clients=client_list,
                total_count=len(client_list),
                wifi_count=len(wifi_clients),
                wired_count=len(wired_clients),
            )
            
    except UniFiConnectionError as e:
        invocation_logger.failure(str(e))
        return UniFiListClientsOutput(
            success=False,
            error=f"Connection error: {e}",
        )
    except UniFiAuthError as e:
        invocation_logger.failure(str(e))
        return UniFiListClientsOutput(
            success=False,
            error=f"Authentication error: {e}",
        )
    except UniFiAPIError as e:
        invocation_logger.failure(str(e))
        return UniFiListClientsOutput(
            success=False,
            error=f"API error: {e}",
        )
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return UniFiListClientsOutput(
            success=False,
            error=f"Unexpected error: {e}",
        )

