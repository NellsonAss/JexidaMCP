"""Discord REST API tools for MCP.

Provides MCP tools for:
- Sending messages to Discord channels
- Creating text channels and categories
- Managing roles
- Getting guild information
"""

import logging
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field

from .client import DiscordClient
from .config import DiscordConfigError

logger = logging.getLogger(__name__)


# =============================================================================
# Get Guild Info Tool
# =============================================================================

class DiscordGetGuildInfoInput(BaseModel):
    """Input schema for discord_get_guild_info."""
    
    guild_id: Optional[str] = Field(
        default=None,
        description="Guild ID. If not provided, uses configured DISCORD_GUILD_ID"
    )


class DiscordGetGuildInfoOutput(BaseModel):
    """Output schema for discord_get_guild_info."""
    
    ok: bool = Field(description="Whether the request succeeded")
    guild_id: str = Field(default="", description="Guild ID")
    name: str = Field(default="", description="Guild name")
    member_count: int = Field(default=0, description="Approximate member count")
    raw: Dict[str, Any] = Field(default_factory=dict, description="Raw API response")
    error: str = Field(default="", description="Error message if failed")


async def discord_get_guild_info(params: DiscordGetGuildInfoInput) -> DiscordGetGuildInfoOutput:
    """Get Discord guild (server) information.
    
    Retrieves basic information about a Discord server.
    Useful for testing connectivity and configuration.
    
    Returns:
        Guild information
    """
    logger.info(f"Getting Discord guild info: {params.guild_id or 'default'}")
    
    try:
        with DiscordClient() as client:
            result = client.get_guild_info(params.guild_id)
            
            if not result.ok:
                return DiscordGetGuildInfoOutput(
                    ok=False,
                    error=result.error or "Unknown error",
                )
            
            data = result.data or {}
            return DiscordGetGuildInfoOutput(
                ok=True,
                guild_id=str(data.get("id", "")),
                name=data.get("name", ""),
                member_count=data.get("approximate_member_count", 0),
                raw=data,
            )
    except DiscordConfigError as e:
        logger.error(f"Discord configuration error: {e}")
        return DiscordGetGuildInfoOutput(
            ok=False,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to get guild info: {e}")
        return DiscordGetGuildInfoOutput(
            ok=False,
            error=str(e),
        )


# =============================================================================
# Send Message Tool
# =============================================================================

class EmbedField(BaseModel):
    """Discord embed field."""
    
    name: str = Field(description="Field name")
    value: str = Field(description="Field value")
    inline: bool = Field(default=False, description="Whether to display inline")


class Embed(BaseModel):
    """Discord embed object."""
    
    title: Optional[str] = Field(default=None, description="Embed title")
    description: Optional[str] = Field(default=None, description="Embed description")
    color: Optional[int] = Field(default=None, description="Embed color as integer")
    fields: List[EmbedField] = Field(default_factory=list, description="Embed fields")


class DiscordSendMessageInput(BaseModel):
    """Input schema for discord_send_message."""
    
    channel_id: str = Field(description="Target channel ID")
    content: str = Field(description="Message content")
    embeds: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Optional list of embed objects"
    )


class DiscordSendMessageOutput(BaseModel):
    """Output schema for discord_send_message."""
    
    ok: bool = Field(description="Whether the message was sent")
    status_code: int = Field(default=0, description="HTTP status code")
    message_id: str = Field(default="", description="Created message ID")
    raw: Dict[str, Any] = Field(default_factory=dict, description="Raw API response")
    error: str = Field(default="", description="Error message if failed")


