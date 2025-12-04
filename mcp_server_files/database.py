"""Database models and session management for secrets storage.

Uses SQLAlchemy with SQLite for simplicity. Secrets are encrypted at rest
using Fernet symmetric encryption.
"""

import os
from datetime import datetime
from typing import Optional

from cryptography.fernet import Fernet
from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config import get_settings

Base = declarative_base()


class Secret(Base):
    """Secret storage model with encryption at rest."""

    __tablename__ = "secrets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    service_type = Column(String(50), nullable=False, index=True)  # azure, unifi, generic
    key = Column(String(255), nullable=False)  # e.g., "azure_client_secret", "unifi_password"
    encrypted_value = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Secret(name={self.name}, service_type={self.service_type}, key={self.key})>"


# Encryption key management
def get_encryption_key() -> bytes:
    """Get encryption key from settings.
    
    If not set, generates a new key (for development only).
    In production, SECRET_ENCRYPTION_KEY must be set.
    """
    settings = get_settings()
    
    if settings.secret_encryption_key:
        return settings.secret_encryption_key.encode()
    
    # For development: generate and warn
    # In production, this should fail
    if settings.environment != "production":
        print("WARNING: SECRET_ENCRYPTION_KEY not set. Generating temporary key for development.")
        new_key = Fernet.generate_key()
        print(f"Generated key (save this to SECRET_ENCRYPTION_KEY): {new_key.decode()}")
        return new_key
    
    raise ValueError("SECRET_ENCRYPTION_KEY must be set in production")


def get_fernet() -> Fernet:
    """Get Fernet encryption instance."""
    key = get_encryption_key()
    return Fernet(key)


def encrypt_value(value: str) -> str:
    """Encrypt a secret value."""
    fernet = get_fernet()
    return fernet.encrypt(value.encode()).decode()


def decrypt_value(encrypted_value: str) -> str:
    """Decrypt a secret value."""
    fernet = get_fernet()
    return fernet.decrypt(encrypted_value.encode()).decode()


# Database setup
def get_database_url() -> str:
    """Get database URL from settings or default to SQLite."""
    settings = get_settings()
    
    if settings.database_url:
        return settings.database_url
    
    # Default to SQLite in same directory as config
    db_path = os.path.join(os.path.dirname(__file__), "secrets.db")
    return f"sqlite:///{db_path}"


def get_engine():
    """Get SQLAlchemy engine."""
    database_url = get_database_url()
    return create_engine(database_url, connect_args={"check_same_thread": False} if "sqlite" in database_url else {})


def get_session_local():
    """Get session factory."""
    return sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


# Create tables
def init_db():
    """Initialize database tables."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


# Dependency for FastAPI
def get_db():
    """Database dependency for FastAPI routes."""
    db = get_session_local()()
    try:
        yield db
    finally:
        db.close()

