"""Synology Network configuration tools.

Provides MCP tools for managing network settings on Synology NAS.
"""

from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field

from logging_config import get_logger, ToolInvocationLogger
from tool_registry import tool

from .client import (
    SynologyClient,
    SynologyConnectionError,
    SynologyAuthError,
    SynologyAPIError,
)

logger = get_logger(__name__)


# -----------------------------------------------------------------------------
# Input/Output Schemas
# -----------------------------------------------------------------------------

class NetworkInterfaceOutput(BaseModel):
    """Network interface information."""
    id: str = Field(description="Interface ID")
    name: str = Field(description="Interface name")
    ip: str = Field(description="IP address")
    mask: str = Field(description="Subnet mask")
    mac: str = Field(description="MAC address")
    type: str = Field(description="Interface type")
    status: str = Field(description="Interface status")


class SynologyGetNetworkConfigInput(BaseModel):
    """Input schema for synology_get_network_config tool."""
    pass


class SynologyGetNetworkConfigOutput(BaseModel):
    """Output schema for synology_get_network_config tool."""
    success: bool = Field(description="Whether the operation succeeded")
    hostname: str = Field(default="", description="NAS hostname")
    workgroup: str = Field(default="", description="Workgroup name")
    dns: List[str] = Field(default_factory=list, description="DNS servers")
    gateway: str = Field(default="", description="Default gateway")
    error: str = Field(default="", description="Error message if failed")


class SynologyListNetworkInterfacesInput(BaseModel):
    """Input schema for synology_list_network_interfaces tool."""
    pass


class SynologyListNetworkInterfacesOutput(BaseModel):
    """Output schema for synology_list_network_interfaces tool."""
    success: bool = Field(description="Whether the operation succeeded")
    interfaces: List[NetworkInterfaceOutput] = Field(
        default_factory=list,
        description="List of network interfaces"
    )
    interface_count: int = Field(default=0, description="Number of interfaces")
    error: str = Field(default="", description="Error message if failed")


# -----------------------------------------------------------------------------
# Tool Implementations
# -----------------------------------------------------------------------------

@tool(
    name="synology_get_network_config",
    description="Get network configuration from Synology NAS (hostname, DNS, gateway)",
    input_schema=SynologyGetNetworkConfigInput,
    output_schema=SynologyGetNetworkConfigOutput,
    tags=["synology", "network", "config"]
)
async def synology_get_network_config(params: SynologyGetNetworkConfigInput) -> SynologyGetNetworkConfigOutput:
    """Get network configuration."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_get_network_config")
    
    try:
        async with SynologyClient() as client:
            config = await client.get_network_config()
            
            invocation_logger.success()
            
            return SynologyGetNetworkConfigOutput(
                success=True,
                hostname=config.get("hostname", ""),
                workgroup=config.get("workgroup", ""),
                dns=config.get("dns", []),
                gateway=config.get("gateway", ""),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyGetNetworkConfigOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyGetNetworkConfigOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyGetNetworkConfigOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyGetNetworkConfigOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_list_network_interfaces",
    description="List network interfaces on Synology NAS",
    input_schema=SynologyListNetworkInterfacesInput,
    output_schema=SynologyListNetworkInterfacesOutput,
    tags=["synology", "network", "interfaces"]
)
async def synology_list_network_interfaces(params: SynologyListNetworkInterfacesInput) -> SynologyListNetworkInterfacesOutput:
    """List network interfaces."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_list_network_interfaces")
    
    try:
        async with SynologyClient() as client:
            interfaces = await client.list_network_interfaces()
            
            interface_list = [
                NetworkInterfaceOutput(
                    id=iface.get("id", ""),
                    name=iface.get("name", ""),
                    ip=iface.get("ip", ""),
                    mask=iface.get("mask", ""),
                    mac=iface.get("mac", ""),
                    type=iface.get("type", ""),
                    status=iface.get("status", ""),
                )
                for iface in interfaces
            ]
            
            invocation_logger.success(interface_count=len(interface_list))
            
            return SynologyListNetworkInterfacesOutput(
                success=True,
                interfaces=interface_list,
                interface_count=len(interface_list),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyListNetworkInterfacesOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyListNetworkInterfacesOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyListNetworkInterfacesOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyListNetworkInterfacesOutput(success=False, error=f"Unexpected error: {e}")

