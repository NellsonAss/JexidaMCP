"""HTTP client for Discord REST API.

Provides a thin wrapper around the Discord API v10 with:
- Bot token authentication
- Error handling for non-2xx responses
- Context manager support
"""

import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

import httpx

from .config import DiscordConfig

logger = logging.getLogger(__name__)

# Discord API base URL
DISCORD_API_BASE = "https://discord.com/api/v10"

# Discord channel types
CHANNEL_TYPE_TEXT = 0
CHANNEL_TYPE_CATEGORY = 4


class DiscordAPIError(Exception):
    """Raised when Discord API returns an error."""
    
    def __init__(self, message: str, status_code: int = 0, response_data: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


@dataclass
class DiscordAPIResult:
    """Result of a Discord API call."""
    
    ok: bool
    status_code: int
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class DiscordClient:
    """HTTP client for Discord REST API with Bot token authentication."""
    
    def __init__(self, config: Optional[DiscordConfig] = None):
        """Initialize the client.
        
        Args:
            config: Optional configuration. If not provided, loads from settings/env.
        """
        self.config = config or DiscordConfig.from_settings()
        self._client: Optional[httpx.Client] = None
    
    @property
    def client(self) -> httpx.Client:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=DISCORD_API_BASE,
                timeout=self.config.timeout,
                headers={
                    "Authorization": f"Bot {self.config.bot_token}",
                    "Content-Type": "application/json",
                    "User-Agent": "JexidaMCP Discord Bot (https://github.com/jexida, 1.0)",
                },
            )
        return self._client
    
    def close(self):
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def _handle_response(self, response: httpx.Response) -> DiscordAPIResult:
        """Handle Discord API response.
        
        Args:
            response: HTTP response
            
        Returns:
            DiscordAPIResult with parsed data or error
        """
        try:
            data = response.json() if response.content else None
        except Exception:
            data = None
        
        if response.is_success:
            return DiscordAPIResult(
                ok=True,
                status_code=response.status_code,
                data=data,
            )
        else:
            # Extract error message from Discord response
            error_msg = "Unknown error"
            if data:
                error_msg = data.get("message", str(data))
            return DiscordAPIResult(
                ok=False,
                status_code=response.status_code,
                data=data,
                error=f"HTTP {response.status_code}: {error_msg}",
            )
    
    def get_guild_info(self, guild_id: Optional[str] = None) -> DiscordAPIResult:
        """Get guild (server) information.
        
        Args:
            guild_id: Guild ID. Defaults to configured guild.
            
        Returns:
            Guild information
        """
        gid = guild_id or self.config.guild_id
        try:
            response = self.client.get(f"/guilds/{gid}")
            return self._handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"Failed to get guild info: {e}")
            return DiscordAPIResult(
                ok=False,
                status_code=0,
                error=str(e),
            )
    
    def get_guild_channels(self, guild_id: Optional[str] = None) -> DiscordAPIResult:
        """Get all channels in a guild.
        
        Args:
            guild_id: Guild ID. Defaults to configured guild.
            
        Returns:
            List of channels
        """
        gid = guild_id or self.config.guild_id
        try:
            response = self.client.get(f"/guilds/{gid}/channels")
            return self._handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"Failed to get guild channels: {e}")
            return DiscordAPIResult(
                ok=False,
                status_code=0,
                error=str(e),
            )
    
    def get_guild_roles(self, guild_id: Optional[str] = None) -> DiscordAPIResult:
        """Get all roles in a guild.
        
        Args:
            guild_id: Guild ID. Defaults to configured guild.
            
        Returns:
            List of roles
        """
        gid = guild_id or self.config.guild_id
        try:
            response = self.client.get(f"/guilds/{gid}/roles")
            return self._handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"Failed to get guild roles: {e}")
            return DiscordAPIResult(
                ok=False,
                status_code=0,
                error=str(e),
            )
    
    def send_message(
        self,
        channel_id: str,
        content: str,
        embeds: Optional[List[Dict[str, Any]]] = None,
    ) -> DiscordAPIResult:
        """Send a message to a channel.
        
        Args:
            channel_id: Target channel ID
            content: Message content
            embeds: Optional list of embed objects
            
        Returns:
            Created message data
        """
        payload: Dict[str, Any] = {"content": content}
        if embeds:
            payload["embeds"] = embeds
        
        try:
            response = self.client.post(
                f"/channels/{channel_id}/messages",
                json=payload,
            )
            return self._handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"Failed to send message: {e}")
            return DiscordAPIResult(
                ok=False,
                status_code=0,
                error=str(e),
            )
    
    def create_text_channel(
        self,
        guild_id: Optional[str],
        name: str,
        *,
        parent_id: Optional[str] = None,
        topic: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> DiscordAPIResult:
        """Create a text channel in a guild.
        
        Args:
            guild_id: Guild ID. Defaults to configured guild.
            name: Channel name
            parent_id: Parent category ID (optional)
            topic: Channel topic (optional)
            reason: Audit log reason (optional)
            
        Returns:
            Created channel data
        """
        gid = guild_id or self.config.guild_id
        payload: Dict[str, Any] = {
            "name": name,
            "type": CHANNEL_TYPE_TEXT,
        }
        if parent_id:
            payload["parent_id"] = parent_id
        if topic:
            payload["topic"] = topic
        
        headers = {}
        if reason:
            headers["X-Audit-Log-Reason"] = reason
        
        try:
            response = self.client.post(
                f"/guilds/{gid}/channels",
                json=payload,
                headers=headers,
            )
            return self._handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"Failed to create text channel: {e}")
            return DiscordAPIResult(
                ok=False,
                status_code=0,
                error=str(e),
            )
    
    def create_category_channel(
        self,
        guild_id: Optional[str],
        name: str,
        *,
        reason: Optional[str] = None,
    ) -> DiscordAPIResult:
        """Create a category channel in a guild.
        
        Args:
            guild_id: Guild ID. Defaults to configured guild.
            name: Category name
            reason: Audit log reason (optional)
            
        Returns:
            Created category data
        """
        gid = guild_id or self.config.guild_id
        payload: Dict[str, Any] = {
            "name": name,
            "type": CHANNEL_TYPE_CATEGORY,
        }
        
        headers = {}
        if reason:
            headers["X-Audit-Log-Reason"] = reason
        
        try:
            response = self.client.post(
                f"/guilds/{gid}/channels",
                json=payload,
                headers=headers,
            )
            return self._handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"Failed to create category channel: {e}")
            return DiscordAPIResult(
                ok=False,
                status_code=0,
                error=str(e),
            )
    
    def create_role(
        self,
        guild_id: Optional[str],
        name: str,
        *,
        permissions: Optional[int] = None,
        color: Optional[int] = None,
        hoist: bool = False,
        reason: Optional[str] = None,
    ) -> DiscordAPIResult:
        """Create a role in a guild.
        
        Args:
            guild_id: Guild ID. Defaults to configured guild.
            name: Role name
            permissions: Permission bit set (optional)
            color: Role color as integer (optional)
            hoist: Whether to display role separately in member list
            reason: Audit log reason (optional)
            
        Returns:
            Created role data
        """
        gid = guild_id or self.config.guild_id
        payload: Dict[str, Any] = {
            "name": name,
            "hoist": hoist,
        }
        if permissions is not None:
            payload["permissions"] = str(permissions)
        if color is not None:
            payload["color"] = color
        
        headers = {}
        if reason:
            headers["X-Audit-Log-Reason"] = reason
        
        try:
            response = self.client.post(
                f"/guilds/{gid}/roles",
                json=payload,
                headers=headers,
            )
            return self._handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"Failed to create role: {e}")
            return DiscordAPIResult(
                ok=False,
                status_code=0,
                error=str(e),
            )
    
    def ensure_role(
        self,
        guild_id: Optional[str],
        name: str,
        *,
        permissions: Optional[int] = None,
        color: Optional[int] = None,
        hoist: bool = False,
    ) -> DiscordAPIResult:
        """Ensure a role exists in a guild.
        
        If the role exists, returns it. Otherwise, creates it.
        
        Args:
            guild_id: Guild ID. Defaults to configured guild.
            name: Role name
            permissions: Permission bit set (optional)
            color: Role color as integer (optional)
            hoist: Whether to display role separately in member list
            
        Returns:
            Role data (existing or newly created)
        """
        gid = guild_id or self.config.guild_id
        
        # First, get existing roles
        roles_result = self.get_guild_roles(gid)
        if not roles_result.ok:
            return roles_result
        
        # Check if role already exists
        existing_roles = roles_result.data or []
        for role in existing_roles:
            if role.get("name", "").lower() == name.lower():
                logger.info(f"Role '{name}' already exists with ID {role.get('id')}")
                return DiscordAPIResult(
                    ok=True,
                    status_code=200,
                    data={**role, "_existed": True},
                )
        
        # Role doesn't exist, create it
        logger.info(f"Creating role '{name}'")
        result = self.create_role(
            gid,
            name,
            permissions=permissions,
            color=color,
            hoist=hoist,
            reason="Created by JexidaMCP Discord bootstrap",
        )
        if result.ok and result.data:
            result.data["_existed"] = False
        return result
    
    def add_role_to_user(
        self,
        guild_id: Optional[str],
        user_id: str,
        role_id: str,
        *,
        reason: Optional[str] = None,
    ) -> DiscordAPIResult:
        """Add a role to a guild member.
        
        Args:
            guild_id: Guild ID. Defaults to configured guild.
            user_id: User ID
            role_id: Role ID to add
            reason: Audit log reason (optional)
            
        Returns:
            Success status
        """
        gid = guild_id or self.config.guild_id
        
        headers = {}
        if reason:
            headers["X-Audit-Log-Reason"] = reason
        
        try:
            response = self.client.put(
                f"/guilds/{gid}/members/{user_id}/roles/{role_id}",
                headers=headers,
            )
            # This endpoint returns 204 No Content on success
            if response.status_code == 204:
                return DiscordAPIResult(
                    ok=True,
                    status_code=204,
                    data={"added": True},
                )
            return self._handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"Failed to add role to user: {e}")
            return DiscordAPIResult(
                ok=False,
                status_code=0,
                error=str(e),
            )

