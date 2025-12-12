"""Azure Data tools for Storage and SQL operations.

Provides MCP tools for:
- Creating storage accounts
- Creating blob containers
- Creating SQL servers and databases
- Managing SQL firewall rules
"""

import logging
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field

from .auth import (
    get_credential_and_subscription,
    AzureError,
    wrap_azure_error,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Storage Input/Output Schemas
# =============================================================================

class AzureDataCreateStorageAccountInput(BaseModel):
    """Input schema for azure_data_create_storage_account."""
    resource_group: str = Field(description="Resource group name")
    name: str = Field(
        description="Storage account name (3-24 chars, lowercase letters and numbers only)"
    )
    location: str = Field(description="Azure region (e.g., 'eastus')")
    sku: str = Field(
        default="Standard_LRS",
        description="SKU: Standard_LRS, Standard_GRS, Standard_RAGRS, Standard_ZRS, Premium_LRS"
    )
    kind: str = Field(
        default="StorageV2",
        description="Storage kind: StorageV2, BlobStorage, BlockBlobStorage, FileStorage"
    )
    access_tier: Optional[str] = Field(
        default="Hot",
        description="Access tier: Hot, Cool (only for BlobStorage/StorageV2)"
    )
    tags: Optional[Dict[str, str]] = Field(
        default=None,
        description="Tags to apply"
    )
    subscription_id: Optional[str] = Field(
        default=None,
        description="Subscription ID (uses default if not provided)"
    )


class AzureDataCreateStorageAccountOutput(BaseModel):
    """Output schema for azure_data_create_storage_account."""
    success: bool = Field(description="Whether creation succeeded")
    name: str = Field(default="", description="Storage account name")
    resource_group: str = Field(default="", description="Resource group")
    location: str = Field(default="", description="Azure region")
    primary_endpoint: str = Field(default="", description="Primary blob endpoint")
    provisioning_state: str = Field(default="", description="Provisioning state")
    resource_id: str = Field(default="", description="Full resource ID")
    error: str = Field(default="", description="Error message if failed")


class AzureDataCreateBlobContainerInput(BaseModel):
    """Input schema for azure_data_create_blob_container."""
    resource_group: str = Field(description="Resource group name")
    account_name: str = Field(description="Storage account name")
    container_name: str = Field(description="Container name")
    public_access: str = Field(
        default="None",
        description="Public access level: None, Container, Blob"
    )
    subscription_id: Optional[str] = Field(
        default=None,
        description="Subscription ID (uses default if not provided)"
    )


class AzureDataCreateBlobContainerOutput(BaseModel):
    """Output schema for azure_data_create_blob_container."""
    success: bool = Field(description="Whether creation succeeded")
    container_name: str = Field(default="", description="Container name")
    account_name: str = Field(default="", description="Storage account name")
    public_access: str = Field(default="", description="Public access level")
    resource_id: str = Field(default="", description="Full resource ID")
    error: str = Field(default="", description="Error message if failed")


# =============================================================================
# SQL Input/Output Schemas
# =============================================================================

class AzureDataCreateSqlServerInput(BaseModel):
    """Input schema for azure_data_create_sql_server."""
    resource_group: str = Field(description="Resource group name")
    name: str = Field(description="SQL server name (globally unique)")
    location: str = Field(description="Azure region (e.g., 'eastus')")
    admin_login: str = Field(description="Administrator login name")
    admin_password_secret_ref: str = Field(
        description="Secret reference for admin password (will be resolved from secrets store)"
    )
    version: str = Field(default="12.0", description="SQL Server version")
    tags: Optional[Dict[str, str]] = Field(
        default=None,
        description="Tags to apply"
    )
    subscription_id: Optional[str] = Field(
        default=None,
        description="Subscription ID (uses default if not provided)"
    )


class AzureDataCreateSqlServerOutput(BaseModel):
    """Output schema for azure_data_create_sql_server."""
    success: bool = Field(description="Whether creation succeeded")
    name: str = Field(default="", description="SQL server name")
    resource_group: str = Field(default="", description="Resource group")
    location: str = Field(default="", description="Azure region")
    fqdn: str = Field(default="", description="Fully qualified domain name")
    state: str = Field(default="", description="Server state")
    resource_id: str = Field(default="", description="Full resource ID")
    error: str = Field(default="", description="Error message if failed")


class AzureDataCreateSqlDatabaseInput(BaseModel):
    """Input schema for azure_data_create_sql_database."""
    resource_group: str = Field(description="Resource group name")
    server_name: str = Field(description="SQL server name")
    database_name: str = Field(description="Database name")
    sku_name: str = Field(
        default="Basic",
        description="SKU name: Basic, S0, S1, S2, P1, P2, etc."
    )
    max_size_bytes: Optional[int] = Field(
        default=None,
        description="Maximum size in bytes (defaults based on SKU)"
    )
    collation: str = Field(
        default="SQL_Latin1_General_CP1_CI_AS",
        description="Database collation"
    )
    subscription_id: Optional[str] = Field(
        default=None,
        description="Subscription ID (uses default if not provided)"
    )


class AzureDataCreateSqlDatabaseOutput(BaseModel):
    """Output schema for azure_data_create_sql_database."""
    success: bool = Field(description="Whether creation succeeded")
    database_name: str = Field(default="", description="Database name")
    server_name: str = Field(default="", description="SQL server name")
    sku_name: str = Field(default="", description="SKU name")
    status: str = Field(default="", description="Database status")
    resource_id: str = Field(default="", description="Full resource ID")
    error: str = Field(default="", description="Error message if failed")


class AzureDataSetSqlFirewallRuleInput(BaseModel):
    """Input schema for azure_data_set_sql_firewall_rule_allow_azure_services."""
    resource_group: str = Field(description="Resource group name")
    server_name: str = Field(description="SQL server name")
    subscription_id: Optional[str] = Field(
        default=None,
        description="Subscription ID (uses default if not provided)"
    )


class AzureDataSetSqlFirewallRuleOutput(BaseModel):
    """Output schema for azure_data_set_sql_firewall_rule_allow_azure_services."""
    success: bool = Field(description="Whether the rule was set")
    server_name: str = Field(default="", description="SQL server name")
    rule_name: str = Field(default="", description="Firewall rule name")
    message: str = Field(default="", description="Status message")
    error: str = Field(default="", description="Error message if failed")


# =============================================================================
# Helper Functions
# =============================================================================

def _resolve_secret(secret_ref: str) -> str:
    """Resolve a secret reference to its actual value.
    
    Attempts to load from Django secrets_app if available,
    otherwise falls back to environment variable.
    """
    import os
    
    # Try Django secrets store first
    try:
        from secrets_app.models import Secret
        
        # Parse secret_ref format: "service_type:key" or just "key"
        if ":" in secret_ref:
            service_type, key = secret_ref.split(":", 1)
        else:
            service_type = "azure"
            key = secret_ref
        
        try:
            secret = Secret.objects.get(service_type=service_type, key=key)
            return secret.get_value()
        except Secret.DoesNotExist:
            pass
    except ImportError:
        pass
    
    # Fall back to environment variable
    env_val = os.environ.get(secret_ref)
    if env_val:
        return env_val
    
    # Try uppercase version
    env_val = os.environ.get(secret_ref.upper())
    if env_val:
        return env_val
    
    raise ValueError(f"Could not resolve secret: {secret_ref}")


# =============================================================================
# Storage Tool Implementations
# =============================================================================

async def azure_data_create_storage_account(
    params: AzureDataCreateStorageAccountInput
) -> AzureDataCreateStorageAccountOutput:
    """Create an Azure Storage account.
    
    Args:
        params.resource_group: Resource group name
        params.name: Storage account name
        params.location: Azure region
        params.sku: Storage SKU
        params.kind: Storage kind
        params.access_tier: Access tier
        params.tags: Tags
        params.subscription_id: Subscription ID
        
    Returns:
        Created storage account details
    """
    logger.info(f"Creating storage account: {params.name}")
    
    try:
        from azure.mgmt.storage import StorageManagementClient
        from azure.mgmt.storage.models import (
            StorageAccountCreateParameters,
            Sku,
            Kind,
            AccessTier,
        )
        
        credential, subscription_id = get_credential_and_subscription(params.subscription_id)
        client = StorageManagementClient(credential, subscription_id)
        
        # Build parameters
        sku = Sku(name=params.sku)
        kind = getattr(Kind, params.kind.upper(), Kind.STORAGE_V2)
        
        create_params = StorageAccountCreateParameters(
            sku=sku,
            kind=kind,
            location=params.location,
            tags=params.tags,
        )
        
        if params.access_tier:
            create_params.access_tier = getattr(AccessTier, params.access_tier.upper(), AccessTier.HOT)
        
        # Create storage account
        poller = client.storage_accounts.begin_create(
            params.resource_group,
            params.name,
            create_params,
        )
        result = poller.result()
        
        # Get primary endpoint
        primary_endpoint = ""
        if result.primary_endpoints and result.primary_endpoints.blob:
            primary_endpoint = result.primary_endpoints.blob
        
        logger.info(f"Created storage account: {result.name}")
        
        return AzureDataCreateStorageAccountOutput(
            success=True,
            name=result.name,
            resource_group=params.resource_group,
            location=result.location,
            primary_endpoint=primary_endpoint,
            provisioning_state=result.provisioning_state or "",
            resource_id=result.id or "",
        )
        
    except AzureError as e:
        logger.error(f"Azure error creating storage account: {e}")
        return AzureDataCreateStorageAccountOutput(
            success=False,
            name=params.name,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create storage account: {e}")
        wrapped = wrap_azure_error(e)
        return AzureDataCreateStorageAccountOutput(
            success=False,
            name=params.name,
            error=wrapped.message,
        )


async def azure_data_create_blob_container(
    params: AzureDataCreateBlobContainerInput
) -> AzureDataCreateBlobContainerOutput:
    """Create a blob container in a storage account.
    
    Args:
        params.resource_group: Resource group name
        params.account_name: Storage account name
        params.container_name: Container name
        params.public_access: Public access level
        params.subscription_id: Subscription ID
        
    Returns:
        Created container details
    """
    logger.info(f"Creating blob container: {params.container_name} in {params.account_name}")
    
    try:
        from azure.mgmt.storage import StorageManagementClient
        from azure.mgmt.storage.models import BlobContainer, PublicAccess
        
        credential, subscription_id = get_credential_and_subscription(params.subscription_id)
        client = StorageManagementClient(credential, subscription_id)
        
        # Map public access level
        public_access_map = {
            "none": PublicAccess.NONE,
            "container": PublicAccess.CONTAINER,
            "blob": PublicAccess.BLOB,
        }
        public_access = public_access_map.get(
            params.public_access.lower(),
            PublicAccess.NONE
        )
        
        # Create container
        container = BlobContainer(public_access=public_access)
        
        result = client.blob_containers.create(
            params.resource_group,
            params.account_name,
            params.container_name,
            container,
        )
        
        logger.info(f"Created blob container: {result.name}")
        
        return AzureDataCreateBlobContainerOutput(
            success=True,
            container_name=result.name,
            account_name=params.account_name,
            public_access=result.public_access.value if result.public_access else "None",
            resource_id=result.id or "",
        )
        
    except AzureError as e:
        logger.error(f"Azure error creating blob container: {e}")
        return AzureDataCreateBlobContainerOutput(
            success=False,
            container_name=params.container_name,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create blob container: {e}")
        wrapped = wrap_azure_error(e)
        return AzureDataCreateBlobContainerOutput(
            success=False,
            container_name=params.container_name,
            error=wrapped.message,
        )


# =============================================================================
# SQL Tool Implementations
# =============================================================================

async def azure_data_create_sql_server(
    params: AzureDataCreateSqlServerInput
) -> AzureDataCreateSqlServerOutput:
    """Create an Azure SQL Server.
    
    Args:
        params.resource_group: Resource group name
        params.name: SQL server name
        params.location: Azure region
        params.admin_login: Admin login
        params.admin_password_secret_ref: Secret reference for password
        params.version: SQL version
        params.tags: Tags
        params.subscription_id: Subscription ID
        
    Returns:
        Created SQL server details
    """
    logger.info(f"Creating SQL server: {params.name}")
    
    try:
        from azure.mgmt.sql import SqlManagementClient
        from azure.mgmt.sql.models import Server
        
        # Resolve the password from secret store
        try:
            admin_password = _resolve_secret(params.admin_password_secret_ref)
        except ValueError as e:
            return AzureDataCreateSqlServerOutput(
                success=False,
                name=params.name,
                error=str(e),
            )
        
        credential, subscription_id = get_credential_and_subscription(params.subscription_id)
        client = SqlManagementClient(credential, subscription_id)
        
        # Build server parameters
        server = Server(
            location=params.location,
            administrator_login=params.admin_login,
            administrator_login_password=admin_password,
            version=params.version,
            tags=params.tags,
        )
        
        # Create server
        poller = client.servers.begin_create_or_update(
            params.resource_group,
            params.name,
            server,
        )
        result = poller.result()
        
        logger.info(f"Created SQL server: {result.name}")
        
        return AzureDataCreateSqlServerOutput(
            success=True,
            name=result.name,
            resource_group=params.resource_group,
            location=result.location,
            fqdn=result.fully_qualified_domain_name or "",
            state=result.state or "",
            resource_id=result.id or "",
        )
        
    except AzureError as e:
        logger.error(f"Azure error creating SQL server: {e}")
        return AzureDataCreateSqlServerOutput(
            success=False,
            name=params.name,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create SQL server: {e}")
        wrapped = wrap_azure_error(e)
        return AzureDataCreateSqlServerOutput(
            success=False,
            name=params.name,
            error=wrapped.message,
        )


async def azure_data_create_sql_database(
    params: AzureDataCreateSqlDatabaseInput
) -> AzureDataCreateSqlDatabaseOutput:
    """Create an Azure SQL Database.
    
    Args:
        params.resource_group: Resource group name
        params.server_name: SQL server name
        params.database_name: Database name
        params.sku_name: SKU name
        params.max_size_bytes: Maximum size
        params.collation: Database collation
        params.subscription_id: Subscription ID
        
    Returns:
        Created database details
    """
    logger.info(f"Creating SQL database: {params.database_name} on {params.server_name}")
    
    try:
        from azure.mgmt.sql import SqlManagementClient
        from azure.mgmt.sql.models import Database, Sku
        
        credential, subscription_id = get_credential_and_subscription(params.subscription_id)
        client = SqlManagementClient(credential, subscription_id)
        
        # Get server location
        server = client.servers.get(params.resource_group, params.server_name)
        
        # Build database parameters
        database = Database(
            location=server.location,
            sku=Sku(name=params.sku_name),
            collation=params.collation,
        )
        
        if params.max_size_bytes:
            database.max_size_bytes = params.max_size_bytes
        
        # Create database
        poller = client.databases.begin_create_or_update(
            params.resource_group,
            params.server_name,
            params.database_name,
            database,
        )
        result = poller.result()
        
        logger.info(f"Created SQL database: {result.name}")
        
        return AzureDataCreateSqlDatabaseOutput(
            success=True,
            database_name=result.name,
            server_name=params.server_name,
            sku_name=result.sku.name if result.sku else "",
            status=result.status or "",
            resource_id=result.id or "",
        )
        
    except AzureError as e:
        logger.error(f"Azure error creating SQL database: {e}")
        return AzureDataCreateSqlDatabaseOutput(
            success=False,
            database_name=params.database_name,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create SQL database: {e}")
        wrapped = wrap_azure_error(e)
        return AzureDataCreateSqlDatabaseOutput(
            success=False,
            database_name=params.database_name,
            error=wrapped.message,
        )


async def azure_data_set_sql_firewall_rule_allow_azure_services(
    params: AzureDataSetSqlFirewallRuleInput
) -> AzureDataSetSqlFirewallRuleOutput:
    """Set SQL Server firewall rule to allow Azure services.
    
    Creates a special firewall rule with start and end IP of 0.0.0.0
    which allows all Azure services to connect.
    
    Args:
        params.resource_group: Resource group name
        params.server_name: SQL server name
        params.subscription_id: Subscription ID
        
    Returns:
        Firewall rule creation result
    """
    logger.info(f"Setting Azure services firewall rule for: {params.server_name}")
    
    try:
        from azure.mgmt.sql import SqlManagementClient
        from azure.mgmt.sql.models import FirewallRule
        
        credential, subscription_id = get_credential_and_subscription(params.subscription_id)
        client = SqlManagementClient(credential, subscription_id)
        
        # Create the special "Allow Azure Services" rule
        # This uses 0.0.0.0 for both start and end IP
        rule_name = "AllowAllWindowsAzureIps"
        
        rule = FirewallRule(
            start_ip_address="0.0.0.0",
            end_ip_address="0.0.0.0",
        )
        
        result = client.firewall_rules.create_or_update(
            params.resource_group,
            params.server_name,
            rule_name,
            rule,
        )
        
        logger.info(f"Created firewall rule: {rule_name}")
        
        return AzureDataSetSqlFirewallRuleOutput(
            success=True,
            server_name=params.server_name,
            rule_name=result.name,
            message="Firewall rule created to allow Azure services",
        )
        
    except AzureError as e:
        logger.error(f"Azure error setting firewall rule: {e}")
        return AzureDataSetSqlFirewallRuleOutput(
            success=False,
            server_name=params.server_name,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to set firewall rule: {e}")
        wrapped = wrap_azure_error(e)
        return AzureDataSetSqlFirewallRuleOutput(
            success=False,
            server_name=params.server_name,
            error=wrapped.message,
        )

