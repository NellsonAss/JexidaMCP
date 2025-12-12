"""Synology Log Center and Resource Monitor tools.

Provides MCP tools for monitoring and logs on Synology NAS.
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

class LogEntryOutput(BaseModel):
    """System log entry."""
    time: int = Field(description="Log timestamp")
    user: str = Field(description="User associated with log")
    event: str = Field(description="Event type")
    ip: str = Field(description="IP address")
    desc: str = Field(description="Description")


class ResourceUsageOutput(BaseModel):
    """Resource usage information."""
    cpu_user_load: float = Field(description="CPU user load percentage")
    cpu_system_load: float = Field(description="CPU system load percentage")
    cpu_total_load: float = Field(description="CPU total load percentage")
    memory_total: int = Field(description="Total memory in bytes")
    memory_available: int = Field(description="Available memory in bytes")
    memory_usage_percent: float = Field(description="Memory usage percentage")
    disk_read_access: int = Field(description="Disk read access count")
    disk_write_access: int = Field(description="Disk write access count")
    disk_utilization: float = Field(description="Disk utilization percentage")


class SynologyListLogsInput(BaseModel):
    """Input schema for synology_list_logs tool."""
    log_type: str = Field(default="connection", description="Log type: connection, transfer, etc.")
    offset: int = Field(default=0, description="Starting offset")
    limit: int = Field(default=100, description="Maximum logs to return")


class SynologyListLogsOutput(BaseModel):
    """Output schema for synology_list_logs tool."""
    success: bool = Field(description="Whether the operation succeeded")
    logs: List[LogEntryOutput] = Field(
        default_factory=list,
        description="List of log entries"
    )
    log_count: int = Field(default=0, description="Number of logs returned")
    error: str = Field(default="", description="Error message if failed")


class SynologyGetResourceUsageInput(BaseModel):
    """Input schema for synology_get_resource_usage tool."""
    pass


class SynologyGetResourceUsageOutput(BaseModel):
    """Output schema for synology_get_resource_usage tool."""
    success: bool = Field(description="Whether the operation succeeded")
    usage: Optional[ResourceUsageOutput] = Field(
        default=None,
        description="Resource usage information"
    )
    error: str = Field(default="", description="Error message if failed")


class SynologyListPhotoAlbumsInput(BaseModel):
    """Input schema for synology_list_photo_albums tool."""
    pass


class PhotoAlbumOutput(BaseModel):
    """Photo album information."""
    id: int = Field(description="Album ID")
    name: str = Field(description="Album name")
    item_count: int = Field(description="Number of items")
    create_time: int = Field(description="Creation timestamp")
    type: str = Field(description="Album type")


class SynologyListPhotoAlbumsOutput(BaseModel):
    """Output schema for synology_list_photo_albums tool."""
    success: bool = Field(description="Whether the operation succeeded")
    albums: List[PhotoAlbumOutput] = Field(
        default_factory=list,
        description="List of photo albums"
    )
    album_count: int = Field(default=0, description="Number of albums")
    error: str = Field(default="", description="Error message if failed")


class SynologyGetDriveStatusInput(BaseModel):
    """Input schema for synology_get_drive_status tool."""
    pass


class SynologyGetDriveStatusOutput(BaseModel):
    """Output schema for synology_get_drive_status tool."""
    success: bool = Field(description="Whether the operation succeeded")
    version: str = Field(default="", description="Synology Drive version")
    status: str = Field(default="", description="Drive status")
    error: str = Field(default="", description="Error message if failed")


class DriveTeamFolderOutput(BaseModel):
    """Synology Drive team folder information."""
    id: str = Field(description="Folder ID")
    name: str = Field(description="Folder name")
    share_name: str = Field(description="Associated shared folder")
    enable_version: bool = Field(description="Version control enabled")


class SynologyListDriveTeamFoldersInput(BaseModel):
    """Input schema for synology_list_drive_team_folders tool."""
    pass


class SynologyListDriveTeamFoldersOutput(BaseModel):
    """Output schema for synology_list_drive_team_folders tool."""
    success: bool = Field(description="Whether the operation succeeded")
    folders: List[DriveTeamFolderOutput] = Field(
        default_factory=list,
        description="List of team folders"
    )
    folder_count: int = Field(default=0, description="Number of folders")
    error: str = Field(default="", description="Error message if failed")


# -----------------------------------------------------------------------------
# Tool Implementations
# -----------------------------------------------------------------------------

@tool(
    name="synology_list_logs",
    description="List system logs from Synology NAS Log Center",
    input_schema=SynologyListLogsInput,
    output_schema=SynologyListLogsOutput,
    tags=["synology", "logs", "monitoring"]
)
async def synology_list_logs(params: SynologyListLogsInput) -> SynologyListLogsOutput:
    """List system logs."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_list_logs", log_type=params.log_type)
    
    try:
        async with SynologyClient() as client:
            logs = await client.list_logs(
                log_type=params.log_type,
                offset=params.offset,
                limit=params.limit,
            )
            
            log_list = [
                LogEntryOutput(
                    time=log.get("time", 0),
                    user=log.get("user", ""),
                    event=log.get("event", ""),
                    ip=log.get("ip", ""),
                    desc=log.get("desc", ""),
                )
                for log in logs
            ]
            
            invocation_logger.success(log_count=len(log_list))
            
            return SynologyListLogsOutput(
                success=True,
                logs=log_list,
                log_count=len(log_list),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyListLogsOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyListLogsOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyListLogsOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyListLogsOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_get_resource_usage",
    description="Get current resource usage from Synology NAS (CPU, memory, disk, network)",
    input_schema=SynologyGetResourceUsageInput,
    output_schema=SynologyGetResourceUsageOutput,
    tags=["synology", "monitoring", "resources"]
)
async def synology_get_resource_usage(params: SynologyGetResourceUsageInput) -> SynologyGetResourceUsageOutput:
    """Get current resource usage."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_get_resource_usage")
    
    try:
        async with SynologyClient() as client:
            usage = await client.get_resource_usage()
            
            cpu = usage.get("cpu", {})
            memory = usage.get("memory", {})
            disk = usage.get("disk", {})
            
            invocation_logger.success()
            
            return SynologyGetResourceUsageOutput(
                success=True,
                usage=ResourceUsageOutput(
                    cpu_user_load=cpu.get("user_load", 0),
                    cpu_system_load=cpu.get("system_load", 0),
                    cpu_total_load=cpu.get("total_load", 0),
                    memory_total=memory.get("total_real", 0),
                    memory_available=memory.get("avail_real", 0),
                    memory_usage_percent=memory.get("real_usage", 0),
                    disk_read_access=disk.get("read_access", 0),
                    disk_write_access=disk.get("write_access", 0),
                    disk_utilization=disk.get("utilization", 0),
                ),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyGetResourceUsageOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyGetResourceUsageOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyGetResourceUsageOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyGetResourceUsageOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_list_photo_albums",
    description="List photo albums in Synology Photos",
    input_schema=SynologyListPhotoAlbumsInput,
    output_schema=SynologyListPhotoAlbumsOutput,
    tags=["synology", "photos", "media"]
)
async def synology_list_photo_albums(params: SynologyListPhotoAlbumsInput) -> SynologyListPhotoAlbumsOutput:
    """List photo albums."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_list_photo_albums")
    
    try:
        async with SynologyClient() as client:
            albums = await client.list_photo_albums()
            
            album_list = [
                PhotoAlbumOutput(
                    id=a.get("id", 0),
                    name=a.get("name", ""),
                    item_count=a.get("item_count", 0),
                    create_time=a.get("create_time", 0),
                    type=a.get("type", ""),
                )
                for a in albums
            ]
            
            invocation_logger.success(album_count=len(album_list))
            
            return SynologyListPhotoAlbumsOutput(
                success=True,
                albums=album_list,
                album_count=len(album_list),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyListPhotoAlbumsOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyListPhotoAlbumsOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyListPhotoAlbumsOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyListPhotoAlbumsOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_get_drive_status",
    description="Get Synology Drive status and version",
    input_schema=SynologyGetDriveStatusInput,
    output_schema=SynologyGetDriveStatusOutput,
    tags=["synology", "drive", "sync"]
)
async def synology_get_drive_status(params: SynologyGetDriveStatusInput) -> SynologyGetDriveStatusOutput:
    """Get Synology Drive status."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_get_drive_status")
    
    try:
        async with SynologyClient() as client:
            status = await client.get_drive_status()
            
            invocation_logger.success()
            
            return SynologyGetDriveStatusOutput(
                success=True,
                version=status.get("version", ""),
                status=status.get("status", ""),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyGetDriveStatusOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyGetDriveStatusOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyGetDriveStatusOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyGetDriveStatusOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_list_drive_team_folders",
    description="List Synology Drive team folders",
    input_schema=SynologyListDriveTeamFoldersInput,
    output_schema=SynologyListDriveTeamFoldersOutput,
    tags=["synology", "drive", "sync"]
)
async def synology_list_drive_team_folders(params: SynologyListDriveTeamFoldersInput) -> SynologyListDriveTeamFoldersOutput:
    """List Synology Drive team folders."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_list_drive_team_folders")
    
    try:
        async with SynologyClient() as client:
            folders = await client.list_drive_team_folders()
            
            folder_list = [
                DriveTeamFolderOutput(
                    id=f.get("id", ""),
                    name=f.get("name", ""),
                    share_name=f.get("share_name", ""),
                    enable_version=f.get("enable_version", False),
                )
                for f in folders
            ]
            
            invocation_logger.success(folder_count=len(folder_list))
            
            return SynologyListDriveTeamFoldersOutput(
                success=True,
                folders=folder_list,
                folder_count=len(folder_list),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyListDriveTeamFoldersOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyListDriveTeamFoldersOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyListDriveTeamFoldersOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyListDriveTeamFoldersOutput(success=False, error=f"Unexpected error: {e}")

