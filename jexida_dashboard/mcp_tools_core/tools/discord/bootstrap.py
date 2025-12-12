"""Discord server bootstrap tool.

Reads a YAML configuration file and ensures the Discord server
structure matches the spec (categories, channels, roles).
"""

import logging
import os
import re
from pathlib import Path
from typing import Optional, Dict, Any, List

import yaml
from pydantic import BaseModel, Field

from .client import DiscordClient, CHANNEL_TYPE_CATEGORY, CHANNEL_TYPE_TEXT
from .config import DiscordConfigError

logger = logging.getLogger(__name__)

# Default config file location
DEFAULT_CONFIG_PATH = "config/discord_server.yml"


class DiscordBootstrapServerInput(BaseModel):
    """Input schema for discord_bootstrap_server."""
    
    config_path: Optional[str] = Field(
        default=None,
        description=f"Path to YAML config file. Defaults to {DEFAULT_CONFIG_PATH}"
    )
    guild_id: Optional[str] = Field(
        default=None,
        description="Override guild ID from config or environment"
    )
    dry_run: bool = Field(
        default=False,
        description="If true, only report what would be done without making changes"
    )


class DiscordBootstrapServerOutput(BaseModel):
    """Output schema for discord_bootstrap_server."""
    
    ok: bool = Field(description="Whether the bootstrap completed successfully")
    guild_id: str = Field(default="", description="Guild ID that was bootstrapped")
    categories_created: List[str] = Field(default_factory=list, description="Categories created")
    categories_existing: List[str] = Field(default_factory=list, description="Categories that already existed")
    channels_created: List[str] = Field(default_factory=list, description="Channels created")
    channels_existing: List[str] = Field(default_factory=list, description="Channels that already existed")
    roles_created: List[str] = Field(default_factory=list, description="Roles created")
    roles_existing: List[str] = Field(default_factory=list, description="Roles that already existed")
    errors: List[str] = Field(default_factory=list, description="Errors encountered during bootstrap")
    error: str = Field(default="", description="Fatal error message if failed")


def _expand_env_vars(value: str) -> str:
    """Expand environment variables in a string.
    
    Supports ${VAR_NAME} syntax.
    """
    pattern = r'\$\{([^}]+)\}'
    
    def replace(match):
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))
    
    return re.sub(pattern, replace, value)


def _load_config(config_path: str) -> Dict[str, Any]:
    """Load and parse the YAML config file.
    
    Args:
        config_path: Path to config file
        
    Returns:
        Parsed config dictionary
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config is invalid YAML
    """
    # Try multiple possible locations
    paths_to_try = [
        Path(config_path),
        Path("/opt/jexida-mcp") / config_path,
        Path.cwd() / config_path,
    ]
    
    config_file = None
    for path in paths_to_try:
        if path.exists():
            config_file = path
            break
    
    if not config_file:
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Expand environment variables
    content = _expand_env_vars(content)
    
    return yaml.safe_load(content)


def _normalize_channel_name(name: str) -> str:
    """Normalize a channel name for comparison.
    
    Discord channel names are lowercase with hyphens.
    """
    return name.lower().replace(" ", "-").replace("_", "-")


