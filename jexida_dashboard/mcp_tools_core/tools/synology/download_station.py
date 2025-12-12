"""Synology Download Station tools.

Provides MCP tools for managing downloads on Synology NAS.
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
    SynologyDownloadTask,
)

logger = get_logger(__name__)


# -----------------------------------------------------------------------------
# Input/Output Schemas
# -----------------------------------------------------------------------------

class DownloadTaskOutput(BaseModel):
    """Single download task information."""
    id: str = Field(description="Task ID")
    title: str = Field(description="Download title/filename")
    status: str = Field(description="Status: waiting, downloading, paused, finished, error")
    size: int = Field(description="Total size in bytes")
    size_downloaded: int = Field(description="Downloaded size in bytes")
    speed_download: int = Field(description="Download speed in bytes/sec")
    percent_done: float = Field(description="Completion percentage")
    destination: str = Field(description="Destination folder")


class SynologyListDownloadsInput(BaseModel):
    """Input schema for synology_list_downloads tool."""
    pass  # No parameters needed


class SynologyListDownloadsOutput(BaseModel):
    """Output schema for synology_list_downloads tool."""
    success: bool = Field(description="Whether the operation succeeded")
    tasks: List[DownloadTaskOutput] = Field(
        default_factory=list,
        description="List of download tasks"
    )
    task_count: int = Field(default=0, description="Number of tasks")
    error: str = Field(default="", description="Error message if failed")


class SynologyAddDownloadInput(BaseModel):
    """Input schema for synology_add_download tool."""
    uri: str = Field(description="URL or magnet link to download")
    destination: Optional[str] = Field(
        default=None,
        description="Destination folder path (optional)"
    )


class SynologyAddDownloadOutput(BaseModel):
    """Output schema for synology_add_download tool."""
    success: bool = Field(description="Whether the operation succeeded")
    task_id: str = Field(default="", description="Created task ID")
    error: str = Field(default="", description="Error message if failed")


class SynologyPauseDownloadInput(BaseModel):
    """Input schema for synology_pause_download tool."""
    task_id: str = Field(description="Task ID to pause")


class SynologyPauseDownloadOutput(BaseModel):
    """Output schema for synology_pause_download tool."""
    success: bool = Field(description="Whether the operation succeeded")
    error: str = Field(default="", description="Error message if failed")


class SynologyResumeDownloadInput(BaseModel):
    """Input schema for synology_resume_download tool."""
    task_id: str = Field(description="Task ID to resume")


class SynologyResumeDownloadOutput(BaseModel):
    """Output schema for synology_resume_download tool."""
    success: bool = Field(description="Whether the operation succeeded")
    error: str = Field(default="", description="Error message if failed")


class SynologyDeleteDownloadInput(BaseModel):
    """Input schema for synology_delete_download tool."""
    task_id: str = Field(description="Task ID to delete")
    force_complete: bool = Field(
        default=False,
        description="Delete even if download is not complete"
    )


class SynologyDeleteDownloadOutput(BaseModel):
    """Output schema for synology_delete_download tool."""
    success: bool = Field(description="Whether the operation succeeded")
    error: str = Field(default="", description="Error message if failed")


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def _task_to_output(task: SynologyDownloadTask) -> DownloadTaskOutput:
    """Convert SynologyDownloadTask to DownloadTaskOutput."""
    return DownloadTaskOutput(
        id=task.id,
        title=task.title,
        status=task.status,
        size=task.size,
        size_downloaded=task.size_downloaded,
        speed_download=task.speed_download,
        percent_done=task.percent_done,
        destination=task.destination,
    )


# -----------------------------------------------------------------------------
# Tool Implementations
# -----------------------------------------------------------------------------

@tool(
    name="synology_list_downloads",
    description="List all download tasks in Synology Download Station",
    input_schema=SynologyListDownloadsInput,
    output_schema=SynologyListDownloadsOutput,
    tags=["synology", "downloadstation", "downloads"]
)
async def synology_list_downloads(params: SynologyListDownloadsInput) -> SynologyListDownloadsOutput:
    """List all download tasks."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_list_downloads")
    
    try:
        async with SynologyClient() as client:
            tasks = await client.list_downloads()
            
            task_list = [_task_to_output(t) for t in tasks]
            
            invocation_logger.success(task_count=len(task_list))
            
            return SynologyListDownloadsOutput(
                success=True,
                tasks=task_list,
                task_count=len(task_list),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyListDownloadsOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyListDownloadsOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyListDownloadsOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyListDownloadsOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_add_download",
    description="Add a new download task to Synology Download Station (URL or magnet link)",
    input_schema=SynologyAddDownloadInput,
    output_schema=SynologyAddDownloadOutput,
    tags=["synology", "downloadstation", "downloads"]
)
async def synology_add_download(params: SynologyAddDownloadInput) -> SynologyAddDownloadOutput:
    """Add a new download task."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_add_download", uri=params.uri[:50])
    
    try:
        async with SynologyClient() as client:
            task_id = await client.add_download(
                uri=params.uri,
                destination=params.destination,
            )
            
            invocation_logger.success(task_id=task_id)
            
            return SynologyAddDownloadOutput(
                success=True,
                task_id=task_id,
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyAddDownloadOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyAddDownloadOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyAddDownloadOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyAddDownloadOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_pause_download",
    description="Pause a download task in Synology Download Station",
    input_schema=SynologyPauseDownloadInput,
    output_schema=SynologyPauseDownloadOutput,
    tags=["synology", "downloadstation", "downloads"]
)
async def synology_pause_download(params: SynologyPauseDownloadInput) -> SynologyPauseDownloadOutput:
    """Pause a download task."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_pause_download", task_id=params.task_id)
    
    try:
        async with SynologyClient() as client:
            await client.pause_download(params.task_id)
            
            invocation_logger.success()
            
            return SynologyPauseDownloadOutput(success=True)
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyPauseDownloadOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyPauseDownloadOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyPauseDownloadOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyPauseDownloadOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_resume_download",
    description="Resume a paused download task in Synology Download Station",
    input_schema=SynologyResumeDownloadInput,
    output_schema=SynologyResumeDownloadOutput,
    tags=["synology", "downloadstation", "downloads"]
)
async def synology_resume_download(params: SynologyResumeDownloadInput) -> SynologyResumeDownloadOutput:
    """Resume a paused download task."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_resume_download", task_id=params.task_id)
    
    try:
        async with SynologyClient() as client:
            await client.resume_download(params.task_id)
            
            invocation_logger.success()
            
            return SynologyResumeDownloadOutput(success=True)
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyResumeDownloadOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyResumeDownloadOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyResumeDownloadOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyResumeDownloadOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_delete_download",
    description="Delete a download task from Synology Download Station",
    input_schema=SynologyDeleteDownloadInput,
    output_schema=SynologyDeleteDownloadOutput,
    tags=["synology", "downloadstation", "downloads"]
)
async def synology_delete_download(params: SynologyDeleteDownloadInput) -> SynologyDeleteDownloadOutput:
    """Delete a download task."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_delete_download", task_id=params.task_id)
    
    try:
        async with SynologyClient() as client:
            await client.delete_download(
                task_id=params.task_id,
                force_complete=params.force_complete,
            )
            
            invocation_logger.success()
            
            return SynologyDeleteDownloadOutput(success=True)
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyDeleteDownloadOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyDeleteDownloadOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyDeleteDownloadOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyDeleteDownloadOutput(success=False, error=f"Unexpected error: {e}")

