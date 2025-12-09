"""Synology Shared Folder tools.

Provides MCP tools for managing shared folders on Synology NAS.
"""

from typing import List, Optional

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

class SharedFolderOutput(BaseModel):
    """Shared folder information."""
    name: str = Field(description="Folder name")
    path: str = Field(description="Folder path")
    vol_path: str = Field(description="Volume path")
    desc: str = Field(description="Description")
    enable_recycle_bin: bool = Field(description="Recycle bin enabled")
    encryption: int = Field(description="Encryption status")
    is_aclmode: bool = Field(description="ACL mode enabled")


class SynologyListSharedFoldersInput(BaseModel):
    """Input schema for synology_list_shared_folders tool."""
    pass


class SynologyListSharedFoldersOutput(BaseModel):
    """Output schema for synology_list_shared_folders tool."""
    success: bool = Field(description="Whether the operation succeeded")
    folders: List[SharedFolderOutput] = Field(
        default_factory=list,
        description="List of shared folders"
    )
    folder_count: int = Field(default=0, description="Number of folders")
    error: str = Field(default="", description="Error message if failed")


class SynologyGetSharedFolderInfoInput(BaseModel):
    """Input schema for synology_get_shared_folder_info tool."""
    name: str = Field(description="Shared folder name")


class SynologyGetSharedFolderInfoOutput(BaseModel):
    """Output schema for synology_get_shared_folder_info tool."""
    success: bool = Field(description="Whether the operation succeeded")
    folder: Optional[SharedFolderOutput] = Field(
        default=None,
        description="Shared folder information"
    )
    error: str = Field(default="", description="Error message if failed")


class SynologyCreateSharedFolderInput(BaseModel):
    """Input schema for synology_create_shared_folder tool."""
    name: str = Field(description="Shared folder name")
    vol_path: str = Field(default="/volume1", description="Volume path")
    desc: str = Field(default="", description="Description")
    enable_recycle_bin: bool = Field(default=True, description="Enable recycle bin")


class SynologyCreateSharedFolderOutput(BaseModel):
    """Output schema for synology_create_shared_folder tool."""
    success: bool = Field(description="Whether the operation succeeded")
    name: str = Field(default="", description="Created folder name")
    error: str = Field(default="", description="Error message if failed")


class SynologyDeleteSharedFolderInput(BaseModel):
    """Input schema for synology_delete_shared_folder tool."""
    name: str = Field(description="Shared folder name to delete")


class SynologyDeleteSharedFolderOutput(BaseModel):
    """Output schema for synology_delete_shared_folder tool."""
    success: bool = Field(description="Whether the operation succeeded")
    error: str = Field(default="", description="Error message if failed")


# -----------------------------------------------------------------------------
# Tool Implementations
# -----------------------------------------------------------------------------

@tool(
    name="synology_list_shared_folders",
    description="List all shared folders on Synology NAS",
    input_schema=SynologyListSharedFoldersInput,
    output_schema=SynologyListSharedFoldersOutput,
    tags=["synology", "storage", "shares"]
)
async def synology_list_shared_folders(params: SynologyListSharedFoldersInput) -> SynologyListSharedFoldersOutput:
    """List all shared folders."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_list_shared_folders")
    
    try:
        async with SynologyClient() as client:
            folders = await client.list_shared_folders()
            
            folder_list = [
                SharedFolderOutput(
                    name=f.get("name", ""),
                    path=f.get("path", ""),
                    vol_path=f.get("vol_path", ""),
                    desc=f.get("desc", ""),
                    enable_recycle_bin=f.get("enable_recycle_bin", False),
                    encryption=f.get("encryption", 0),
                    is_aclmode=f.get("is_aclmode", False),
                )
                for f in folders
            ]
            
            invocation_logger.success(folder_count=len(folder_list))
            
            return SynologyListSharedFoldersOutput(
                success=True,
                folders=folder_list,
                folder_count=len(folder_list),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyListSharedFoldersOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyListSharedFoldersOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyListSharedFoldersOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyListSharedFoldersOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_get_shared_folder_info",
    description="Get information about a specific shared folder on Synology NAS",
    input_schema=SynologyGetSharedFolderInfoInput,
    output_schema=SynologyGetSharedFolderInfoOutput,
    tags=["synology", "storage", "shares"]
)
async def synology_get_shared_folder_info(params: SynologyGetSharedFolderInfoInput) -> SynologyGetSharedFolderInfoOutput:
    """Get shared folder information."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_get_shared_folder_info", name=params.name)
    
    try:
        async with SynologyClient() as client:
            folder = await client.get_shared_folder_info(params.name)
            
            invocation_logger.success()
            
            return SynologyGetSharedFolderInfoOutput(
                success=True,
                folder=SharedFolderOutput(
                    name=folder.get("name", ""),
                    path=folder.get("path", ""),
                    vol_path=folder.get("vol_path", ""),
                    desc=folder.get("desc", ""),
                    enable_recycle_bin=folder.get("enable_recycle_bin", False),
                    encryption=folder.get("encryption", 0),
                    is_aclmode=folder.get("is_aclmode", False),
                ),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyGetSharedFolderInfoOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyGetSharedFolderInfoOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyGetSharedFolderInfoOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyGetSharedFolderInfoOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_create_shared_folder",
    description="Create a new shared folder on Synology NAS",
    input_schema=SynologyCreateSharedFolderInput,
    output_schema=SynologyCreateSharedFolderOutput,
    tags=["synology", "storage", "shares"]
)
async def synology_create_shared_folder(params: SynologyCreateSharedFolderInput) -> SynologyCreateSharedFolderOutput:
    """Create a new shared folder."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_create_shared_folder", name=params.name)
    
    try:
        async with SynologyClient() as client:
            await client.create_shared_folder(
                name=params.name,
                vol_path=params.vol_path,
                desc=params.desc,
                enable_recycle_bin=params.enable_recycle_bin,
            )
            
            invocation_logger.success()
            
            return SynologyCreateSharedFolderOutput(
                success=True,
                name=params.name,
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyCreateSharedFolderOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyCreateSharedFolderOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyCreateSharedFolderOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyCreateSharedFolderOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_delete_shared_folder",
    description="Delete a shared folder from Synology NAS",
    input_schema=SynologyDeleteSharedFolderInput,
    output_schema=SynologyDeleteSharedFolderOutput,
    tags=["synology", "storage", "shares"]
)
async def synology_delete_shared_folder(params: SynologyDeleteSharedFolderInput) -> SynologyDeleteSharedFolderOutput:
    """Delete a shared folder."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_delete_shared_folder", name=params.name)
    
    try:
        async with SynologyClient() as client:
            await client.delete_shared_folder(params.name)
            
            invocation_logger.success()
            
            return SynologyDeleteSharedFolderOutput(success=True)
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyDeleteSharedFolderOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyDeleteSharedFolderOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyDeleteSharedFolderOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyDeleteSharedFolderOutput(success=False, error=f"Unexpected error: {e}")

