"""HTTP client for Patreon API v2.

Handles authentication (access token or OAuth2 refresh flow) and provides
methods for interacting with the Patreon API.

Environment Variables:
    PATREON_ACCESS_TOKEN: Creator access token (for quick setup)
    PATREON_CLIENT_ID: OAuth2 client ID (for refresh flow)
    PATREON_CLIENT_SECRET: OAuth2 client secret (for refresh flow)
    PATREON_REFRESH_TOKEN: OAuth2 refresh token (for production)
    PATREON_CREATOR_CAMPAIGN_ID: Default campaign ID (optional)
"""

import os
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

PATREON_API_BASE_URL = "https://www.patreon.com/api/oauth2/v2"
PATREON_TOKEN_URL = "https://www.patreon.com/api/oauth2/token"
DEFAULT_TIMEOUT = 30


# =============================================================================
# Custom Exceptions
# =============================================================================

class PatreonError(Exception):
    """Base exception for Patreon operations."""
    
    def __init__(self, message: str, error_type: str = "PatreonError", details: Optional[Dict] = None):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to a dictionary for API responses."""
        return {
            "error_type": self.error_type,
            "message": self.message,
            "details": self.details,
        }


class PatreonConfigError(PatreonError):
    """Raised when Patreon configuration is missing or invalid."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "ConfigurationError", details)


class PatreonAuthError(PatreonError):
    """Raised when Patreon authentication fails."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "AuthenticationError", details)


class PatreonAPIError(PatreonError):
    """Raised when a Patreon API call fails."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict] = None):
        details = details or {}
        if status_code:
            details["status_code"] = status_code
        super().__init__(message, "PatreonAPIError", details)


