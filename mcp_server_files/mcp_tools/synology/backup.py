"""Synology Hyper Backup tools.

Provides MCP tools for managing backup tasks on Synology NAS.
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
    SynologyBackupTask,
)

logger = get_logger(__name__)


# -----------------------------------------------------------------------------
# Input/Output Schemas
# -----------------------------------------------------------------------------

class BackupTaskInfoOutput(BaseModel):
    """Backup task information."""
    task_id: int = Field(description="Task ID")
    name: str = Field(description="Task name")
    status: str = Field(description="Task status")
    last_run_time: int = Field(description="Last run timestamp")
    next_run_time: int = Field(description="Next scheduled run timestamp")
    target_type: str = Field(description="Backup target type")


class SynologyListBackupTasksInput(BaseModel):
    """Input schema for synology_list_backup_tasks tool."""
    pass  # No parameters needed


class SynologyListBackupTasksOutput(BaseModel):
    """Output schema for synology_list_backup_tasks tool."""
    success: bool = Field(description="Whether the operation succeeded")
    tasks: List[BackupTaskInfoOutput] = Field(
        default_factory=list,
        description="List of backup tasks"
    )
    task_count: int = Field(default=0, description="Number of tasks")
    error: str = Field(default="", description="Error message if failed")


class SynologyRunBackupTaskInput(BaseModel):
    """Input schema for synology_run_backup_task tool."""
    task_id: int = Field(description="Backup task ID to run")


class SynologyRunBackupTaskOutput(BaseModel):
    """Output schema for synology_run_backup_task tool."""
    success: bool = Field(description="Whether the operation succeeded")
    task_id: int = Field(default=0, description="Task ID that was triggered")
    error: str = Field(default="", description="Error message if failed")


class SynologyGetBackupStatusInput(BaseModel):
    """Input schema for synology_get_backup_status tool."""
    task_id: int = Field(description="Backup task ID")


class BackupStatusOutput(BaseModel):
    """Backup task status information."""
    task_id: int = Field(description="Task ID")
    state: str = Field(description="Current state")
    progress: float = Field(description="Progress percentage")
    transferred_bytes: int = Field(description="Bytes transferred")
    error: Optional[str] = Field(default=None, description="Error message if any")


class SynologyGetBackupStatusOutput(BaseModel):
    """Output schema for synology_get_backup_status tool."""
    success: bool = Field(description="Whether the operation succeeded")
    status: Optional[BackupStatusOutput] = Field(
        default=None,
        description="Backup status information"
    )
    error: str = Field(default="", description="Error message if failed")


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def _task_to_output(task: SynologyBackupTask) -> BackupTaskInfoOutput:
    """Convert SynologyBackupTask to BackupTaskInfoOutput."""
    return BackupTaskInfoOutput(
        task_id=task.task_id,
        name=task.name,
        status=task.status,
        last_run_time=task.last_run_time,
        next_run_time=task.next_run_time,
        target_type=task.target_type,
    )


# -----------------------------------------------------------------------------
# Tool Implementations
# -----------------------------------------------------------------------------

@tool(
    name="synology_list_backup_tasks",
    description="List Hyper Backup tasks on Synology NAS",
    input_schema=SynologyListBackupTasksInput,
    output_schema=SynologyListBackupTasksOutput,
    tags=["synology", "backup", "hyperbackup"]
)
async def synology_list_backup_tasks(params: SynologyListBackupTasksInput) -> SynologyListBackupTasksOutput:
    """List all Hyper Backup tasks."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_list_backup_tasks")
    
    try:
        async with SynologyClient() as client:
            tasks = await client.list_backup_tasks()
            
            task_list = [_task_to_output(t) for t in tasks]
            
            invocation_logger.success(task_count=len(task_list))
            
            return SynologyListBackupTasksOutput(
                success=True,
                tasks=task_list,
                task_count=len(task_list),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyListBackupTasksOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyListBackupTasksOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyListBackupTasksOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyListBackupTasksOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_run_backup_task",
    description="Trigger a Hyper Backup task to run on Synology NAS",
    input_schema=SynologyRunBackupTaskInput,
    output_schema=SynologyRunBackupTaskOutput,
    tags=["synology", "backup", "hyperbackup"]
)
async def synology_run_backup_task(params: SynologyRunBackupTaskInput) -> SynologyRunBackupTaskOutput:
    """Trigger a backup task to run."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_run_backup_task", task_id=params.task_id)
    
    try:
        async with SynologyClient() as client:
            await client.run_backup_task(params.task_id)
            
            invocation_logger.success()
            
            return SynologyRunBackupTaskOutput(
                success=True,
                task_id=params.task_id,
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyRunBackupTaskOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyRunBackupTaskOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyRunBackupTaskOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyRunBackupTaskOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_get_backup_status",
    description="Get the current status of a Hyper Backup task on Synology NAS",
    input_schema=SynologyGetBackupStatusInput,
    output_schema=SynologyGetBackupStatusOutput,
    tags=["synology", "backup", "hyperbackup"]
)
async def synology_get_backup_status(params: SynologyGetBackupStatusInput) -> SynologyGetBackupStatusOutput:
    """Get the current status of a backup task."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_get_backup_status", task_id=params.task_id)
    
    try:
        async with SynologyClient() as client:
            status_data = await client.get_backup_status(params.task_id)
            
            status = BackupStatusOutput(
                task_id=status_data.get("task_id", params.task_id),
                state=status_data.get("state", "unknown"),
                progress=status_data.get("progress", 0),
                transferred_bytes=status_data.get("transferred_bytes", 0),
                error=status_data.get("error"),
            )
            
            invocation_logger.success(state=status.state)
            
            return SynologyGetBackupStatusOutput(
                success=True,
                status=status,
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyGetBackupStatusOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyGetBackupStatusOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyGetBackupStatusOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyGetBackupStatusOutput(success=False, error=f"Unexpected error: {e}")

