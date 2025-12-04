"""Synology system information tools.

Provides MCP tools for retrieving system information from Synology NAS.
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
    SynologySystemInfo,
    SynologyStorageVolume,
)

logger = get_logger(__name__)


# -----------------------------------------------------------------------------
# Input/Output Schemas
# -----------------------------------------------------------------------------

class SynologyGetSystemInfoInput(BaseModel):
    """Input schema for synology_get_system_info tool."""
    pass  # No parameters needed


class SystemInfoOutput(BaseModel):
    """System information output."""
    model: str = Field(description="NAS model")
    serial: str = Field(description="Serial number")
    firmware_version: str = Field(description="DSM firmware version")
    uptime_seconds: int = Field(description="System uptime in seconds")
    cpu_usage_percent: float = Field(description="CPU usage percentage")
    memory_usage_percent: float = Field(description="Memory usage percentage")
    memory_total_mb: int = Field(description="Total memory in MB")
    memory_used_mb: int = Field(description="Used memory in MB")
    temperature: Optional[int] = Field(default=None, description="System temperature in Celsius")


class SynologyGetSystemInfoOutput(BaseModel):
    """Output schema for synology_get_system_info tool."""
    success: bool = Field(description="Whether the operation succeeded")
    info: Optional[SystemInfoOutput] = Field(
        default=None,
        description="System information"
    )
    error: str = Field(default="", description="Error message if failed")


class SynologyGetStorageInfoInput(BaseModel):
    """Input schema for synology_get_storage_info tool."""
    pass  # No parameters needed


class StorageVolumeOutput(BaseModel):
    """Storage volume information."""
    id: str = Field(description="Volume ID")
    status: str = Field(description="Volume status")
    total_size: int = Field(description="Total size in bytes")
    used_size: int = Field(description="Used size in bytes")
    free_size: int = Field(description="Free size in bytes")
    usage_percent: float = Field(description="Usage percentage")


class SynologyGetStorageInfoOutput(BaseModel):
    """Output schema for synology_get_storage_info tool."""
    success: bool = Field(description="Whether the operation succeeded")
    volumes: List[StorageVolumeOutput] = Field(
        default_factory=list,
        description="List of storage volumes"
    )
    volume_count: int = Field(default=0, description="Number of volumes")
    error: str = Field(default="", description="Error message if failed")


class SynologyGetNetworkInfoInput(BaseModel):
    """Input schema for synology_get_network_info tool."""
    pass  # No parameters needed


class SynologyGetNetworkInfoOutput(BaseModel):
    """Output schema for synology_get_network_info tool."""
    success: bool = Field(description="Whether the operation succeeded")
    hostname: str = Field(default="", description="NAS hostname")
    dns_name: str = Field(default="", description="DNS name")
    error: str = Field(default="", description="Error message if failed")


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def _system_info_to_output(info: SynologySystemInfo) -> SystemInfoOutput:
    """Convert SynologySystemInfo to SystemInfoOutput."""
    return SystemInfoOutput(
        model=info.model,
        serial=info.serial,
        firmware_version=info.firmware_version,
        uptime_seconds=info.uptime_seconds,
        cpu_usage_percent=info.cpu_usage_percent,
        memory_usage_percent=info.memory_usage_percent,
        memory_total_mb=info.memory_total_mb,
        memory_used_mb=info.memory_used_mb,
        temperature=info.temperature,
    )


def _volume_to_output(vol: SynologyStorageVolume) -> StorageVolumeOutput:
    """Convert SynologyStorageVolume to StorageVolumeOutput."""
    return StorageVolumeOutput(
        id=vol.id,
        status=vol.status,
        total_size=vol.total_size,
        used_size=vol.used_size,
        free_size=vol.free_size,
        usage_percent=vol.usage_percent,
    )


# -----------------------------------------------------------------------------
# Tool Implementations
# -----------------------------------------------------------------------------

@tool(
    name="synology_get_system_info",
    description="Get system information from Synology NAS including CPU, memory, and uptime",
    input_schema=SynologyGetSystemInfoInput,
    output_schema=SynologyGetSystemInfoOutput,
    tags=["synology", "system", "monitoring"]
)
async def synology_get_system_info(params: SynologyGetSystemInfoInput) -> SynologyGetSystemInfoOutput:
    """Get system information."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_get_system_info")
    
    try:
        async with SynologyClient() as client:
            info = await client.get_system_info()
            
            invocation_logger.success(model=info.model)
            
            return SynologyGetSystemInfoOutput(
                success=True,
                info=_system_info_to_output(info),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyGetSystemInfoOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyGetSystemInfoOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyGetSystemInfoOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyGetSystemInfoOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_get_storage_info",
    description="Get storage volume information from Synology NAS",
    input_schema=SynologyGetStorageInfoInput,
    output_schema=SynologyGetStorageInfoOutput,
    tags=["synology", "system", "storage"]
)
async def synology_get_storage_info(params: SynologyGetStorageInfoInput) -> SynologyGetStorageInfoOutput:
    """Get storage volume information."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_get_storage_info")
    
    try:
        async with SynologyClient() as client:
            volumes = await client.get_storage_info()
            
            volume_list = [_volume_to_output(v) for v in volumes]
            
            invocation_logger.success(volume_count=len(volume_list))
            
            return SynologyGetStorageInfoOutput(
                success=True,
                volumes=volume_list,
                volume_count=len(volume_list),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyGetStorageInfoOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyGetStorageInfoOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyGetStorageInfoOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyGetStorageInfoOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_get_network_info",
    description="Get network information from Synology NAS",
    input_schema=SynologyGetNetworkInfoInput,
    output_schema=SynologyGetNetworkInfoOutput,
    tags=["synology", "system", "network"]
)
async def synology_get_network_info(params: SynologyGetNetworkInfoInput) -> SynologyGetNetworkInfoOutput:
    """Get network information."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_get_network_info")
    
    try:
        async with SynologyClient() as client:
            network = await client.get_network_info()
            
            invocation_logger.success(hostname=network.get("hostname", ""))
            
            return SynologyGetNetworkInfoOutput(
                success=True,
                hostname=network.get("hostname", ""),
                dns_name=network.get("dns", ""),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyGetNetworkInfoOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyGetNetworkInfoOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyGetNetworkInfoOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyGetNetworkInfoOutput(success=False, error=f"Unexpected error: {e}")

