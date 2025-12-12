"""Discord integration tools for JexidaMCP.

Provides MCP tools for:
- Sending messages to Discord channels
- Creating channels and categories
- Managing roles
- Bootstrapping Discord server structure from YAML spec
"""

from .config import DiscordConfig, DiscordConfigError
from .client import DiscordClient, DiscordAPIResult, DiscordAPIError
from .api import (
    discord_send_message,
    discord_create_text_channel,
    discord_create_category_channel,
    discord_ensure_role,
    discord_get_guild_info,
)
from .bootstrap import discord_bootstrap_server

__all__ = [
    # Config
    "DiscordConfig",
    "DiscordConfigError",
    # Client
    "DiscordClient",
    "DiscordAPIResult",
    "DiscordAPIError",
    # Tools
    "discord_send_message",
    "discord_create_text_channel",
    "discord_create_category_channel",
    "discord_ensure_role",
    "discord_get_guild_info",
    "discord_bootstrap_server",
]

