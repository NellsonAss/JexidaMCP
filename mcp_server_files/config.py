"""Configuration management for MCP Server.

Loads configuration from environment variables with sensible defaults.
Also supports loading secrets from database with fallback to environment variables.
Secrets are never logged or exposed in responses.
"""

from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field

# Try to import database config (may fail if DB not initialized)
try:
    from config_db import load_config_from_db
    DB_CONFIG_AVAILABLE = True
except ImportError:
    DB_CONFIG_AVAILABLE = False
    load_config_from_db = None


class Settings(BaseSettings):
    """MCP Server configuration settings.
    
    All settings can be overridden via environment variables.
    Prefix: None (uses exact variable names).
    """
    
    # Server settings
    mcp_server_port: int = Field(default=8080, description="Port for MCP server")
    mcp_server_host: str = Field(default="0.0.0.0", description="Host to bind to")
    mcp_log_level: str = Field(default="INFO", description="Logging level")
    
    # Azure CLI settings
    azure_cli_path: str = Field(default="az", description="Path to Azure CLI binary")
    azure_cli_timeout: int = Field(default=300, description="Timeout for Azure CLI commands in seconds")
    azure_command_max_length: int = Field(default=4096, description="Maximum command length")
    
    # Azure authentication (optional for Phase 1)
    azure_tenant_id: Optional[str] = Field(default=None, description="Azure tenant ID")
    azure_client_id: Optional[str] = Field(default=None, description="Azure client ID")
    azure_client_secret: Optional[str] = Field(default=None, description="Azure client secret (never logged)")
    azure_default_subscription: Optional[str] = Field(default=None, description="Default Azure subscription ID")
    
    # HTTP health probe settings
    http_probe_default_timeout: int = Field(default=30, description="Default timeout for HTTP probes")
    http_probe_max_timeout: int = Field(default=120, description="Maximum timeout for HTTP probes")
    
    # UniFi Controller settings
    unifi_controller_url: Optional[str] = Field(
        default=None,
        description="UniFi Controller URL (e.g., https://192.168.1.1)"
    )
    unifi_username: Optional[str] = Field(
        default=None,
        description="UniFi Controller admin username"
    )
    unifi_password: Optional[str] = Field(
        default=None,
        description="UniFi Controller admin password (never logged)"
    )
    unifi_site: str = Field(
        default="default",
        description="UniFi site ID"
    )
    unifi_verify_ssl: bool = Field(
        default=False,
        description="Verify SSL certificates (False for self-signed certs)"
    )
    unifi_timeout: int = Field(
        default=30,
        description="Timeout for UniFi API requests in seconds"
    )
    
    # Network scanning settings
    nmap_path: str = Field(default="nmap", description="Path to nmap binary")
    nmap_timeout: int = Field(default=300, description="Timeout for nmap scans in seconds")
    
    # Synology NAS settings
    synology_url: Optional[str] = Field(
        default=None,
        description="Synology NAS URL (e.g., https://192.168.1.10:5001)"
    )
    synology_username: Optional[str] = Field(
        default=None,
        description="Synology NAS admin username"
    )
    synology_password: Optional[str] = Field(
        default=None,
        description="Synology NAS admin password (never logged)"
    )
    synology_verify_ssl: bool = Field(
        default=False,
        description="Verify SSL certificates for Synology NAS"
    )
    synology_timeout: int = Field(
        default=30,
        description="Timeout for Synology API requests in seconds"
    )
    
    # Database settings
    database_url: Optional[str] = Field(
        default=None,
        description="Database URL (defaults to sqlite:///secrets.db)"
    )
    
    # Encryption settings
    secret_encryption_key: Optional[str] = Field(
        default=None,
        description="Fernet encryption key for secrets (required in production)"
    )
    
    # Environment
    environment: str = Field(
        default="development",
        description="Environment: development or production"
    )
    
    # Authentication settings
    auth_password: Optional[str] = Field(
        default=None,
        description="Password for web UI access (if not set, auth is disabled)"
    )
    auth_session_secret: Optional[str] = Field(
        default=None,
        description="Secret key for session cookies (auto-generated if not set)"
    )
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",  # Ignore unknown environment variables
    }
    
    def get_safe_dict(self) -> dict:
        """Return config as dict with secrets masked.
        
        Use this for logging or debugging - never exposes secrets.
        """
        data = self.model_dump()
        # Mask secret fields
        if data.get("azure_client_secret"):
            data["azure_client_secret"] = "***MASKED***"
        if data.get("unifi_password"):
            data["unifi_password"] = "***MASKED***"
        if data.get("synology_password"):
            data["synology_password"] = "***MASKED***"
        if data.get("secret_encryption_key"):
            data["secret_encryption_key"] = "***MASKED***"
        if data.get("auth_password"):
            data["auth_password"] = "***MASKED***"
        if data.get("auth_session_secret"):
            data["auth_session_secret"] = "***MASKED***"
        return data


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance.
    
    Creates the instance on first call, then returns cached version.
    Loads secrets from database if available, with fallback to environment variables.
    """
    global _settings
    if _settings is None:
        # Load from environment first (non-secret defaults)
        _settings = Settings()
        
        # Override with database secrets if available
        if DB_CONFIG_AVAILABLE and load_config_from_db:
            try:
                db_config = load_config_from_db()
                # Update settings with database values (only if not None)
                for key, value in db_config.items():
                    if value is not None:
                        setattr(_settings, key, value)
            except Exception:
                # If DB access fails, fall back to environment variables
                # This allows the server to start even if DB isn't ready
                pass
    
    return _settings


def reload_settings() -> Settings:
    """Force reload settings from environment and database.
    
    Useful for testing or after environment/secret changes.
    """
    global _settings
    _settings = None  # Clear cache
    return get_settings()  # Reload from environment + database

