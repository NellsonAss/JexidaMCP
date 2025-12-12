"""Azure authentication and credential management.

Provides centralized Azure authentication using DefaultAzureCredential,
with fallback to ClientSecretCredential for service principal auth.

Environment Variables:
    AZURE_TENANT_ID: Azure Active Directory tenant ID
    AZURE_CLIENT_ID: Service principal client ID
    AZURE_CLIENT_SECRET: Service principal client secret
    AZURE_SUBSCRIPTION_ID: Default Azure subscription ID
"""

import logging
import os
from typing import Optional, Tuple, Any, Dict

logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class AzureError(Exception):
    """Base exception for Azure operations."""
    
    def __init__(self, message: str, error_type: str = "AzureError", details: Optional[Dict] = None):
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


class AzureAuthError(AzureError):
    """Raised when Azure authentication fails."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "AuthenticationError", details)


class AzureConfigError(AzureError):
    """Raised when Azure configuration is missing or invalid."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "ConfigurationError", details)


class AzureNotFoundError(AzureError):
    """Raised when an Azure resource is not found."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "NotFoundError", details)


class AzureValidationError(AzureError):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "ValidationError", details)


class AzureAPIError(AzureError):
    """Raised when an Azure API call fails."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict] = None):
        details = details or {}
        if status_code:
            details["status_code"] = status_code
        super().__init__(message, "AzureAPIError", details)


