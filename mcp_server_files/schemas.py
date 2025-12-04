"""Pydantic schemas for secret management forms."""

from typing import Optional
from pydantic import BaseModel, Field


class SecretCreate(BaseModel):
    """Schema for creating a new secret."""
    name: str = Field(..., description="Human-readable name for this secret")
    service_type: str = Field(..., description="Service type: azure, unifi, or generic")
    key: str = Field(..., description="Secret key (e.g., 'azure_client_secret', 'unifi_password')")
    value: str = Field(..., description="Secret value (will be encrypted)")


class SecretUpdate(BaseModel):
    """Schema for updating an existing secret."""
    name: Optional[str] = Field(None, description="Human-readable name")
    value: Optional[str] = Field(None, description="Secret value (will be encrypted if provided)")


class SecretResponse(BaseModel):
    """Schema for secret response (value is never included)."""
    id: int
    name: str
    service_type: str
    key: str
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True

