"""Azure Security tools (Phase 2 - Stubs).

Provides MCP tools for:
- Creating Key Vaults
- Managing secrets
- Assigning RBAC roles

NOTE: These are stub implementations. Full implementation is planned for Phase 2.
"""

import logging
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# Input/Output Schemas
# =============================================================================

class AzureSecurityCreateKeyVaultInput(BaseModel):
    """Input schema for azure_security_create_key_vault."""
    resource_group: str = Field(description="Resource group name")
    name: str = Field(description="Key Vault name (globally unique)")
    location: str = Field(description="Azure region")
    sku: str = Field(default="standard", description="SKU: standard or premium")
    enable_soft_delete: bool = Field(default=True, description="Enable soft delete")
    soft_delete_retention_days: int = Field(default=90, description="Soft delete retention days")
    enable_purge_protection: bool = Field(default=False, description="Enable purge protection")
    tags: Optional[Dict[str, str]] = Field(default=None, description="Tags")
    subscription_id: Optional[str] = Field(default=None, description="Subscription ID")


class AzureSecurityCreateKeyVaultOutput(BaseModel):
    """Output schema for azure_security_create_key_vault."""
    success: bool = Field(description="Whether creation succeeded")
    name: str = Field(default="", description="Key Vault name")
    resource_id: str = Field(default="", description="Full resource ID")
    vault_uri: str = Field(default="", description="Key Vault URI")
    error: str = Field(default="", description="Error message if failed")


class AzureSecuritySetSecretInput(BaseModel):
    """Input schema for azure_security_set_secret."""
    vault_name: str = Field(description="Key Vault name")
    secret_name: str = Field(description="Secret name")
    secret_value: str = Field(description="Secret value")
    content_type: Optional[str] = Field(default=None, description="Content type")
    tags: Optional[Dict[str, str]] = Field(default=None, description="Secret tags")
    expiration_date: Optional[str] = Field(default=None, description="Expiration date (ISO 8601)")


class AzureSecuritySetSecretOutput(BaseModel):
    """Output schema for azure_security_set_secret."""
    success: bool = Field(description="Whether the secret was set")
    secret_name: str = Field(default="", description="Secret name")
    vault_name: str = Field(default="", description="Key Vault name")
    version: str = Field(default="", description="Secret version")
    error: str = Field(default="", description="Error message if failed")


class AzureSecurityGetSecretInput(BaseModel):
    """Input schema for azure_security_get_secret."""
    vault_name: str = Field(description="Key Vault name")
    secret_name: str = Field(description="Secret name")
    version: Optional[str] = Field(default=None, description="Secret version (latest if not specified)")


class AzureSecurityGetSecretOutput(BaseModel):
    """Output schema for azure_security_get_secret."""
    success: bool = Field(description="Whether the secret was retrieved")
    secret_name: str = Field(default="", description="Secret name")
    value: str = Field(default="", description="Secret value")
    version: str = Field(default="", description="Secret version")
    content_type: str = Field(default="", description="Content type")
    error: str = Field(default="", description="Error message if failed")


class AzureSecurityAssignRoleInput(BaseModel):
    """Input schema for azure_security_assign_role_to_principal."""
    scope: str = Field(description="Scope for the role assignment (resource ID)")
    role_definition_name: str = Field(
        description="Role name (e.g., 'Contributor', 'Reader', 'Storage Blob Data Contributor')"
    )
    principal_id: str = Field(description="Object ID of the principal (user, group, service principal)")
    principal_type: str = Field(
        default="ServicePrincipal",
        description="Principal type: User, Group, ServicePrincipal"
    )


class AzureSecurityAssignRoleOutput(BaseModel):
    """Output schema for azure_security_assign_role_to_principal."""
    success: bool = Field(description="Whether the role was assigned")
    role_assignment_id: str = Field(default="", description="Role assignment ID")
    role_definition_name: str = Field(default="", description="Role name")
    principal_id: str = Field(default="", description="Principal ID")
    scope: str = Field(default="", description="Assignment scope")
    error: str = Field(default="", description="Error message if failed")


# =============================================================================
# Stub Tool Implementations
# =============================================================================

async def azure_security_create_key_vault(
    params: AzureSecurityCreateKeyVaultInput
) -> AzureSecurityCreateKeyVaultOutput:
    """Create an Azure Key Vault.
    
    NOTE: This is a stub implementation. Full implementation planned for Phase 2.
    
    Args:
        params: Key Vault configuration
        
    Returns:
        Created Key Vault details
        
    Raises:
        NotImplementedError: This is a stub
    """
    logger.warning("azure_security_create_key_vault is a stub - not yet implemented")
    raise NotImplementedError(
        "azure_security_create_key_vault is planned for Phase 2. "
        "Use azure_cli_run for Key Vault operations in the meantime."
    )


async def azure_security_set_secret(
    params: AzureSecuritySetSecretInput
) -> AzureSecuritySetSecretOutput:
    """Set a secret in Azure Key Vault.
    
    NOTE: This is a stub implementation. Full implementation planned for Phase 2.
    
    Args:
        params: Secret configuration
        
    Returns:
        Set secret result
        
    Raises:
        NotImplementedError: This is a stub
    """
    logger.warning("azure_security_set_secret is a stub - not yet implemented")
    raise NotImplementedError(
        "azure_security_set_secret is planned for Phase 2. "
        "Use azure_cli_run for secret operations in the meantime."
    )


async def azure_security_get_secret(
    params: AzureSecurityGetSecretInput
) -> AzureSecurityGetSecretOutput:
    """Get a secret from Azure Key Vault.
    
    NOTE: This is a stub implementation. Full implementation planned for Phase 2.
    
    Args:
        params: Secret retrieval parameters
        
    Returns:
        Secret value and metadata
        
    Raises:
        NotImplementedError: This is a stub
    """
    logger.warning("azure_security_get_secret is a stub - not yet implemented")
    raise NotImplementedError(
        "azure_security_get_secret is planned for Phase 2. "
        "Use azure_cli_run for secret operations in the meantime."
    )


async def azure_security_assign_role_to_principal(
    params: AzureSecurityAssignRoleInput
) -> AzureSecurityAssignRoleOutput:
    """Assign an RBAC role to a principal.
    
    NOTE: This is a stub implementation. Full implementation planned for Phase 2.
    
    Args:
        params: Role assignment configuration
        
    Returns:
        Role assignment result
        
    Raises:
        NotImplementedError: This is a stub
    """
    logger.warning("azure_security_assign_role_to_principal is a stub - not yet implemented")
    raise NotImplementedError(
        "azure_security_assign_role_to_principal is planned for Phase 2. "
        "Use azure_cli_run for RBAC operations in the meantime."
    )

