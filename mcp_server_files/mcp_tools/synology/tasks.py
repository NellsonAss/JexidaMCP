"""Synology Task Scheduler tools.

Provides MCP tools for managing scheduled tasks on Synology NAS.
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

class ScheduledTaskOutput(BaseModel):
    """Scheduled task information."""
    id: int = Field(description="Task ID")
    name: str = Field(description="Task name")
    type: str = Field(description="Task type")
    enable: bool = Field(description="Whether task is enabled")
    next_trigger_time: int = Field(description="Next run timestamp")
    last_work_time: int = Field(description="Last run timestamp")
    status: str = Field(description="Task status")


class SynologyListScheduledTasksInput(BaseModel):
    """Input schema for synology_list_scheduled_tasks tool."""
    pass


class SynologyListScheduledTasksOutput(BaseModel):
    """Output schema for synology_list_scheduled_tasks tool."""
    success: bool = Field(description="Whether the operation succeeded")
    tasks: List[ScheduledTaskOutput] = Field(
        default_factory=list,
        description="List of scheduled tasks"
    )
    task_count: int = Field(default=0, description="Number of tasks")
    error: str = Field(default="", description="Error message if failed")


class SynologyRunScheduledTaskInput(BaseModel):
    """Input schema for synology_run_scheduled_task tool."""
    task_id: int = Field(description="Task ID to run")


class SynologyRunScheduledTaskOutput(BaseModel):
    """Output schema for synology_run_scheduled_task tool."""
    success: bool = Field(description="Whether the operation succeeded")
    task_id: int = Field(default=0, description="Task ID that was run")
    error: str = Field(default="", description="Error message if failed")


class SynologyEnableScheduledTaskInput(BaseModel):
    """Input schema for synology_enable_scheduled_task tool."""
    task_id: int = Field(description="Task ID")
    enabled: bool = Field(default=True, description="Enable or disable the task")


class SynologyEnableScheduledTaskOutput(BaseModel):
    """Output schema for synology_enable_scheduled_task tool."""
    success: bool = Field(description="Whether the operation succeeded")
    error: str = Field(default="", description="Error message if failed")


# -----------------------------------------------------------------------------
# Tool Implementations
# -----------------------------------------------------------------------------

@tool(
    name="synology_list_scheduled_tasks",
    description="List scheduled tasks on Synology NAS",
    input_schema=SynologyListScheduledTasksInput,
    output_schema=SynologyListScheduledTasksOutput,
    tags=["synology", "tasks", "scheduler"]
)
async def synology_list_scheduled_tasks(params: SynologyListScheduledTasksInput) -> SynologyListScheduledTasksOutput:
    """List scheduled tasks."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_list_scheduled_tasks")
    
    try:
        async with SynologyClient() as client:
            tasks = await client.list_scheduled_tasks()
            
            task_list = [
                ScheduledTaskOutput(
                    id=t.get("id", 0),
                    name=t.get("name", ""),
                    type=t.get("type", ""),
                    enable=t.get("enable", False),
                    next_trigger_time=t.get("next_trigger_time", 0),
                    last_work_time=t.get("last_work_time", 0),
                    status=t.get("status", ""),
                )
                for t in tasks
            ]
            
            invocation_logger.success(task_count=len(task_list))
            
            return SynologyListScheduledTasksOutput(
                success=True,
                tasks=task_list,
                task_count=len(task_list),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyListScheduledTasksOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyListScheduledTasksOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyListScheduledTasksOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyListScheduledTasksOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_run_scheduled_task",
    description="Run a scheduled task immediately on Synology NAS",
    input_schema=SynologyRunScheduledTaskInput,
    output_schema=SynologyRunScheduledTaskOutput,
    tags=["synology", "tasks", "scheduler"]
)
async def synology_run_scheduled_task(params: SynologyRunScheduledTaskInput) -> SynologyRunScheduledTaskOutput:
    """Run a scheduled task immediately."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_run_scheduled_task", task_id=params.task_id)
    
    try:
        async with SynologyClient() as client:
            await client.run_scheduled_task(params.task_id)
            
            invocation_logger.success()
            
            return SynologyRunScheduledTaskOutput(
                success=True,
                task_id=params.task_id,
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyRunScheduledTaskOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyRunScheduledTaskOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyRunScheduledTaskOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyRunScheduledTaskOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_enable_scheduled_task",
    description="Enable or disable a scheduled task on Synology NAS",
    input_schema=SynologyEnableScheduledTaskInput,
    output_schema=SynologyEnableScheduledTaskOutput,
    tags=["synology", "tasks", "scheduler"]
)
async def synology_enable_scheduled_task(params: SynologyEnableScheduledTaskInput) -> SynologyEnableScheduledTaskOutput:
    """Enable or disable a scheduled task."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_enable_scheduled_task", task_id=params.task_id, enabled=params.enabled)
    
    try:
        async with SynologyClient() as client:
            await client.enable_scheduled_task(params.task_id, params.enabled)
            
            invocation_logger.success()
            
            return SynologyEnableScheduledTaskOutput(success=True)
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyEnableScheduledTaskOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyEnableScheduledTaskOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyEnableScheduledTaskOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyEnableScheduledTaskOutput(success=False, error=f"Unexpected error: {e}")