async def discord_send_message(params: DiscordSendMessageInput) -> DiscordSendMessageOutput:
    """Send a message to a Discord channel.
    
    Sends a text message with optional embeds to the specified channel.
    
    Args:
        params: Channel ID, content, and optional embeds
        
    Returns:
        Message creation result
    """
    logger.info(f"Sending Discord message to channel: {params.channel_id}")
    
    try:
        with DiscordClient() as client:
            result = client.send_message(
                params.channel_id,
                params.content,
                embeds=params.embeds,
            )
            
            if not result.ok:
                return DiscordSendMessageOutput(
                    ok=False,
                    status_code=result.status_code,
                    error=result.error or "Unknown error",
                )
            
            data = result.data or {}
            return DiscordSendMessageOutput(
                ok=True,
                status_code=result.status_code,
                message_id=str(data.get("id", "")),
                raw=data,
            )
    except DiscordConfigError as e:
        logger.error(f"Discord configuration error: {e}")
        return DiscordSendMessageOutput(
            ok=False,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        return DiscordSendMessageOutput(
            ok=False,
            error=str(e),
        )


# =============================================================================
# Create Text Channel Tool
# =============================================================================

class DiscordCreateTextChannelInput(BaseModel):
    """Input schema for discord_create_text_channel."""
    
    name: str = Field(description="Channel name (lowercase, no spaces)")
    guild_id: Optional[str] = Field(
        default=None,
        description="Guild ID. If not provided, uses configured DISCORD_GUILD_ID"
    )
    parent_id: Optional[str] = Field(
        default=None,
        description="Parent category ID (optional)"
    )
    topic: Optional[str] = Field(
        default=None,
        description="Channel topic (optional)"
    )


class DiscordCreateTextChannelOutput(BaseModel):
    """Output schema for discord_create_text_channel."""
    
    ok: bool = Field(description="Whether the channel was created")
    status_code: int = Field(default=0, description="HTTP status code")
    channel_id: str = Field(default="", description="Created channel ID")
    raw: Dict[str, Any] = Field(default_factory=dict, description="Raw API response")
    error: str = Field(default="", description="Error message if failed")


async def discord_create_text_channel(params: DiscordCreateTextChannelInput) -> DiscordCreateTextChannelOutput:
    """Create a text channel in a Discord guild.
    
    Creates a new text channel, optionally under a category.
    
    Args:
        params: Channel configuration
        
    Returns:
        Channel creation result
    """
    logger.info(f"Creating Discord text channel: {params.name}")
    
    try:
        with DiscordClient() as client:
            result = client.create_text_channel(
                params.guild_id,
                params.name,
                parent_id=params.parent_id,
                topic=params.topic,
                reason="Created by JexidaMCP",
            )
            
            if not result.ok:
                return DiscordCreateTextChannelOutput(
                    ok=False,
                    status_code=result.status_code,
                    error=result.error or "Unknown error",
                )
            
            data = result.data or {}
            return DiscordCreateTextChannelOutput(
                ok=True,
                status_code=result.status_code,
                channel_id=str(data.get("id", "")),
                raw=data,
            )
    except DiscordConfigError as e:
        logger.error(f"Discord configuration error: {e}")
        return DiscordCreateTextChannelOutput(
            ok=False,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create text channel: {e}")
        return DiscordCreateTextChannelOutput(
            ok=False,
            error=str(e),
        )


# =============================================================================
# Create Category Channel Tool
# =============================================================================

class DiscordCreateCategoryChannelInput(BaseModel):
    """Input schema for discord_create_category_channel."""
    
    name: str = Field(description="Category name")
    guild_id: Optional[str] = Field(
        default=None,
        description="Guild ID. If not provided, uses configured DISCORD_GUILD_ID"
    )


class DiscordCreateCategoryChannelOutput(BaseModel):
    """Output schema for discord_create_category_channel."""
    
    ok: bool = Field(description="Whether the category was created")
    status_code: int = Field(default=0, description="HTTP status code")
    channel_id: str = Field(default="", description="Created category ID")
    raw: Dict[str, Any] = Field(default_factory=dict, description="Raw API response")
    error: str = Field(default="", description="Error message if failed")


async def discord_create_category_channel(params: DiscordCreateCategoryChannelInput) -> DiscordCreateCategoryChannelOutput:
    """Create a category channel in a Discord guild.
    
    Creates a new category that can contain text channels.
    
    Args:
        params: Category configuration
        
    Returns:
        Category creation result
    """
    logger.info(f"Creating Discord category channel: {params.name}")
    
    try:
        with DiscordClient() as client:
            result = client.create_category_channel(
                params.guild_id,
                params.name,
                reason="Created by JexidaMCP",
            )
            
            if not result.ok:
                return DiscordCreateCategoryChannelOutput(
                    ok=False,
                    status_code=result.status_code,
                    error=result.error or "Unknown error",
                )
            
            data = result.data or {}
            return DiscordCreateCategoryChannelOutput(
                ok=True,
                status_code=result.status_code,
                channel_id=str(data.get("id", "")),
                raw=data,
            )
    except DiscordConfigError as e:
        logger.error(f"Discord configuration error: {e}")
        return DiscordCreateCategoryChannelOutput(
            ok=False,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create category channel: {e}")
        return DiscordCreateCategoryChannelOutput(
            ok=False,
            error=str(e),
        )


# =============================================================================
# Ensure Role Tool
# =============================================================================

class DiscordEnsureRoleInput(BaseModel):
    """Input schema for discord_ensure_role."""
    
    name: str = Field(description="Role name")
    guild_id: Optional[str] = Field(
        default=None,
        description="Guild ID. If not provided, uses configured DISCORD_GUILD_ID"
    )
    permissions: Optional[int] = Field(
        default=None,
        description="Permission bit set (optional)"
    )
    color: Optional[int] = Field(
        default=None,
        description="Role color as integer (optional)"
    )
    hoist: bool = Field(
        default=False,
        description="Whether to display role separately in member list"
    )


class DiscordEnsureRoleOutput(BaseModel):
    """Output schema for discord_ensure_role."""
    
    ok: bool = Field(description="Whether the operation succeeded")
    status_code: int = Field(default=0, description="HTTP status code")
    role_id: str = Field(default="", description="Role ID (existing or newly created)")
    existed: bool = Field(default=False, description="Whether the role already existed")
    raw: Dict[str, Any] = Field(default_factory=dict, description="Raw API response")
    error: str = Field(default="", description="Error message if failed")


async def discord_ensure_role(params: DiscordEnsureRoleInput) -> DiscordEnsureRoleOutput:
    """Ensure a role exists in a Discord guild.
    
    If the role already exists, returns it. Otherwise, creates it.
    This operation is idempotent.
    
    Args:
        params: Role configuration
        
    Returns:
        Role data (existing or newly created)
    """
    logger.info(f"Ensuring Discord role exists: {params.name}")
    
    try:
        with DiscordClient() as client:
            result = client.ensure_role(
                params.guild_id,
                params.name,
                permissions=params.permissions,
                color=params.color,
                hoist=params.hoist,
            )
            
            if not result.ok:
                return DiscordEnsureRoleOutput(
                    ok=False,
                    status_code=result.status_code,
                    error=result.error or "Unknown error",
                )
            
            data = result.data or {}
            return DiscordEnsureRoleOutput(
                ok=True,
                status_code=result.status_code,
                role_id=str(data.get("id", "")),
                existed=data.get("_existed", False),
                raw={k: v for k, v in data.items() if not k.startswith("_")},
            )
    except DiscordConfigError as e:
        logger.error(f"Discord configuration error: {e}")
        return DiscordEnsureRoleOutput(
            ok=False,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to ensure role: {e}")
        return DiscordEnsureRoleOutput(
            ok=False,
            error=str(e),
        )

