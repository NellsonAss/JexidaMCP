"""Configuration for Discord integration.

Handles loading Discord bot credentials from:
1. Encrypted secrets store (preferred)
2. Django settings
3. Environment variables (fallback)
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


class DiscordConfigError(Exception):
    """Raised when Discord configuration is missing or invalid."""
    pass


@dataclass
class DiscordConfig:
    """Configuration for Discord bot connection."""
    
    bot_token: str
    guild_id: str
    default_announcements_channel_id: Optional[str] = None
    default_log_channel_id: Optional[str] = None
    timeout: int = 30
    
    def __post_init__(self):
        """Validate required fields."""
        if not self.bot_token:
            raise DiscordConfigError(
                "Discord integration is not configured: missing DISCORD_BOT_TOKEN environment variable"
            )
        if not self.guild_id:
            raise DiscordConfigError(
                "Discord integration is not configured: missing DISCORD_GUILD_ID environment variable"
            )
    
    @classmethod
    def from_env(cls) -> "DiscordConfig":
        """Load configuration from environment variables."""
        return cls(
            bot_token=os.environ.get("DISCORD_BOT_TOKEN", ""),
            guild_id=os.environ.get("DISCORD_GUILD_ID", ""),
            default_announcements_channel_id=os.environ.get("DISCORD_DEFAULT_ANNOUNCEMENTS_CHANNEL_ID"),
            default_log_channel_id=os.environ.get("DISCORD_DEFAULT_LOG_CHANNEL_ID"),
            timeout=int(os.environ.get("DISCORD_TIMEOUT", "30")),
        )
    
    @classmethod
    def from_secrets_store(cls) -> Optional["DiscordConfig"]:
        """Load configuration from the encrypted secrets store.
        
        Returns:
            DiscordConfig if secrets found, None otherwise
        """
        try:
            from secrets_app.models import Secret
            
            def get_secret(key: str, default: str = "") -> str:
                """Get a secret value by key."""
                try:
                    secret = Secret.objects.get(service_type="discord", key=key)
                    return secret.get_value()
                except Secret.DoesNotExist:
                    return default
            
            # Check if we have Discord secrets
            if not Secret.objects.filter(service_type="discord").exists():
                return None
            
            bot_token = get_secret("bot_token", "")
            guild_id = get_secret("guild_id", "")
            
            if not bot_token or not guild_id:
                return None
            
            logger.info("Loaded Discord config from secrets store")
            return cls(
                bot_token=bot_token,
                guild_id=guild_id,
                default_announcements_channel_id=get_secret("announcements_channel_id") or None,
                default_log_channel_id=get_secret("log_channel_id") or None,
                timeout=30,
            )
        except Exception as e:
            logger.debug(f"Could not load from secrets store: {e}")
            return None
    
    @classmethod
    def from_settings(cls) -> "DiscordConfig":
        """Load configuration from secrets store, then Django settings, then env.
        
        Raises:
            DiscordConfigError: If required configuration is missing
        """
        # Try secrets store first (encrypted credentials)
        config = cls.from_secrets_store()
        if config:
            return config
        
        # Fall back to Django settings / env vars
        try:
            from django.conf import settings
            return cls(
                bot_token=getattr(settings, "DISCORD_BOT_TOKEN", None) or os.environ.get("DISCORD_BOT_TOKEN", ""),
                guild_id=getattr(settings, "DISCORD_GUILD_ID", None) or os.environ.get("DISCORD_GUILD_ID", ""),
                default_announcements_channel_id=(
                    getattr(settings, "DISCORD_DEFAULT_ANNOUNCEMENTS_CHANNEL_ID", None) or 
                    os.environ.get("DISCORD_DEFAULT_ANNOUNCEMENTS_CHANNEL_ID")
                ),
                default_log_channel_id=(
                    getattr(settings, "DISCORD_DEFAULT_LOG_CHANNEL_ID", None) or 
                    os.environ.get("DISCORD_DEFAULT_LOG_CHANNEL_ID")
                ),
                timeout=int(
                    getattr(settings, "DISCORD_TIMEOUT", None) or 
                    os.environ.get("DISCORD_TIMEOUT", "30")
                ),
            )
        except Exception:
            return cls.from_env()

