"""Azure Core tools for subscriptions, resource groups, and locations.

Provides MCP tools for:
- Getting connection info
- Listing subscriptions
- Managing resource groups
- Listing locations
"""

import logging
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field

from .auth import (
    get_credential_and_subscription,
    get_azure_config,
    get_subscription_id,
    get_tenant_id,
    validate_azure_config,
    AzureError,
    AzureConfigError,
    wrap_azure_error,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Input/Output Schemas
# =============================================================================

class AzureCoreGetConnectionInfoInput(BaseModel):
    """Input schema for azure_core_get_connection_info."""
    pass  # No parameters needed


class AzureCoreGetConnectionInfoOutput(BaseModel):
    """Output schema for azure_core_get_connection_info."""
    success: bool = Field(description="Whether the check succeeded")
    subscription_id: str = Field(default="", description="Active subscription ID")
    tenant_id: str = Field(default="", description="Azure tenant ID")
    client_id: str = Field(default="", description="Service principal client ID (if configured)")
    auth_method: str = Field(default="", description="Authentication method being used")
    is_valid: bool = Field(default=False, description="Whether configuration is valid")
    message: str = Field(default="", description="Configuration status message")
    error: str = Field(default="", description="Error message if failed")


class AzureCoreListSubscriptionsInput(BaseModel):
    """Input schema for azure_core_list_subscriptions."""
    pass  # No parameters needed


class SubscriptionInfo(BaseModel):
    """Information about an Azure subscription."""
    subscription_id: str = Field(description="Subscription ID")
    display_name: str = Field(description="Subscription display name")
    state: str = Field(description="Subscription state (Enabled, Disabled, etc.)")
    tenant_id: str = Field(default="", description="Tenant ID")


class AzureCoreListSubscriptionsOutput(BaseModel):
    """Output schema for azure_core_list_subscriptions."""
    success: bool = Field(description="Whether the request succeeded")
    subscriptions: List[SubscriptionInfo] = Field(default_factory=list, description="List of subscriptions")
    count: int = Field(default=0, description="Number of subscriptions")
    error: str = Field(default="", description="Error message if failed")


class AzureCoreListLocationsInput(BaseModel):
    """Input schema for azure_core_list_locations."""
    subscription_id: Optional[str] = Field(
        default=None,
        description="Subscription ID (uses default if not provided)"
    )


class LocationInfo(BaseModel):
    """Information about an Azure location."""
    name: str = Field(description="Location name (e.g., 'eastus')")
    display_name: str = Field(description="Display name (e.g., 'East US')")
    regional_display_name: str = Field(default="", description="Regional display name")


class AzureCoreListLocationsOutput(BaseModel):
    """Output schema for azure_core_list_locations."""
    success: bool = Field(description="Whether the request succeeded")
    locations: List[LocationInfo] = Field(default_factory=list, description="List of locations")
    count: int = Field(default=0, description="Number of locations")
    error: str = Field(default="", description="Error message if failed")


class AzureCoreListResourceGroupsInput(BaseModel):
    """Input schema for azure_core_list_resource_groups."""
    subscription_id: Optional[str] = Field(
        default=None,
        description="Subscription ID (uses default if not provided)"
    )


class ResourceGroupInfo(BaseModel):
    """Information about a resource group."""
    name: str = Field(description="Resource group name")
    location: str = Field(description="Azure region")
    tags: Dict[str, str] = Field(default_factory=dict, description="Resource group tags")
    provisioning_state: str = Field(default="", description="Provisioning state")


class AzureCoreListResourceGroupsOutput(BaseModel):
    """Output schema for azure_core_list_resource_groups."""
    success: bool = Field(description="Whether the request succeeded")
    resource_groups: List[ResourceGroupInfo] = Field(default_factory=list, description="List of resource groups")
    count: int = Field(default=0, description="Number of resource groups")
    subscription_id: str = Field(default="", description="Subscription ID used")
    error: str = Field(default="", description="Error message if failed")


class AzureCoreCreateResourceGroupInput(BaseModel):
    """Input schema for azure_core_create_resource_group."""
    name: str = Field(description="Resource group name")
    location: str = Field(description="Azure region (e.g., 'eastus')")
    tags: Optional[Dict[str, str]] = Field(
        default=None,
        description="Tags to apply to the resource group"
    )
    subscription_id: Optional[str] = Field(
        default=None,
        description="Subscription ID (uses default if not provided)"
    )


class AzureCoreCreateResourceGroupOutput(BaseModel):
    """Output schema for azure_core_create_resource_group."""
    success: bool = Field(description="Whether the creation succeeded")
    created: bool = Field(default=False, description="True if new RG was created, False if it already existed")
    name: str = Field(default="", description="Resource group name")
    location: str = Field(default="", description="Resource group location")
    provisioning_state: str = Field(default="", description="Provisioning state")
    error: str = Field(default="", description="Error message if failed")


class AzureCoreDeleteResourceGroupInput(BaseModel):
    """Input schema for azure_core_delete_resource_group."""
    name: str = Field(description="Resource group name to delete")
    force: bool = Field(
        default=False,
        description="Must be True to confirm deletion. This is a destructive operation."
    )
    subscription_id: Optional[str] = Field(
        default=None,
        description="Subscription ID (uses default if not provided)"
    )


class AzureCoreDeleteResourceGroupOutput(BaseModel):
    """Output schema for azure_core_delete_resource_group."""
    success: bool = Field(description="Whether the deletion was initiated")
    deleted: bool = Field(default=False, description="Whether deletion was initiated")
    name: str = Field(default="", description="Resource group name")
    message: str = Field(default="", description="Status message")
    error: str = Field(default="", description="Error message if failed")


# =============================================================================
# Tool Implementations
# =============================================================================

async def azure_core_get_connection_info(
    params: AzureCoreGetConnectionInfoInput
) -> AzureCoreGetConnectionInfoOutput:
    """Get current Azure connection information.
    
    Returns the active subscription ID, tenant ID, and authentication status.
    Does not include secrets.
    
    Returns:
        Connection info with subscription and auth details
    """
    logger.info("Getting Azure connection info")
    
    try:
        config = get_azure_config()
        is_valid, message = validate_azure_config()
        
        # Determine auth method
        if config.get("has_client_secret"):
            auth_method = "ServicePrincipal"
        else:
            auth_method = "DefaultAzureCredential"
        
        return AzureCoreGetConnectionInfoOutput(
            success=True,
            subscription_id=config.get("subscription_id") or "",
            tenant_id=config.get("tenant_id") or "",
            client_id=config.get("client_id") or "",
            auth_method=auth_method,
            is_valid=is_valid,
            message=message,
        )
        
    except Exception as e:
        logger.error(f"Failed to get connection info: {e}")
        return AzureCoreGetConnectionInfoOutput(
            success=False,
            error=str(e),
        )


async def azure_core_list_subscriptions(
    params: AzureCoreListSubscriptionsInput
) -> AzureCoreListSubscriptionsOutput:
    """List all Azure subscriptions accessible with current credentials.
    
    Returns:
        List of subscriptions with IDs and names
    """
    logger.info("Listing Azure subscriptions")
    
    try:
        from azure.mgmt.resource import SubscriptionClient
        from .auth import get_azure_credential
        
        credential = get_azure_credential()
        client = SubscriptionClient(credential)
        
        subscriptions = []
        for sub in client.subscriptions.list():
            subscriptions.append(SubscriptionInfo(
                subscription_id=sub.subscription_id,
                display_name=sub.display_name,
                state=sub.state.value if sub.state else "Unknown",
                tenant_id=sub.tenant_id or "",
            ))
        
        logger.info(f"Found {len(subscriptions)} subscriptions")
        
        return AzureCoreListSubscriptionsOutput(
            success=True,
            subscriptions=subscriptions,
            count=len(subscriptions),
        )
        
    except AzureError as e:
        logger.error(f"Azure error listing subscriptions: {e}")
        return AzureCoreListSubscriptionsOutput(
            success=False,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to list subscriptions: {e}")
        wrapped = wrap_azure_error(e)
        return AzureCoreListSubscriptionsOutput(
            success=False,
            error=wrapped.message,
        )


async def azure_core_list_locations(
    params: AzureCoreListLocationsInput
) -> AzureCoreListLocationsOutput:
    """List available Azure locations/regions.
    
    Args:
        params.subscription_id: Subscription ID (uses default if not provided)
        
    Returns:
        List of locations with names and display names
    """
    logger.info(f"Listing Azure locations for subscription: {params.subscription_id or 'default'}")
    
    try:
        from azure.mgmt.resource import SubscriptionClient
        
        credential, subscription_id = get_credential_and_subscription(params.subscription_id)
        client = SubscriptionClient(credential)
        
        locations = []
        for loc in client.subscriptions.list_locations(subscription_id):
            locations.append(LocationInfo(
                name=loc.name,
                display_name=loc.display_name or loc.name,
                regional_display_name=loc.regional_display_name or "",
            ))
        
        logger.info(f"Found {len(locations)} locations")
        
        return AzureCoreListLocationsOutput(
            success=True,
            locations=locations,
            count=len(locations),
        )
        
    except AzureError as e:
        logger.error(f"Azure error listing locations: {e}")
        return AzureCoreListLocationsOutput(
            success=False,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to list locations: {e}")
        wrapped = wrap_azure_error(e)
        return AzureCoreListLocationsOutput(
            success=False,
            error=wrapped.message,
        )


async def azure_core_list_resource_groups(
    params: AzureCoreListResourceGroupsInput
) -> AzureCoreListResourceGroupsOutput:
    """List resource groups in a subscription.
    
    Args:
        params.subscription_id: Subscription ID (uses default if not provided)
        
    Returns:
        List of resource groups with details
    """
    logger.info(f"Listing resource groups for subscription: {params.subscription_id or 'default'}")
    
    try:
        from azure.mgmt.resource import ResourceManagementClient
        
        credential, subscription_id = get_credential_and_subscription(params.subscription_id)
        client = ResourceManagementClient(credential, subscription_id)
        
        resource_groups = []
        for rg in client.resource_groups.list():
            resource_groups.append(ResourceGroupInfo(
                name=rg.name,
                location=rg.location,
                tags=rg.tags or {},
                provisioning_state=rg.properties.provisioning_state if rg.properties else "",
            ))
        
        logger.info(f"Found {len(resource_groups)} resource groups")
        
        return AzureCoreListResourceGroupsOutput(
            success=True,
            resource_groups=resource_groups,
            count=len(resource_groups),
            subscription_id=subscription_id,
        )
        
    except AzureError as e:
        logger.error(f"Azure error listing resource groups: {e}")
        return AzureCoreListResourceGroupsOutput(
            success=False,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to list resource groups: {e}")
        wrapped = wrap_azure_error(e)
        return AzureCoreListResourceGroupsOutput(
            success=False,
            error=wrapped.message,
        )


async def azure_core_create_resource_group(
    params: AzureCoreCreateResourceGroupInput
) -> AzureCoreCreateResourceGroupOutput:
    """Create a new resource group.
    
    Args:
        params.name: Resource group name
        params.location: Azure region
        params.tags: Optional tags
        params.subscription_id: Subscription ID (uses default if not provided)
        
    Returns:
        Created resource group details
    """
    logger.info(f"Creating resource group: {params.name} in {params.location}")
    
    try:
        from azure.mgmt.resource import ResourceManagementClient
        from azure.mgmt.resource.resources.models import ResourceGroup
        
        credential, subscription_id = get_credential_and_subscription(params.subscription_id)
        client = ResourceManagementClient(credential, subscription_id)
        
        # Check if RG already exists
        try:
            existing = client.resource_groups.get(params.name)
            logger.info(f"Resource group {params.name} already exists")
            return AzureCoreCreateResourceGroupOutput(
                success=True,
                created=False,
                name=existing.name,
                location=existing.location,
                provisioning_state=existing.properties.provisioning_state if existing.properties else "",
            )
        except Exception:
            # RG doesn't exist, create it
            pass
        
        # Create resource group
        rg_params = ResourceGroup(
            location=params.location,
            tags=params.tags,
        )
        
        result = client.resource_groups.create_or_update(params.name, rg_params)
        
        logger.info(f"Created resource group: {result.name}")
        
        return AzureCoreCreateResourceGroupOutput(
            success=True,
            created=True,
            name=result.name,
            location=result.location,
            provisioning_state=result.properties.provisioning_state if result.properties else "",
        )
        
    except AzureError as e:
        logger.error(f"Azure error creating resource group: {e}")
        return AzureCoreCreateResourceGroupOutput(
            success=False,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create resource group: {e}")
        wrapped = wrap_azure_error(e)
        return AzureCoreCreateResourceGroupOutput(
            success=False,
            error=wrapped.message,
        )


async def azure_core_delete_resource_group(
    params: AzureCoreDeleteResourceGroupInput
) -> AzureCoreDeleteResourceGroupOutput:
    """Delete a resource group.
    
    WARNING: This is a destructive operation that deletes all resources
    in the resource group. The force parameter must be True.
    
    Args:
        params.name: Resource group name to delete
        params.force: Must be True to confirm deletion
        params.subscription_id: Subscription ID (uses default if not provided)
        
    Returns:
        Deletion status
    """
    logger.info(f"Delete resource group request: {params.name}, force={params.force}")
    
    if not params.force:
        return AzureCoreDeleteResourceGroupOutput(
            success=False,
            deleted=False,
            name=params.name,
            message="Deletion requires force=True. This will delete all resources in the resource group.",
            error="force parameter must be True to confirm deletion",
        )
    
    try:
        from azure.mgmt.resource import ResourceManagementClient
        
        credential, subscription_id = get_credential_and_subscription(params.subscription_id)
        client = ResourceManagementClient(credential, subscription_id)
        
        # Start async delete operation
        poller = client.resource_groups.begin_delete(params.name)
        
        logger.info(f"Initiated deletion of resource group: {params.name}")
        
        return AzureCoreDeleteResourceGroupOutput(
            success=True,
            deleted=True,
            name=params.name,
            message=f"Deletion initiated for resource group '{params.name}'. This may take several minutes to complete.",
        )
        
    except AzureError as e:
        logger.error(f"Azure error deleting resource group: {e}")
        return AzureCoreDeleteResourceGroupOutput(
            success=False,
            name=params.name,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to delete resource group: {e}")
        wrapped = wrap_azure_error(e)
        return AzureCoreDeleteResourceGroupOutput(
            success=False,
            name=params.name,
            error=wrapped.message,
        )

