"""Database-backed configuration loading for MCP Server.

Loads secrets from database with fallback to environment variables.
"""

from typing import Optional

from sqlalchemy.orm import Session

from database import Secret, decrypt_value, get_db, get_session_local


def get_secret_from_db(service_type: str, key: str) -> Optional[str]:
    """Get a secret value from the database.
    
    Args:
        service_type: Service type (azure, unifi, generic)
        key: Secret key name
        
    Returns:
        Decrypted secret value or None if not found
    """
    db = next(get_db())
    try:
        secret = db.query(Secret).filter(
            Secret.service_type == service_type,
            Secret.key == key
        ).first()
        
        if secret:
            return decrypt_value(secret.encrypted_value)
        return None
    finally:
        db.close()


def get_all_secrets_for_service(service_type: str) -> dict[str, str]:
    """Get all secrets for a service type as a dictionary.
    
    Args:
        service_type: Service type (azure, unifi, generic)
        
    Returns:
        Dictionary mapping key -> decrypted value
    """
    db = next(get_db())
    try:
        secrets = db.query(Secret).filter(
            Secret.service_type == service_type
        ).all()
        
        result = {}
        for secret in secrets:
            result[secret.key] = decrypt_value(secret.encrypted_value)
        return result
    finally:
        db.close()


def load_config_from_db() -> dict[str, Optional[str]]:
    """Load configuration values from database.
    
    Returns a dictionary with config keys and values.
    Falls back to None if not found in database.
    """
    config = {}
    
    # Azure secrets
    azure_secrets = get_all_secrets_for_service("azure")
    config["azure_tenant_id"] = azure_secrets.get("tenant_id")
    config["azure_client_id"] = azure_secrets.get("client_id")
    config["azure_client_secret"] = azure_secrets.get("client_secret")
    config["azure_default_subscription"] = azure_secrets.get("subscription_id")
    
    # UniFi secrets
    unifi_secrets = get_all_secrets_for_service("unifi")
    config["unifi_controller_url"] = unifi_secrets.get("controller_url")
    config["unifi_username"] = unifi_secrets.get("username")
    config["unifi_password"] = unifi_secrets.get("password")
    config["unifi_site"] = unifi_secrets.get("site", "default")
    
    # Synology secrets
    synology_secrets = get_all_secrets_for_service("synology")
    config["synology_url"] = synology_secrets.get("url")
    config["synology_username"] = synology_secrets.get("username")
    config["synology_password"] = synology_secrets.get("password")
    
    return config