class PatreonNotFoundError(PatreonError):
    """Raised when a Patreon resource is not found."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "NotFoundError", details)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class PatreonConfig:
    """Configuration for Patreon API connection."""
    
    access_token: str
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    refresh_token: Optional[str] = None
    campaign_id: Optional[str] = None
    timeout: int = DEFAULT_TIMEOUT
    
    @classmethod
    def from_env(cls) -> "PatreonConfig":
        """Load configuration from environment variables.
        
        Returns:
            PatreonConfig instance
            
        Raises:
            PatreonConfigError: If required configuration is missing
        """
        access_token = os.environ.get("PATREON_ACCESS_TOKEN", "")
        client_id = os.environ.get("PATREON_CLIENT_ID")
        client_secret = os.environ.get("PATREON_CLIENT_SECRET")
        refresh_token = os.environ.get("PATREON_REFRESH_TOKEN")
        campaign_id = os.environ.get("PATREON_CREATOR_CAMPAIGN_ID")
        
        # Check if we have valid auth
        has_access_token = bool(access_token)
        has_oauth2 = all([client_id, client_secret, refresh_token])
        
        if not has_access_token and not has_oauth2:
            raise PatreonConfigError(
                "Patreon credentials not configured. "
                "Set PATREON_ACCESS_TOKEN for quick setup, or set "
                "PATREON_CLIENT_ID, PATREON_CLIENT_SECRET, and PATREON_REFRESH_TOKEN for OAuth2.",
                details={
                    "missing": "PATREON_ACCESS_TOKEN or OAuth2 credentials",
                    "hint": "See docs/patreon_integration.md for setup instructions"
                }
            )
        
        return cls(
            access_token=access_token,
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            campaign_id=campaign_id,
            timeout=int(os.environ.get("PATREON_TIMEOUT", str(DEFAULT_TIMEOUT))),
        )
    
    @classmethod
    def from_secrets_store(cls) -> Optional["PatreonConfig"]:
        """Load configuration from the encrypted secrets store.
        
        Returns:
            PatreonConfig if secrets found, None otherwise
        """
        try:
            from secrets_app.models import Secret
            
            def get_secret(key: str, default: str = "") -> str:
                """Get a secret value by key."""
                try:
                    secret = Secret.objects.get(service_type="patreon", key=key)
                    return secret.get_value()
                except Secret.DoesNotExist:
                    return default
            
            # Check if we have patreon secrets
            if not Secret.objects.filter(service_type="patreon").exists():
                return None
            
            access_token = get_secret("access_token", "")
            client_id = get_secret("client_id")
            client_secret = get_secret("client_secret")
            refresh_token = get_secret("refresh_token")
            campaign_id = get_secret("campaign_id")
            
            if not access_token and not (client_id and client_secret and refresh_token):
                return None
            
            logger.info("Loaded Patreon config from secrets store")
            return cls(
                access_token=access_token,
                client_id=client_id,
                client_secret=client_secret,
                refresh_token=refresh_token,
                campaign_id=campaign_id,
            )
        except Exception as e:
            logger.debug(f"Could not load from secrets store: {e}")
            return None
    
    @classmethod
    def from_settings(cls) -> "PatreonConfig":
        """Load configuration from secrets store, then Django settings, then env.
        
        Returns:
            PatreonConfig instance
            
        Raises:
            PatreonConfigError: If no valid configuration found
        """
        # Try secrets store first (encrypted credentials)
        config = cls.from_secrets_store()
        if config:
            return config
        
        # Fall back to environment variables
        return cls.from_env()
    
    @property
    def has_oauth2(self) -> bool:
        """Check if OAuth2 refresh credentials are available."""
        return all([self.client_id, self.client_secret, self.refresh_token])
    
    @property
    def has_access_token(self) -> bool:
        """Check if an access token is available."""
        return bool(self.access_token)


# =============================================================================
# Client
# =============================================================================

class PatreonClient:
    """HTTP client for Patreon API v2.
    
    Supports both direct access token auth and OAuth2 refresh flow.
    """
    
    def __init__(self, config: Optional[PatreonConfig] = None):
        """Initialize the client.
        
        Args:
            config: Optional configuration. If not provided, loads from settings/env.
        """
        self.config = config or PatreonConfig.from_settings()
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._client is None or self._client.is_closed:
            # Ensure we have a valid access token
            if not self.config.access_token and self.config.has_oauth2:
                await self._refresh_access_token()
            
            if not self.config.access_token:
                raise PatreonConfigError(
                    "No valid access token available. "
                    "Check your Patreon configuration."
                )
            
            self._client = httpx.AsyncClient(
                base_url=PATREON_API_BASE_URL,
                timeout=self.config.timeout,
                headers={
                    "Authorization": f"Bearer {self.config.access_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
        return self._client
    
    async def close(self):
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def _refresh_access_token(self) -> None:
        """Refresh the access token using OAuth2 refresh token.
        
        Raises:
            PatreonAuthError: If token refresh fails
        """
        if not self.config.has_oauth2:
            raise PatreonConfigError(
                "OAuth2 credentials not configured. "
                "Cannot refresh access token."
            )
        
        logger.info("Refreshing Patreon access token")
        
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.post(
                    PATREON_TOKEN_URL,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": self.config.refresh_token,
                        "client_id": self.config.client_id,
                        "client_secret": self.config.client_secret,
                    },
                )
                
                if response.status_code != 200:
                    raise PatreonAuthError(
                        f"Token refresh failed: {response.status_code}",
                        details={"response": response.text}
                    )
                
                data = response.json()
                self.config.access_token = data["access_token"]
                
                # Update refresh token if a new one was provided
                if "refresh_token" in data:
                    self.config.refresh_token = data["refresh_token"]
                    logger.info("Received new refresh token")
                
                logger.info("Access token refreshed successfully")
                
        except httpx.RequestError as e:
            raise PatreonAuthError(
                f"Token refresh request failed: {e}",
                details={"error": str(e)}
            )
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an authenticated API request.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/identity")
            params: Query parameters
            
        Returns:
            JSON response data
            
        Raises:
            PatreonAPIError: If the request fails
            PatreonAuthError: If authentication fails
            PatreonNotFoundError: If resource not found
        """
        client = await self._get_client()
        
        try:
            response = await client.request(method, endpoint, params=params)
            
            # Handle specific status codes
            if response.status_code == 401:
                # Token expired - try refresh if OAuth2 is configured
                if self.config.has_oauth2:
                    await self._refresh_access_token()
                    # Recreate client with new token
                    await self.close()
                    client = await self._get_client()
                    response = await client.request(method, endpoint, params=params)
                else:
                    raise PatreonAuthError(
                        "Access token is invalid or expired. "
                        "Generate a new token or configure OAuth2 refresh."
                    )
            
            if response.status_code == 404:
                raise PatreonNotFoundError(
                    f"Resource not found: {endpoint}",
                    details={"endpoint": endpoint}
                )
            
            if response.status_code >= 400:
                error_data = {}
                try:
                    error_data = response.json()
                except Exception:
                    error_data = {"raw": response.text}
                
                raise PatreonAPIError(
                    f"API request failed: {response.status_code}",
                    status_code=response.status_code,
                    details=error_data,
                )
            
            return response.json()
            
        except httpx.RequestError as e:
            raise PatreonAPIError(
                f"Request failed: {e}",
                details={"error": str(e)}
            )
    
    # -------------------------------------------------------------------------
    # API Methods
    # -------------------------------------------------------------------------
    
    async def get_identity(self, include_memberships: bool = False) -> Dict[str, Any]:
        """Get the current user's identity (creator info).
        
        Args:
            include_memberships: Include membership info
            
        Returns:
            Identity data including user and optionally campaign info
        """
        params = {
            "fields[user]": "email,first_name,full_name,image_url,url,created",
            "include": "memberships,campaign" if include_memberships else "campaign",
        }
        
        if include_memberships:
            params["fields[member]"] = "patron_status,is_follower,pledge_relationship_start"
        
        return await self._request("GET", "/identity", params=params)
    
    async def get_campaigns(self) -> Dict[str, Any]:
        """Get all campaigns for the current creator.
        
        Returns:
            Campaign data including all campaigns
        """
        params = {
            "fields[campaign]": "created_at,creation_name,patron_count,url,summary,is_monthly,is_nsfw",
        }
        
        return await self._request("GET", "/campaigns", params=params)
    
    async def get_campaign(self, campaign_id: str) -> Dict[str, Any]:
        """Get a specific campaign by ID.
        
        Args:
            campaign_id: The campaign ID
            
        Returns:
            Campaign details
        """
        params = {
            "fields[campaign]": "created_at,creation_name,patron_count,url,summary,is_monthly,is_nsfw,discord_server_id",
            "include": "tiers,creator",
            "fields[tier]": "amount_cents,title,description,patron_count,published",
            "fields[user]": "full_name,email,url",
        }
        
        return await self._request("GET", f"/campaigns/{campaign_id}", params=params)
    
    async def get_tiers(self, campaign_id: str) -> List[Dict[str, Any]]:
        """Get all tiers for a campaign.
        
        Args:
            campaign_id: The campaign ID
            
        Returns:
            List of tier data
        """
        # Get campaign with tiers included
        data = await self.get_campaign(campaign_id)
        
        # Extract tiers from included data
        tiers = []
        included = data.get("included", [])
        
        for item in included:
            if item.get("type") == "tier":
                tier_data = {
                    "id": item["id"],
                    **item.get("attributes", {}),
                }
                tiers.append(tier_data)
        
        return tiers
    
    async def get_patrons(
        self,
        campaign_id: str,
        status_filter: Optional[str] = None,
        cursor: Optional[str] = None,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Get patrons (members) for a campaign.
        
        Args:
            campaign_id: The campaign ID
            status_filter: Filter by status (active_patron, declined_patron, former_patron)
            cursor: Pagination cursor for next page
            page_size: Number of results per page (max 1000)
            
        Returns:
            Member data with pagination info
        """
        params = {
            "fields[member]": "full_name,email,patron_status,pledge_relationship_start,lifetime_support_cents,currently_entitled_amount_cents,last_charge_date,last_charge_status,note",
            "fields[tier]": "amount_cents,title,description",
            "fields[user]": "full_name,email,url",
            "include": "currently_entitled_tiers,user",
            "page[count]": min(page_size, 1000),
        }
        
        if cursor:
            params["page[cursor]"] = cursor
        
        data = await self._request("GET", f"/campaigns/{campaign_id}/members", params=params)
        
        # Process and filter members
        members = []
        included = {
            f"{item['type']}_{item['id']}": item 
            for item in data.get("included", [])
        }
        
        for member in data.get("data", []):
            attrs = member.get("attributes", {})
            
            # Apply status filter if specified
            if status_filter and attrs.get("patron_status") != status_filter:
                continue
            
            # Get tier info
            tier_ids = [
                rel["id"] 
                for rel in member.get("relationships", {}).get("currently_entitled_tiers", {}).get("data", [])
            ]
            
            tiers = []
            for tier_id in tier_ids:
                tier = included.get(f"tier_{tier_id}")
                if tier:
                    tiers.append({
                        "id": tier_id,
                        "title": tier.get("attributes", {}).get("title"),
                        "amount_cents": tier.get("attributes", {}).get("amount_cents"),
                    })
            
            # Get user info
            user_data = member.get("relationships", {}).get("user", {}).get("data", {})
            user_id = user_data.get("id") if user_data else None
            user_info = included.get(f"user_{user_id}", {}).get("attributes", {}) if user_id else {}
            
            members.append({
                "id": member["id"],
                "full_name": attrs.get("full_name") or user_info.get("full_name", ""),
                "email": attrs.get("email") or user_info.get("email", ""),
                "patron_status": attrs.get("patron_status"),
                "pledge_relationship_start": attrs.get("pledge_relationship_start"),
                "lifetime_support_cents": attrs.get("lifetime_support_cents"),
                "currently_entitled_amount_cents": attrs.get("currently_entitled_amount_cents"),
                "last_charge_date": attrs.get("last_charge_date"),
                "last_charge_status": attrs.get("last_charge_status"),
                "note": attrs.get("note"),
                "tiers": tiers,
            })
        
        # Get pagination info
        pagination = data.get("meta", {}).get("pagination", {})
        next_cursor = None
        if "cursors" in pagination and pagination["cursors"].get("next"):
            next_cursor = pagination["cursors"]["next"]
        
        return {
            "members": members,
            "total": pagination.get("total", len(members)),
            "next_cursor": next_cursor,
            "has_more": next_cursor is not None,
        }
    
    async def get_all_patrons(
        self,
        campaign_id: str,
        status_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get all patrons for a campaign (handles pagination).
        
        Args:
            campaign_id: The campaign ID
            status_filter: Filter by status
            
        Returns:
            List of all patron data
        """
        all_members = []
        cursor = None
        
        while True:
            result = await self.get_patrons(
                campaign_id,
                status_filter=status_filter,
                cursor=cursor,
            )
            
            all_members.extend(result["members"])
            
            if not result["has_more"]:
                break
            
            cursor = result["next_cursor"]
        
        return all_members
    
    async def get_patron(self, member_id: str) -> Dict[str, Any]:
        """Get a specific patron (member) by ID.
        
        Args:
            member_id: The member ID
            
        Returns:
            Member details
        """
        params = {
            "fields[member]": "full_name,email,patron_status,pledge_relationship_start,lifetime_support_cents,currently_entitled_amount_cents,last_charge_date,last_charge_status,note",
            "fields[tier]": "amount_cents,title,description",
            "fields[user]": "full_name,email,url",
            "include": "currently_entitled_tiers,user,campaign",
        }
        
        data = await self._request("GET", f"/members/{member_id}", params=params)
        
        # Process member data
        member = data.get("data", {})
        attrs = member.get("attributes", {})
        
        included = {
            f"{item['type']}_{item['id']}": item 
            for item in data.get("included", [])
        }
        
        # Get tier info
        tier_ids = [
            rel["id"] 
            for rel in member.get("relationships", {}).get("currently_entitled_tiers", {}).get("data", [])
        ]
        
        tiers = []
        for tier_id in tier_ids:
            tier = included.get(f"tier_{tier_id}")
            if tier:
                tiers.append({
                    "id": tier_id,
                    "title": tier.get("attributes", {}).get("title"),
                    "amount_cents": tier.get("attributes", {}).get("amount_cents"),
                })
        
        # Get user info
        user_data = member.get("relationships", {}).get("user", {}).get("data", {})
        user_id = user_data.get("id") if user_data else None
        user_info = included.get(f"user_{user_id}", {}).get("attributes", {}) if user_id else {}
        
        return {
            "id": member.get("id"),
            "full_name": attrs.get("full_name") or user_info.get("full_name", ""),
            "email": attrs.get("email") or user_info.get("email", ""),
            "patron_status": attrs.get("patron_status"),
            "pledge_relationship_start": attrs.get("pledge_relationship_start"),
            "lifetime_support_cents": attrs.get("lifetime_support_cents"),
            "currently_entitled_amount_cents": attrs.get("currently_entitled_amount_cents"),
            "last_charge_date": attrs.get("last_charge_date"),
            "last_charge_status": attrs.get("last_charge_status"),
            "note": attrs.get("note"),
            "tiers": tiers,
            "user_url": user_info.get("url"),
        }


# =============================================================================
# Helper Functions
# =============================================================================

def get_default_campaign_id() -> Optional[str]:
    """Get the default campaign ID from config.
    
    Returns:
        Campaign ID or None if not configured
    """
    return os.environ.get("PATREON_CREATOR_CAMPAIGN_ID")


def validate_patreon_config() -> tuple[bool, str]:
    """Validate Patreon configuration.
    
    Returns:
        Tuple of (is_valid, message)
    """
    access_token = os.environ.get("PATREON_ACCESS_TOKEN", "")
    client_id = os.environ.get("PATREON_CLIENT_ID")
    client_secret = os.environ.get("PATREON_CLIENT_SECRET")
    refresh_token = os.environ.get("PATREON_REFRESH_TOKEN")
    
    has_access_token = bool(access_token)
    has_oauth2 = all([client_id, client_secret, refresh_token])
    
    if has_access_token and has_oauth2:
        return True, "Full OAuth2 configuration with access token"
    elif has_oauth2:
        return True, "OAuth2 refresh flow configured"
    elif has_access_token:
        return True, "Access token configured (quick setup)"
    else:
        return False, "No Patreon credentials configured"