async def discord_bootstrap_server(params: DiscordBootstrapServerInput) -> DiscordBootstrapServerOutput:
    """Bootstrap a Discord server from a YAML configuration.
    
    Reads the configuration file and ensures the server structure matches:
    - Creates missing categories
    - Creates missing text channels under their categories
    - Creates missing roles
    
    This operation is idempotent - running it multiple times produces the same result.
    
    Args:
        params: Bootstrap configuration
        
    Returns:
        Summary of what was created vs what already existed
    """
    config_path = params.config_path or DEFAULT_CONFIG_PATH
    logger.info(f"Bootstrapping Discord server from: {config_path}")
    
    # Result tracking
    result = DiscordBootstrapServerOutput(ok=True)
    
    try:
        # Load config
        config = _load_config(config_path)
        logger.info(f"Loaded config with {len(config.get('categories', []))} categories and {len(config.get('roles', []))} roles")
        
    except FileNotFoundError as e:
        return DiscordBootstrapServerOutput(
            ok=False,
            error=f"Config file not found: {config_path}",
        )
    except yaml.YAMLError as e:
        return DiscordBootstrapServerOutput(
            ok=False,
            error=f"Invalid YAML in config: {e}",
        )
    
    try:
        with DiscordClient() as client:
            # Determine guild ID
            guild_id = params.guild_id or config.get("guild_id") or client.config.guild_id
            result.guild_id = guild_id
            
            if params.dry_run:
                logger.info("DRY RUN - no changes will be made")
            
            # Get existing channels
            channels_result = client.get_guild_channels(guild_id)
            if not channels_result.ok:
                return DiscordBootstrapServerOutput(
                    ok=False,
                    error=f"Failed to get existing channels: {channels_result.error}",
                )
            
            existing_channels = channels_result.data or []
            
            # Build lookup maps
            existing_categories = {
                _normalize_channel_name(ch["name"]): ch
                for ch in existing_channels
                if ch.get("type") == CHANNEL_TYPE_CATEGORY
            }
            existing_text_channels = {
                (_normalize_channel_name(ch["name"]), ch.get("parent_id")): ch
                for ch in existing_channels
                if ch.get("type") == CHANNEL_TYPE_TEXT
            }
            
            # Process categories and their channels
            for category_spec in config.get("categories", []):
                category_name = category_spec.get("name", "")
                if not category_name:
                    continue
                
                normalized_cat_name = _normalize_channel_name(category_name)
                
                # Ensure category exists
                if normalized_cat_name in existing_categories:
                    category_id = existing_categories[normalized_cat_name]["id"]
                    result.categories_existing.append(category_name)
                    logger.info(f"Category '{category_name}' already exists")
                else:
                    if params.dry_run:
                        logger.info(f"[DRY RUN] Would create category: {category_name}")
                        result.categories_created.append(f"{category_name} (dry run)")
                        category_id = None
                    else:
                        # Create category
                        cat_result = client.create_category_channel(
                            guild_id,
                            category_name,
                            reason="Created by JexidaMCP Discord bootstrap",
                        )
                        if cat_result.ok:
                            category_id = cat_result.data.get("id")
                            result.categories_created.append(category_name)
                            logger.info(f"Created category: {category_name}")
                        else:
                            result.errors.append(f"Failed to create category '{category_name}': {cat_result.error}")
                            logger.error(f"Failed to create category '{category_name}': {cat_result.error}")
                            continue
                
                # Process channels in this category
                for channel_spec in category_spec.get("channels", []):
                    channel_name = channel_spec.get("name", "")
                    if not channel_name:
                        continue
                    
                    normalized_ch_name = _normalize_channel_name(channel_name)
                    channel_topic = channel_spec.get("topic", "")
                    
                    # Check if channel exists (with any parent or this parent)
                    channel_exists = False
                    for (ch_name, parent_id), ch_data in existing_text_channels.items():
                        if ch_name == normalized_ch_name:
                            channel_exists = True
                            break
                    
                    if channel_exists:
                        result.channels_existing.append(f"{category_name}/{channel_name}")
                        logger.info(f"Channel '{channel_name}' already exists")
                    else:
                        if params.dry_run:
                            logger.info(f"[DRY RUN] Would create channel: {channel_name}")
                            result.channels_created.append(f"{category_name}/{channel_name} (dry run)")
                        elif category_id:
                            # Create channel
                            ch_result = client.create_text_channel(
                                guild_id,
                                channel_name,
                                parent_id=category_id,
                                topic=channel_topic,
                                reason="Created by JexidaMCP Discord bootstrap",
                            )
                            if ch_result.ok:
                                result.channels_created.append(f"{category_name}/{channel_name}")
                                logger.info(f"Created channel: {category_name}/{channel_name}")
                            else:
                                result.errors.append(f"Failed to create channel '{channel_name}': {ch_result.error}")
                                logger.error(f"Failed to create channel '{channel_name}': {ch_result.error}")
            
            # Process roles
            for role_spec in config.get("roles", []):
                role_name = role_spec.get("name", "")
                if not role_name:
                    continue
                
                hoist = role_spec.get("hoist", False)
                color = role_spec.get("color")
                permissions = role_spec.get("permissions")
                
                if params.dry_run:
                    # Check if role exists for dry run
                    roles_result = client.get_guild_roles(guild_id)
                    if roles_result.ok:
                        existing_roles = {r["name"].lower(): r for r in roles_result.data or []}
                        if role_name.lower() in existing_roles:
                            result.roles_existing.append(role_name)
                            logger.info(f"Role '{role_name}' already exists")
                        else:
                            result.roles_created.append(f"{role_name} (dry run)")
                            logger.info(f"[DRY RUN] Would create role: {role_name}")
                else:
                    # Ensure role exists
                    role_result = client.ensure_role(
                        guild_id,
                        role_name,
                        permissions=permissions,
                        color=color,
                        hoist=hoist,
                    )
                    if role_result.ok:
                        if role_result.data.get("_existed"):
                            result.roles_existing.append(role_name)
                        else:
                            result.roles_created.append(role_name)
                    else:
                        result.errors.append(f"Failed to ensure role '{role_name}': {role_result.error}")
                        logger.error(f"Failed to ensure role '{role_name}': {role_result.error}")
            
            # Set overall success based on errors
            if result.errors:
                result.ok = False
                result.error = f"Bootstrap completed with {len(result.errors)} error(s)"
            
            return result
            
    except DiscordConfigError as e:
        logger.error(f"Discord configuration error: {e}")
        return DiscordBootstrapServerOutput(
            ok=False,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Bootstrap failed: {e}")
        return DiscordBootstrapServerOutput(
            ok=False,
            error=str(e),
        )

