"""Patreon tools package.

Provides MCP tools for interacting with the Patreon API v2:
- Get creator/campaign information
- List tiers and their details
- List and filter patrons
- Export patron data for automation workflows

Environment Variables:
    PATREON_ACCESS_TOKEN: Creator access token (required for quick setup)
    PATREON_CLIENT_ID: OAuth2 client ID (for refresh flow)
    PATREON_CLIENT_SECRET: OAuth2 client secret (for refresh flow)
    PATREON_REFRESH_TOKEN: OAuth2 refresh token (for production)
    PATREON_CREATOR_CAMPAIGN_ID: Default campaign ID (optional, can be discovered)
"""

from .client import (
    PatreonClient,
    PatreonConfig,
    PatreonError,
    PatreonConfigError,
    PatreonAuthError,
    PatreonAPIError,
    PatreonNotFoundError,
)

from .tools import (
    patreon_get_creator,
    patreon_get_tiers,
    patreon_get_patrons,
    patreon_get_patron,
    patreon_export_patrons,
)

__all__ = [
    # Client
    "PatreonClient",
    "PatreonConfig",
    
    # Exceptions
    "PatreonError",
    "PatreonConfigError",
    "PatreonAuthError",
    "PatreonAPIError",
    "PatreonNotFoundError",
    
    # Tools
    "patreon_get_creator",
    "patreon_get_tiers",
    "patreon_get_patrons",
    "patreon_get_patron",
    "patreon_export_patrons",
]

