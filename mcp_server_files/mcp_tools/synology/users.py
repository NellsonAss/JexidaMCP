"""Synology user management tools.

Provides MCP tools for managing user accounts on Synology NAS.
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
    SynologyUser,
)

logger = get_logger(__name__)


# -----------------------------------------------------------------------------
# Input/Output Schemas
# -----------------------------------------------------------------------------

class UserInfoOutput(BaseModel):
    """User account information."""
    name: str = Field(description="Username")
    uid: int = Field(description="User ID")
    description: str = Field(description="User description")
    email: str = Field(description="Email address")
    expired: bool = Field(description="Whether account is expired")


class SynologyListUsersInput(BaseModel):
    """Input schema for synology_list_users tool."""
    pass  # No parameters needed


class SynologyListUsersOutput(BaseModel):
    """Output schema for synology_list_users tool."""
    success: bool = Field(description="Whether the operation succeeded")
    users: List[UserInfoOutput] = Field(
        default_factory=list,
        description="List of user accounts"
    )
    user_count: int = Field(default=0, description="Number of users")
    error: str = Field(default="", description="Error message if failed")


class SynologyGetUserInfoInput(BaseModel):
    """Input schema for synology_get_user_info tool."""
    username: str = Field(description="Username to get info for")


class SynologyGetUserInfoOutput(BaseModel):
    """Output schema for synology_get_user_info tool."""
    success: bool = Field(description="Whether the operation succeeded")
    user: Optional[UserInfoOutput] = Field(
        default=None,
        description="User information"
    )
    error: str = Field(default="", description="Error message if failed")


class SynologyCreateUserInput(BaseModel):
    """Input schema for synology_create_user tool."""
    username: str = Field(description="Username for new account")
    password: str = Field(description="Password for new account")
    description: str = Field(default="", description="User description")
    email: str = Field(default="", description="Email address")


class SynologyCreateUserOutput(BaseModel):
    """Output schema for synology_create_user tool."""
    success: bool = Field(description="Whether the operation succeeded")
    username: str = Field(default="", description="Created username")
    error: str = Field(default="", description="Error message if failed")


class SynologyDeleteUserInput(BaseModel):
    """Input schema for synology_delete_user tool."""
    username: str = Field(description="Username to delete")


class SynologyDeleteUserOutput(BaseModel):
    """Output schema for synology_delete_user tool."""
    success: bool = Field(description="Whether the operation succeeded")
    error: str = Field(default="", description="Error message if failed")


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def _user_to_output(user: SynologyUser) -> UserInfoOutput:
    """Convert SynologyUser to UserInfoOutput."""
    return UserInfoOutput(
        name=user.name,
        uid=user.uid,
        description=user.description,
        email=user.email,
        expired=user.expired,
    )


# -----------------------------------------------------------------------------
# Tool Implementations
# -----------------------------------------------------------------------------

@tool(
    name="synology_list_users",
    description="List all user accounts on Synology NAS",
    input_schema=SynologyListUsersInput,
    output_schema=SynologyListUsersOutput,
    tags=["synology", "users", "admin"]
)
async def synology_list_users(params: SynologyListUsersInput) -> SynologyListUsersOutput:
    """List all user accounts."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_list_users")
    
    try:
        async with SynologyClient() as client:
            users = await client.list_users()
            
            user_list = [_user_to_output(u) for u in users]
            
            invocation_logger.success(user_count=len(user_list))
            
            return SynologyListUsersOutput(
                success=True,
                users=user_list,
                user_count=len(user_list),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyListUsersOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyListUsersOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyListUsersOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyListUsersOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_get_user_info",
    description="Get information about a specific user on Synology NAS",
    input_schema=SynologyGetUserInfoInput,
    output_schema=SynologyGetUserInfoOutput,
    tags=["synology", "users", "admin"]
)
async def synology_get_user_info(params: SynologyGetUserInfoInput) -> SynologyGetUserInfoOutput:
    """Get information about a specific user."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_get_user_info", username=params.username)
    
    try:
        async with SynologyClient() as client:
            user = await client.get_user_info(params.username)
            
            invocation_logger.success()
            
            return SynologyGetUserInfoOutput(
                success=True,
                user=_user_to_output(user),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyGetUserInfoOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyGetUserInfoOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyGetUserInfoOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyGetUserInfoOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_create_user",
    description="Create a new user account on Synology NAS",
    input_schema=SynologyCreateUserInput,
    output_schema=SynologyCreateUserOutput,
    tags=["synology", "users", "admin"]
)
async def synology_create_user(params: SynologyCreateUserInput) -> SynologyCreateUserOutput:
    """Create a new user account."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_create_user", username=params.username)
    
    try:
        async with SynologyClient() as client:
            await client.create_user(
                username=params.username,
                password=params.password,
                description=params.description,
                email=params.email,
            )
            
            invocation_logger.success()
            
            return SynologyCreateUserOutput(
                success=True,
                username=params.username,
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyCreateUserOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyCreateUserOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyCreateUserOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyCreateUserOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_delete_user",
    description="Delete a user account from Synology NAS",
    input_schema=SynologyDeleteUserInput,
    output_schema=SynologyDeleteUserOutput,
    tags=["synology", "users", "admin"]
)
async def synology_delete_user(params: SynologyDeleteUserInput) -> SynologyDeleteUserOutput:
    """Delete a user account."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_delete_user", username=params.username)
    
    try:
        async with SynologyClient() as client:
            await client.delete_user(params.username)
            
            invocation_logger.success()
            
            return SynologyDeleteUserOutput(success=True)
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyDeleteUserOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyDeleteUserOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyDeleteUserOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyDeleteUserOutput(success=False, error=f"Unexpected error: {e}")

