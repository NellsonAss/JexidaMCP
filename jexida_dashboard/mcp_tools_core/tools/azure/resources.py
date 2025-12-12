"""Azure Resources tools for generic ARM resource operations.

Provides MCP tools for:
- Getting resources by ID
- Deleting resources
- Listing resources by type
- Searching resources with Resource Graph
"""

import logging
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field

from .auth import (
    get_credential_and_subscription,
    AzureError,
    AzureNotFoundError,
    wrap_azure_error,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Input/Output Schemas
# =============================================================================

class AzureResourcesGetResourceInput(BaseModel):
    """Input schema for azure_resources_get_resource."""
    resource_id: str = Field(
        description="Full Azure resource ID (e.g., /subscriptions/.../resourceGroups/.../providers/.../...)"
    )


class ResourceDetails(BaseModel):
    """Details of an Azure resource."""
    id: str = Field(description="Full resource ID")
    name: str = Field(description="Resource name")
    type: str = Field(description="Resource type (e.g., Microsoft.Web/sites)")
    location: str = Field(default="", description="Resource location")
    tags: Dict[str, str] = Field(default_factory=dict, description="Resource tags")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Resource properties")
    provisioning_state: str = Field(default="", description="Provisioning state")


class AzureResourcesGetResourceOutput(BaseModel):
    """Output schema for azure_resources_get_resource."""
    success: bool = Field(description="Whether the request succeeded")
    resource: Optional[ResourceDetails] = Field(default=None, description="Resource details")
    error: str = Field(default="", description="Error message if failed")


class AzureResourcesDeleteResourceInput(BaseModel):
    """Input schema for azure_resources_delete_resource."""
    resource_id: str = Field(
        description="Full Azure resource ID to delete"
    )
    force: bool = Field(
        default=False,
        description="Must be True to confirm deletion. This is a destructive operation."
    )


class AzureResourcesDeleteResourceOutput(BaseModel):
    """Output schema for azure_resources_delete_resource."""
    success: bool = Field(description="Whether the deletion was initiated")
    deleted: bool = Field(default=False, description="Whether deletion was initiated")
    resource_id: str = Field(default="", description="Resource ID")
    message: str = Field(default="", description="Status message")
    error: str = Field(default="", description="Error message if failed")


class AzureResourcesListByTypeInput(BaseModel):
    """Input schema for azure_resources_list_by_type."""
    resource_type: str = Field(
        description="Resource type to filter by (e.g., 'Microsoft.Web/sites', 'Microsoft.Storage/storageAccounts')"
    )
    subscription_id: Optional[str] = Field(
        default=None,
        description="Subscription ID (uses default if not provided)"
    )
    resource_group: Optional[str] = Field(
        default=None,
        description="Optional resource group to filter within"
    )


class ResourceSummary(BaseModel):
    """Summary of an Azure resource."""
    id: str = Field(description="Full resource ID")
    name: str = Field(description="Resource name")
    type: str = Field(description="Resource type")
    location: str = Field(default="", description="Resource location")
    resource_group: str = Field(default="", description="Resource group name")


class AzureResourcesListByTypeOutput(BaseModel):
    """Output schema for azure_resources_list_by_type."""
    success: bool = Field(description="Whether the request succeeded")
    resources: List[ResourceSummary] = Field(default_factory=list, description="List of resources")
    count: int = Field(default=0, description="Number of resources found")
    resource_type: str = Field(default="", description="Resource type searched")
    error: str = Field(default="", description="Error message if failed")


class AzureResourcesSearchInput(BaseModel):
    """Input schema for azure_resources_search."""
    query: str = Field(
        description="Azure Resource Graph query (Kusto-like syntax)"
    )
    subscription_id: Optional[str] = Field(
        default=None,
        description="Subscription ID to search (uses default if not provided)"
    )
    top: int = Field(
        default=100,
        description="Maximum number of results to return"
    )


class AzureResourcesSearchOutput(BaseModel):
    """Output schema for azure_resources_search."""
    success: bool = Field(description="Whether the search succeeded")
    resources: List[Dict[str, Any]] = Field(default_factory=list, description="Search results")
    count: int = Field(default=0, description="Number of results")
    total_records: int = Field(default=0, description="Total matching records")
    query: str = Field(default="", description="Query executed")
    error: str = Field(default="", description="Error message if failed")


# =============================================================================
# Tool Implementations
# =============================================================================

def _parse_resource_id(resource_id: str) -> Dict[str, str]:
    """Parse an Azure resource ID into its components.
    
    Args:
        resource_id: Full Azure resource ID
        
    Returns:
        Dictionary with subscription, resource_group, provider, type, name
    """
    parts = resource_id.strip("/").split("/")
    result = {}
    
    for i, part in enumerate(parts):
        if part.lower() == "subscriptions" and i + 1 < len(parts):
            result["subscription_id"] = parts[i + 1]
        elif part.lower() == "resourcegroups" and i + 1 < len(parts):
            result["resource_group"] = parts[i + 1]
        elif part.lower() == "providers" and i + 1 < len(parts):
            result["provider"] = parts[i + 1]
            if i + 2 < len(parts):
                result["type"] = parts[i + 2]
            if i + 3 < len(parts):
                result["name"] = parts[i + 3]
    
    return result


async def azure_resources_get_resource(
    params: AzureResourcesGetResourceInput
) -> AzureResourcesGetResourceOutput:
    """Get details of a specific Azure resource by ID.
    
    Args:
        params.resource_id: Full Azure resource ID
        
    Returns:
        Resource details including properties
    """
    logger.info(f"Getting resource: {params.resource_id}")
    
    try:
        from azure.mgmt.resource import ResourceManagementClient
        from .auth import get_azure_credential
        
        # Parse resource ID to get subscription
        parsed = _parse_resource_id(params.resource_id)
        subscription_id = parsed.get("subscription_id")
        
        if not subscription_id:
            return AzureResourcesGetResourceOutput(
                success=False,
                error="Could not parse subscription ID from resource ID",
            )
        
        credential = get_azure_credential()
        client = ResourceManagementClient(credential, subscription_id)
        
        # Get the resource
        resource = client.resources.get_by_id(
            params.resource_id,
            api_version="2021-04-01"  # Generic API version
        )
        
        # Extract properties safely
        properties = {}
        if hasattr(resource, 'properties') and resource.properties:
            if isinstance(resource.properties, dict):
                properties = resource.properties
            elif hasattr(resource.properties, '__dict__'):
                properties = {k: v for k, v in resource.properties.__dict__.items() if not k.startswith('_')}
        
        provisioning_state = properties.get('provisioningState', '')
        
        details = ResourceDetails(
            id=resource.id,
            name=resource.name,
            type=resource.type,
            location=resource.location or "",
            tags=resource.tags or {},
            properties=properties,
            provisioning_state=provisioning_state,
        )
        
        logger.info(f"Retrieved resource: {resource.name}")
        
        return AzureResourcesGetResourceOutput(
            success=True,
            resource=details,
        )
        
    except AzureError as e:
        logger.error(f"Azure error getting resource: {e}")
        return AzureResourcesGetResourceOutput(
            success=False,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to get resource: {e}")
        error_str = str(e).lower()
        if "not found" in error_str or "404" in error_str:
            return AzureResourcesGetResourceOutput(
                success=False,
                error=f"Resource not found: {params.resource_id}",
            )
        wrapped = wrap_azure_error(e)
        return AzureResourcesGetResourceOutput(
            success=False,
            error=wrapped.message,
        )


async def azure_resources_delete_resource(
    params: AzureResourcesDeleteResourceInput
) -> AzureResourcesDeleteResourceOutput:
    """Delete an Azure resource by ID.
    
    WARNING: This is a destructive operation. The force parameter must be True.
    
    Args:
        params.resource_id: Full Azure resource ID
        params.force: Must be True to confirm deletion
        
    Returns:
        Deletion status
    """
    logger.info(f"Delete resource request: {params.resource_id}, force={params.force}")
    
    if not params.force:
        return AzureResourcesDeleteResourceOutput(
            success=False,
            deleted=False,
            resource_id=params.resource_id,
            message="Deletion requires force=True. This will permanently delete the resource.",
            error="force parameter must be True to confirm deletion",
        )
    
    try:
        from azure.mgmt.resource import ResourceManagementClient
        from .auth import get_azure_credential
        
        # Parse resource ID to get subscription
        parsed = _parse_resource_id(params.resource_id)
        subscription_id = parsed.get("subscription_id")
        
        if not subscription_id:
            return AzureResourcesDeleteResourceOutput(
                success=False,
                resource_id=params.resource_id,
                error="Could not parse subscription ID from resource ID",
            )
        
        credential = get_azure_credential()
        client = ResourceManagementClient(credential, subscription_id)
        
        # Start async delete operation
        poller = client.resources.begin_delete_by_id(
            params.resource_id,
            api_version="2021-04-01"
        )
        
        logger.info(f"Initiated deletion of resource: {params.resource_id}")
        
        return AzureResourcesDeleteResourceOutput(
            success=True,
            deleted=True,
            resource_id=params.resource_id,
            message="Deletion initiated. This may take several minutes to complete.",
        )
        
    except AzureError as e:
        logger.error(f"Azure error deleting resource: {e}")
        return AzureResourcesDeleteResourceOutput(
            success=False,
            resource_id=params.resource_id,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to delete resource: {e}")
        wrapped = wrap_azure_error(e)
        return AzureResourcesDeleteResourceOutput(
            success=False,
            resource_id=params.resource_id,
            error=wrapped.message,
        )


async def azure_resources_list_by_type(
    params: AzureResourcesListByTypeInput
) -> AzureResourcesListByTypeOutput:
    """List Azure resources of a specific type.
    
    Args:
        params.resource_type: Resource type (e.g., 'Microsoft.Web/sites')
        params.subscription_id: Subscription ID (uses default if not provided)
        params.resource_group: Optional resource group filter
        
    Returns:
        List of matching resources
    """
    logger.info(f"Listing resources of type: {params.resource_type}")
    
    try:
        from azure.mgmt.resource import ResourceManagementClient
        
        credential, subscription_id = get_credential_and_subscription(params.subscription_id)
        client = ResourceManagementClient(credential, subscription_id)
        
        # Build filter
        filter_str = f"resourceType eq '{params.resource_type}'"
        
        resources = []
        
        if params.resource_group:
            # List within specific resource group
            for resource in client.resources.list_by_resource_group(
                params.resource_group,
                filter=filter_str
            ):
                resources.append(ResourceSummary(
                    id=resource.id,
                    name=resource.name,
                    type=resource.type,
                    location=resource.location or "",
                    resource_group=params.resource_group,
                ))
        else:
            # List across subscription
            for resource in client.resources.list(filter=filter_str):
                # Extract resource group from ID
                parsed = _parse_resource_id(resource.id)
                resources.append(ResourceSummary(
                    id=resource.id,
                    name=resource.name,
                    type=resource.type,
                    location=resource.location or "",
                    resource_group=parsed.get("resource_group", ""),
                ))
        
        logger.info(f"Found {len(resources)} resources of type {params.resource_type}")
        
        return AzureResourcesListByTypeOutput(
            success=True,
            resources=resources,
            count=len(resources),
            resource_type=params.resource_type,
        )
        
    except AzureError as e:
        logger.error(f"Azure error listing resources: {e}")
        return AzureResourcesListByTypeOutput(
            success=False,
            resource_type=params.resource_type,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to list resources: {e}")
        wrapped = wrap_azure_error(e)
        return AzureResourcesListByTypeOutput(
            success=False,
            resource_type=params.resource_type,
            error=wrapped.message,
        )


async def azure_resources_search(
    params: AzureResourcesSearchInput
) -> AzureResourcesSearchOutput:
    """Search Azure resources using Resource Graph.
    
    Uses Azure Resource Graph for efficient cross-subscription queries.
    
    Example queries:
    - "Resources | where type == 'microsoft.web/sites'"
    - "Resources | where name contains 'prod'"
    - "Resources | where tags.Environment == 'Production'"
    
    Args:
        params.query: Azure Resource Graph query
        params.subscription_id: Subscription to search
        params.top: Maximum results to return
        
    Returns:
        Search results
    """
    logger.info(f"Searching resources with query: {params.query[:100]}...")
    
    try:
        from azure.mgmt.resourcegraph import ResourceGraphClient
        from azure.mgmt.resourcegraph.models import QueryRequest
        
        credential, subscription_id = get_credential_and_subscription(params.subscription_id)
        client = ResourceGraphClient(credential)
        
        # Build query request
        request = QueryRequest(
            subscriptions=[subscription_id],
            query=params.query,
            options={"$top": params.top}
        )
        
        # Execute query
        result = client.resources(request)
        
        # Convert results to list of dicts
        resources = []
        if result.data:
            for row in result.data:
                if isinstance(row, dict):
                    resources.append(row)
                else:
                    # Handle non-dict results
                    resources.append({"data": str(row)})
        
        total_records = result.total_records if hasattr(result, 'total_records') else len(resources)
        
        logger.info(f"Search returned {len(resources)} results")
        
        return AzureResourcesSearchOutput(
            success=True,
            resources=resources,
            count=len(resources),
            total_records=total_records,
            query=params.query,
        )
        
    except ImportError:
        logger.error("azure-mgmt-resourcegraph package not installed")
        return AzureResourcesSearchOutput(
            success=False,
            query=params.query,
            error="Resource Graph SDK not installed. Install with: pip install azure-mgmt-resourcegraph",
        )
    except AzureError as e:
        logger.error(f"Azure error searching resources: {e}")
        return AzureResourcesSearchOutput(
            success=False,
            query=params.query,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to search resources: {e}")
        wrapped = wrap_azure_error(e)
        return AzureResourcesSearchOutput(
            success=False,
            query=params.query,
            error=wrapped.message,
        )

