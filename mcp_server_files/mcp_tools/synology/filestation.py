"""Synology FileStation tools.

Provides MCP tools for file operations on Synology NAS.
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
    SynologyFileInfo,
)

logger = get_logger(__name__)


# -----------------------------------------------------------------------------
# Input/Output Schemas
# -----------------------------------------------------------------------------

class SynologyListFilesInput(BaseModel):
    """Input schema for synology_list_files tool."""
    folder_path: str = Field(
        default="/",
        description="Folder path to list (e.g., /volume1/shared)"
    )
    offset: int = Field(default=0, description="Starting offset")
    limit: int = Field(default=100, description="Maximum items to return")
    sort_by: str = Field(default="name", description="Sort field: name, size, mtime")
    sort_direction: str = Field(default="asc", description="Sort direction: asc, desc")


class FileInfoOutput(BaseModel):
    """Single file/folder information."""
    name: str = Field(description="File/folder name")
    path: str = Field(description="Full path")
    is_dir: bool = Field(description="Whether this is a directory")
    size: int = Field(description="Size in bytes")
    create_time: int = Field(description="Creation timestamp")
    modify_time: int = Field(description="Modification timestamp")
    owner: str = Field(description="Owner username")


class SynologyListFilesOutput(BaseModel):
    """Output schema for synology_list_files tool."""
    success: bool = Field(description="Whether the operation succeeded")
    files: List[FileInfoOutput] = Field(
        default_factory=list,
        description="List of files and folders"
    )
    file_count: int = Field(default=0, description="Number of items returned")
    error: str = Field(default="", description="Error message if failed")


class SynologyGetFileInfoInput(BaseModel):
    """Input schema for synology_get_file_info tool."""
    path: str = Field(description="Path to file or folder")


class SynologyGetFileInfoOutput(BaseModel):
    """Output schema for synology_get_file_info tool."""
    success: bool = Field(description="Whether the operation succeeded")
    file: Optional[FileInfoOutput] = Field(
        default=None,
        description="File information"
    )
    error: str = Field(default="", description="Error message if failed")


class SynologyCreateFolderInput(BaseModel):
    """Input schema for synology_create_folder tool."""
    folder_path: str = Field(description="Parent folder path")
    name: str = Field(description="Name of new folder")


class SynologyCreateFolderOutput(BaseModel):
    """Output schema for synology_create_folder tool."""
    success: bool = Field(description="Whether the operation succeeded")
    folder: Optional[FileInfoOutput] = Field(
        default=None,
        description="Created folder information"
    )
    error: str = Field(default="", description="Error message if failed")


class SynologyDeleteFilesInput(BaseModel):
    """Input schema for synology_delete_files tool."""
    paths: List[str] = Field(description="List of paths to delete")


class SynologyDeleteFilesOutput(BaseModel):
    """Output schema for synology_delete_files tool."""
    success: bool = Field(description="Whether the operation succeeded")
    deleted_count: int = Field(default=0, description="Number of items deleted")
    error: str = Field(default="", description="Error message if failed")


class SynologyMoveFilesInput(BaseModel):
    """Input schema for synology_move_files tool."""
    paths: List[str] = Field(description="Source paths to move")
    dest_folder: str = Field(description="Destination folder path")
    overwrite: bool = Field(default=False, description="Overwrite existing files")


class SynologyMoveFilesOutput(BaseModel):
    """Output schema for synology_move_files tool."""
    success: bool = Field(description="Whether the operation succeeded")
    moved_count: int = Field(default=0, description="Number of items moved")
    error: str = Field(default="", description="Error message if failed")


class SynologyRenameFileInput(BaseModel):
    """Input schema for synology_rename_file tool."""
    path: str = Field(description="Path to file/folder to rename")
    new_name: str = Field(description="New name")


class SynologyRenameFileOutput(BaseModel):
    """Output schema for synology_rename_file tool."""
    success: bool = Field(description="Whether the operation succeeded")
    file: Optional[FileInfoOutput] = Field(
        default=None,
        description="Renamed file information"
    )
    error: str = Field(default="", description="Error message if failed")


class SynologySearchFilesInput(BaseModel):
    """Input schema for synology_search_files tool."""
    folder_path: str = Field(description="Folder to search in")
    pattern: str = Field(description="Search pattern (supports wildcards)")
    extension: Optional[str] = Field(
        default=None,
        description="Filter by file extension (e.g., 'txt', 'pdf')"
    )
    file_type: str = Field(
        default="all",
        description="Filter by type: file, dir, or all"
    )


class SynologySearchFilesOutput(BaseModel):
    """Output schema for synology_search_files tool."""
    success: bool = Field(description="Whether the operation succeeded")
    files: List[FileInfoOutput] = Field(
        default_factory=list,
        description="List of matching files"
    )
    match_count: int = Field(default=0, description="Number of matches found")
    error: str = Field(default="", description="Error message if failed")


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def _file_info_to_output(info: SynologyFileInfo) -> FileInfoOutput:
    """Convert SynologyFileInfo to FileInfoOutput."""
    return FileInfoOutput(
        name=info.name,
        path=info.path,
        is_dir=info.is_dir,
        size=info.size,
        create_time=info.create_time,
        modify_time=info.modify_time,
        owner=info.owner,
    )


# -----------------------------------------------------------------------------
# Tool Implementations
# -----------------------------------------------------------------------------

@tool(
    name="synology_list_files",
    description="List files and folders in a Synology NAS directory",
    input_schema=SynologyListFilesInput,
    output_schema=SynologyListFilesOutput,
    tags=["synology", "filestation", "files"]
)
async def synology_list_files(params: SynologyListFilesInput) -> SynologyListFilesOutput:
    """List files and folders in a directory."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_list_files", folder_path=params.folder_path)
    
    try:
        async with SynologyClient() as client:
            files = await client.list_files(
                folder_path=params.folder_path,
                offset=params.offset,
                limit=params.limit,
                sort_by=params.sort_by,
                sort_direction=params.sort_direction,
            )
            
            file_list = [_file_info_to_output(f) for f in files]
            
            invocation_logger.success(file_count=len(file_list))
            
            return SynologyListFilesOutput(
                success=True,
                files=file_list,
                file_count=len(file_list),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyListFilesOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyListFilesOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyListFilesOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyListFilesOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_get_file_info",
    description="Get detailed information about a file or folder on Synology NAS",
    input_schema=SynologyGetFileInfoInput,
    output_schema=SynologyGetFileInfoOutput,
    tags=["synology", "filestation", "files"]
)
async def synology_get_file_info(params: SynologyGetFileInfoInput) -> SynologyGetFileInfoOutput:
    """Get information about a specific file or folder."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_get_file_info", path=params.path)
    
    try:
        async with SynologyClient() as client:
            info = await client.get_file_info(params.path)
            
            invocation_logger.success()
            
            return SynologyGetFileInfoOutput(
                success=True,
                file=_file_info_to_output(info),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyGetFileInfoOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyGetFileInfoOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyGetFileInfoOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyGetFileInfoOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_create_folder",
    description="Create a new folder on Synology NAS",
    input_schema=SynologyCreateFolderInput,
    output_schema=SynologyCreateFolderOutput,
    tags=["synology", "filestation", "files"]
)
async def synology_create_folder(params: SynologyCreateFolderInput) -> SynologyCreateFolderOutput:
    """Create a new folder."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_create_folder", folder_path=params.folder_path, name=params.name)
    
    try:
        async with SynologyClient() as client:
            folder = await client.create_folder(params.folder_path, params.name)
            
            invocation_logger.success()
            
            return SynologyCreateFolderOutput(
                success=True,
                folder=_file_info_to_output(folder),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyCreateFolderOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyCreateFolderOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyCreateFolderOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyCreateFolderOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_delete_files",
    description="Delete files or folders from Synology NAS",
    input_schema=SynologyDeleteFilesInput,
    output_schema=SynologyDeleteFilesOutput,
    tags=["synology", "filestation", "files"]
)
async def synology_delete_files(params: SynologyDeleteFilesInput) -> SynologyDeleteFilesOutput:
    """Delete files or folders."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_delete_files", paths=params.paths)
    
    try:
        async with SynologyClient() as client:
            await client.delete_files(params.paths)
            
            invocation_logger.success(deleted_count=len(params.paths))
            
            return SynologyDeleteFilesOutput(
                success=True,
                deleted_count=len(params.paths),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyDeleteFilesOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyDeleteFilesOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyDeleteFilesOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyDeleteFilesOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_move_files",
    description="Move files or folders to another location on Synology NAS",
    input_schema=SynologyMoveFilesInput,
    output_schema=SynologyMoveFilesOutput,
    tags=["synology", "filestation", "files"]
)
async def synology_move_files(params: SynologyMoveFilesInput) -> SynologyMoveFilesOutput:
    """Move files or folders."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_move_files", paths=params.paths, dest=params.dest_folder)
    
    try:
        async with SynologyClient() as client:
            await client.move_files(
                params.paths,
                params.dest_folder,
                overwrite=params.overwrite,
            )
            
            invocation_logger.success(moved_count=len(params.paths))
            
            return SynologyMoveFilesOutput(
                success=True,
                moved_count=len(params.paths),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyMoveFilesOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyMoveFilesOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyMoveFilesOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyMoveFilesOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_rename_file",
    description="Rename a file or folder on Synology NAS",
    input_schema=SynologyRenameFileInput,
    output_schema=SynologyRenameFileOutput,
    tags=["synology", "filestation", "files"]
)
async def synology_rename_file(params: SynologyRenameFileInput) -> SynologyRenameFileOutput:
    """Rename a file or folder."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_rename_file", path=params.path, new_name=params.new_name)
    
    try:
        async with SynologyClient() as client:
            file = await client.rename_file(params.path, params.new_name)
            
            invocation_logger.success()
            
            return SynologyRenameFileOutput(
                success=True,
                file=_file_info_to_output(file),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyRenameFileOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyRenameFileOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyRenameFileOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyRenameFileOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_search_files",
    description="Search for files on Synology NAS",
    input_schema=SynologySearchFilesInput,
    output_schema=SynologySearchFilesOutput,
    tags=["synology", "filestation", "files"]
)
async def synology_search_files(params: SynologySearchFilesInput) -> SynologySearchFilesOutput:
    """Search for files."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_search_files", folder=params.folder_path, pattern=params.pattern)
    
    try:
        async with SynologyClient() as client:
            files = await client.search_files(
                folder_path=params.folder_path,
                pattern=params.pattern,
                extension=params.extension,
                file_type=params.file_type if params.file_type != "all" else None,
            )
            
            file_list = [_file_info_to_output(f) for f in files]
            
            invocation_logger.success(match_count=len(file_list))
            
            return SynologySearchFilesOutput(
                success=True,
                files=file_list,
                match_count=len(file_list),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologySearchFilesOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologySearchFilesOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologySearchFilesOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologySearchFilesOutput(success=False, error=f"Unexpected error: {e}")

