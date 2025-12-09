"""Synology Group management tools.

Provides MCP tools for managing user groups on Synology NAS.
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

class GroupOutput(BaseModel):
    """Group information."""
    name: str = Field(description="Group name")
    gid: int = Field(description="Group ID")
    description: str = Field(description="Description")


class GroupDetailOutput(BaseModel):
    """Detailed group information including members."""
    name: str = Field(description="Group name")
    gid: int = Field(description="Group ID")
    description: str = Field(description="Description")
    members: List[str] = Field(default_factory=list, description="Group members")


class SynologyListGroupsInput(BaseModel):
    """Input schema for synology_list_groups tool."""
    pass


class SynologyListGroupsOutput(BaseModel):
    """Output schema for synology_list_groups tool."""
    success: bool = Field(description="Whether the operation succeeded")
    groups: List[GroupOutput] = Field(
        default_factory=list,
        description="List of groups"
    )
    group_count: int = Field(default=0, description="Number of groups")
    error: str = Field(default="", description="Error message if failed")


class SynologyGetGroupInfoInput(BaseModel):
    """Input schema for synology_get_group_info tool."""
    name: str = Field(description="Group name")


class SynologyGetGroupInfoOutput(BaseModel):
    """Output schema for synology_get_group_info tool."""
    success: bool = Field(description="Whether the operation succeeded")
    group: Optional[GroupDetailOutput] = Field(
        default=None,
        description="Group information with members"
    )
    error: str = Field(default="", description="Error message if failed")


class SynologyCreateGroupInput(BaseModel):
    """Input schema for synology_create_group tool."""
    name: str = Field(description="Group name")
    description: str = Field(default="", description="Group description")


class SynologyCreateGroupOutput(BaseModel):
    """Output schema for synology_create_group tool."""
    success: bool = Field(description="Whether the operation succeeded")
    name: str = Field(default="", description="Created group name")
    error: str = Field(default="", description="Error message if failed")


class SynologyDeleteGroupInput(BaseModel):
    """Input schema for synology_delete_group tool."""
    name: str = Field(description="Group name to delete")


class SynologyDeleteGroupOutput(BaseModel):
    """Output schema for synology_delete_group tool."""
    success: bool = Field(description="Whether the operation succeeded")
    error: str = Field(default="", description="Error message if failed")


class SynologyAddGroupMemberInput(BaseModel):
    """Input schema for synology_add_group_member tool."""
    group_name: str = Field(description="Group name")
    username: str = Field(description="Username to add")


class SynologyAddGroupMemberOutput(BaseModel):
    """Output schema for synology_add_group_member tool."""
    success: bool = Field(description="Whether the operation succeeded")
    error: str = Field(default="", description="Error message if failed")


class SynologyRemoveGroupMemberInput(BaseModel):
    """Input schema for synology_remove_group_member tool."""
    group_name: str = Field(description="Group name")
    username: str = Field(description="Username to remove")


class SynologyRemoveGroupMemberOutput(BaseModel):
    """Output schema for synology_remove_group_member tool."""
    success: bool = Field(description="Whether the operation succeeded")
    error: str = Field(default="", description="Error message if failed")


# -----------------------------------------------------------------------------
# Tool Implementations
# -----------------------------------------------------------------------------

@tool(
    name="synology_list_groups",
    description="List all user groups on Synology NAS",
    input_schema=SynologyListGroupsInput,
    output_schema=SynologyListGroupsOutput,
    tags=["synology", "groups", "admin"]
)
async def synology_list_groups(params: SynologyListGroupsInput) -> SynologyListGroupsOutput:
    """List all user groups."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_list_groups")
    
    try:
        async with SynologyClient() as client:
            groups = await client.list_groups()
            
            group_list = [
                GroupOutput(
                    name=g.get("name", ""),
                    gid=g.get("gid", 0),
                    description=g.get("description", ""),
                )
                for g in groups
            ]
            
            invocation_logger.success(group_count=len(group_list))
            
            return SynologyListGroupsOutput(
                success=True,
                groups=group_list,
                group_count=len(group_list),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyListGroupsOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyListGroupsOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyListGroupsOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyListGroupsOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_get_group_info",
    description="Get information about a specific group including its members",
    input_schema=SynologyGetGroupInfoInput,
    output_schema=SynologyGetGroupInfoOutput,
    tags=["synology", "groups", "admin"]
)
async def synology_get_group_info(params: SynologyGetGroupInfoInput) -> SynologyGetGroupInfoOutput:
    """Get group information including members."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_get_group_info", name=params.name)
    
    try:
        async with SynologyClient() as client:
            group = await client.get_group_info(params.name)
            
            invocation_logger.success()
            
            return SynologyGetGroupInfoOutput(
                success=True,
                group=GroupDetailOutput(
                    name=group.get("name", ""),
                    gid=group.get("gid", 0),
                    description=group.get("description", ""),
                    members=group.get("members", []),
                ),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyGetGroupInfoOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyGetGroupInfoOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyGetGroupInfoOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyGetGroupInfoOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_create_group",
    description="Create a new user group on Synology NAS",
    input_schema=SynologyCreateGroupInput,
    output_schema=SynologyCreateGroupOutput,
    tags=["synology", "groups", "admin"]
)
async def synology_create_group(params: SynologyCreateGroupInput) -> SynologyCreateGroupOutput:
    """Create a new user group."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_create_group", name=params.name)
    
    try:
        async with SynologyClient() as client:
            await client.create_group(params.name, params.description)
            
            invocation_logger.success()
            
            return SynologyCreateGroupOutput(
                success=True,
                name=params.name,
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyCreateGroupOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyCreateGroupOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyCreateGroupOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyCreateGroupOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_delete_group",
    description="Delete a user group from Synology NAS",
    input_schema=SynologyDeleteGroupInput,
    output_schema=SynologyDeleteGroupOutput,
    tags=["synology", "groups", "admin"]
)
async def synology_delete_group(params: SynologyDeleteGroupInput) -> SynologyDeleteGroupOutput:
    """Delete a user group."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_delete_group", name=params.name)
    
    try:
        async with SynologyClient() as client:
            await client.delete_group(params.name)
            
            invocation_logger.success()
            
            return SynologyDeleteGroupOutput(success=True)
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyDeleteGroupOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyDeleteGroupOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyDeleteGroupOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyDeleteGroupOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_add_group_member",
    description="Add a user to a group on Synology NAS",
    input_schema=SynologyAddGroupMemberInput,
    output_schema=SynologyAddGroupMemberOutput,
    tags=["synology", "groups", "admin"]
)
async def synology_add_group_member(params: SynologyAddGroupMemberInput) -> SynologyAddGroupMemberOutput:
    """Add a user to a group."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_add_group_member", group=params.group_name, user=params.username)
    
    try:
        async with SynologyClient() as client:
            await client.add_group_member(params.group_name, params.username)
            
            invocation_logger.success()
            
            return SynologyAddGroupMemberOutput(success=True)
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyAddGroupMemberOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyAddGroupMemberOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyAddGroupMemberOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyAddGroupMemberOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_remove_group_member",
    description="Remove a user from a group on Synology NAS",
    input_schema=SynologyRemoveGroupMemberInput,
    output_schema=SynologyRemoveGroupMemberOutput,
    tags=["synology", "groups", "admin"]
)
async def synology_remove_group_member(params: SynologyRemoveGroupMemberInput) -> SynologyRemoveGroupMemberOutput:
    """Remove a user from a group."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_remove_group_member", group=params.group_name, user=params.username)
    
    try:
        async with SynologyClient() as client:
            await client.remove_group_member(params.group_name, params.username)
            
            invocation_logger.success()
            
            return SynologyRemoveGroupMemberOutput(success=True)
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyRemoveGroupMemberOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyRemoveGroupMemberOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyRemoveGroupMemberOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyRemoveGroupMemberOutput(success=False, error=f"Unexpected error: {e}")

