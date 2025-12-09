"""Secret encryption/decryption services.

Provides Fernet symmetric encryption for secrets at rest.
"""

import os
from typing import Optional

from cryptography.fernet import Fernet

from ..logging import get_logger

logger = get_logger(__name__)


def get_encryption_key() -> bytes:
    """Get encryption key from environment.
    
    Returns:
        Encryption key bytes
        
    Raises:
        ValueError: If key not set in production
    """
    key = os.environ.get("SECRET_ENCRYPTION_KEY", "").strip()
    
    if key:
        return key.encode()
    
    # For development: generate and warn
    environment = os.environ.get("ENVIRONMENT", "development")
    if environment != "production":
        logger.warning("SECRET_ENCRYPTION_KEY not set. Generating temporary key.")
        new_key = Fernet.generate_key()
        logger.warning(f"Generated key (save this): {new_key.decode()}")
        return new_key
    
    raise ValueError("SECRET_ENCRYPTION_KEY must be set in production")


def get_fernet() -> Fernet:
    """Get Fernet encryption instance.
    
    Returns:
        Configured Fernet instance
    """
    key = get_encryption_key()
    return Fernet(key)


def encrypt_value(value: str) -> str:
    """Encrypt a secret value.
    
    Args:
        value: Plain text value to encrypt
        
    Returns:
        Encrypted value as string
    """
    fernet = get_fernet()
    return fernet.encrypt(value.encode()).decode()


def decrypt_value(encrypted_value: str) -> str:
    """Decrypt a secret value.
    
    Args:
        encrypted_value: Encrypted value string
        
    Returns:
        Decrypted plain text value
    """
    fernet = get_fernet()
    return fernet.decrypt(encrypted_value.encode()).decode()