class AzureAuthorizationError(AzureError):
    """Raised when authorization to Azure resource fails."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "AuthorizationError", details)


# =============================================================================
# Credential Management
# =============================================================================

# Cache for credentials to avoid repeated instantiation
_credential_cache = None


def get_azure_credential():
    """Get Azure credential using DefaultAzureCredential.
    
    DefaultAzureCredential tries multiple authentication methods in order:
    1. Environment variables (service principal)
    2. Managed Identity (on Azure VMs)
    3. Azure CLI (if logged in via 'az login')
    4. Visual Studio Code
    5. Azure PowerShell
    
    Returns:
        Azure credential object
        
    Raises:
        AzureAuthError: If no valid credential could be obtained
    """
    global _credential_cache
    
    if _credential_cache is not None:
        return _credential_cache
    
    try:
        from azure.identity import DefaultAzureCredential, ClientSecretCredential
    except ImportError:
        raise AzureConfigError(
            "Azure Identity package not installed. "
            "Install with: pip install azure-identity",
            details={"missing_package": "azure-identity"}
        )
    
    # Check if service principal credentials are explicitly set
    tenant_id = os.environ.get("AZURE_TENANT_ID")
    client_id = os.environ.get("AZURE_CLIENT_ID")
    client_secret = os.environ.get("AZURE_CLIENT_SECRET")
    
    try:
        if tenant_id and client_id and client_secret:
            # Use explicit service principal credentials
            logger.info("Using ClientSecretCredential with service principal")
            _credential_cache = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
            )
        else:
            # Use DefaultAzureCredential for flexible auth
            logger.info("Using DefaultAzureCredential")
            _credential_cache = DefaultAzureCredential()
        
        return _credential_cache
        
    except Exception as e:
        logger.error(f"Failed to create Azure credential: {e}")
        raise AzureAuthError(
            f"Failed to create Azure credential: {str(e)}",
            details={"original_error": str(e)}
        )


def get_subscription_id(subscription_id: Optional[str] = None) -> str:
    """Get Azure subscription ID from parameter or environment.
    
    Args:
        subscription_id: Optional explicit subscription ID
        
    Returns:
        Azure subscription ID
        
    Raises:
        AzureConfigError: If no subscription ID is available
    """
    # Use explicit parameter if provided
    if subscription_id:
        return subscription_id
    
    # Fall back to environment variable
    env_subscription = os.environ.get("AZURE_SUBSCRIPTION_ID")
    if env_subscription:
        return env_subscription
    
    raise AzureConfigError(
        "No Azure subscription ID provided. "
        "Set AZURE_SUBSCRIPTION_ID environment variable or pass subscription_id parameter.",
        details={"missing_var": "AZURE_SUBSCRIPTION_ID"}
    )


def get_credential_and_subscription(
    subscription_id: Optional[str] = None
) -> Tuple[Any, str]:
    """Get both credential and subscription ID.
    
    Convenience function for tools that need both.
    
    Args:
        subscription_id: Optional explicit subscription ID
        
    Returns:
        Tuple of (credential, subscription_id)
    """
    credential = get_azure_credential()
    sub_id = get_subscription_id(subscription_id)
    return credential, sub_id


def get_tenant_id() -> Optional[str]:
    """Get Azure tenant ID from environment.
    
    Returns:
        Azure tenant ID or None if not set
    """
    return os.environ.get("AZURE_TENANT_ID")


def clear_credential_cache():
    """Clear the cached credential.
    
    Useful for testing or when credentials change.
    """
    global _credential_cache
    _credential_cache = None


# =============================================================================
# Error Handling Helpers
# =============================================================================

def wrap_azure_error(exception: Exception) -> AzureError:
    """Wrap an Azure SDK exception into our consistent error format.
    
    Args:
        exception: Original Azure SDK exception
        
    Returns:
        Wrapped AzureError subclass
    """
    error_str = str(exception).lower()
    error_details = {"original_error": str(exception)}
    
    # Try to extract status code from Azure exceptions
    status_code = getattr(exception, 'status_code', None)
    if status_code:
        error_details["status_code"] = status_code
    
    # Classify the error
    if "authentication" in error_str or "credential" in error_str:
        return AzureAuthError(str(exception), error_details)
    
    if "authorization" in error_str or "forbidden" in error_str or status_code == 403:
        return AzureAuthorizationError(str(exception), error_details)
    
    if "not found" in error_str or status_code == 404:
        return AzureNotFoundError(str(exception), error_details)
    
    if "validation" in error_str or "invalid" in error_str or status_code == 400:
        return AzureValidationError(str(exception), error_details)
    
    return AzureAPIError(str(exception), status_code, error_details)


def handle_azure_error(func):
    """Decorator to wrap Azure SDK exceptions.
    
    Catches Azure SDK exceptions and wraps them in our error format.
    """
    import functools
    
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except AzureError:
            raise
        except Exception as e:
            raise wrap_azure_error(e)
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AzureError:
            raise
        except Exception as e:
            raise wrap_azure_error(e)
    
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


# =============================================================================
# Configuration Helpers
# =============================================================================

def get_azure_config() -> Dict[str, Any]:
    """Get current Azure configuration (safe to expose).
    
    Returns:
        Dictionary with Azure configuration (no secrets)
    """
    return {
        "tenant_id": os.environ.get("AZURE_TENANT_ID"),
        "client_id": os.environ.get("AZURE_CLIENT_ID"),
        "subscription_id": os.environ.get("AZURE_SUBSCRIPTION_ID"),
        "has_client_secret": bool(os.environ.get("AZURE_CLIENT_SECRET")),
    }


def validate_azure_config() -> Tuple[bool, str]:
    """Validate Azure configuration.
    
    Returns:
        Tuple of (is_valid, message)
    """
    tenant_id = os.environ.get("AZURE_TENANT_ID")
    client_id = os.environ.get("AZURE_CLIENT_ID")
    client_secret = os.environ.get("AZURE_CLIENT_SECRET")
    subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")
    
    # Check if we have service principal credentials
    has_sp_creds = all([tenant_id, client_id, client_secret])
    
    if has_sp_creds:
        if not subscription_id:
            return False, "Service principal credentials set but AZURE_SUBSCRIPTION_ID missing"
        return True, "Service principal authentication configured"
    
    # Check if any partial credentials are set
    if any([tenant_id, client_id, client_secret]):
        return False, "Partial service principal credentials. Need all of: AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET"
    
    # No explicit credentials - will try DefaultAzureCredential
    return True, "No explicit credentials. Will use DefaultAzureCredential (Azure CLI, Managed Identity, etc.)"

