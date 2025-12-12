"""Azure Deployments tools for ARM/Bicep deployments.

Provides MCP tools for:
- Deploying ARM templates to resource groups
- Deploying ARM templates at subscription scope
- Getting deployment status
- Listing deployments
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field

from .auth import (
    get_credential_and_subscription,
    AzureError,
    wrap_azure_error,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Input/Output Schemas
# =============================================================================

class AzureDeploymentsDeployToResourceGroupInput(BaseModel):
    """Input schema for azure_deployments_deploy_to_resource_group."""
    resource_group: str = Field(description="Target resource group name")
    deployment_name: str = Field(description="Unique name for this deployment")
    template: Dict[str, Any] = Field(description="ARM template as JSON/dict")
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Template parameters as JSON/dict"
    )
    mode: str = Field(
        default="Incremental",
        description="Deployment mode: 'Incremental' or 'Complete'"
    )
    subscription_id: Optional[str] = Field(
        default=None,
        description="Subscription ID (uses default if not provided)"
    )


class DeploymentOutput(BaseModel):
    """Output from a deployment."""
    key: str = Field(description="Output key name")
    value: Any = Field(description="Output value")
    type: str = Field(default="", description="Output type")


class AzureDeploymentsDeployToResourceGroupOutput(BaseModel):
    """Output schema for azure_deployments_deploy_to_resource_group."""
    success: bool = Field(description="Whether deployment was initiated successfully")
    deployment_name: str = Field(default="", description="Deployment name")
    resource_group: str = Field(default="", description="Target resource group")
    provisioning_state: str = Field(default="", description="Deployment provisioning state")
    timestamp: str = Field(default="", description="Deployment timestamp")
    correlation_id: str = Field(default="", description="Deployment correlation ID")
    outputs: List[DeploymentOutput] = Field(default_factory=list, description="Deployment outputs")
    error: str = Field(default="", description="Error message if failed")
    error_details: Dict[str, Any] = Field(default_factory=dict, description="Detailed error info")


class AzureDeploymentsDeployToSubscriptionInput(BaseModel):
    """Input schema for azure_deployments_deploy_to_subscription."""
    deployment_name: str = Field(description="Unique name for this deployment")
    location: str = Field(description="Azure region for deployment metadata")
    template: Dict[str, Any] = Field(description="ARM template as JSON/dict")
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Template parameters as JSON/dict"
    )
    mode: str = Field(
        default="Incremental",
        description="Deployment mode: 'Incremental' or 'Complete'"
    )
    subscription_id: Optional[str] = Field(
        default=None,
        description="Subscription ID (uses default if not provided)"
    )


class AzureDeploymentsDeployToSubscriptionOutput(BaseModel):
    """Output schema for azure_deployments_deploy_to_subscription."""
    success: bool = Field(description="Whether deployment was initiated successfully")
    deployment_name: str = Field(default="", description="Deployment name")
    location: str = Field(default="", description="Deployment location")
    provisioning_state: str = Field(default="", description="Deployment provisioning state")
    timestamp: str = Field(default="", description="Deployment timestamp")
    correlation_id: str = Field(default="", description="Deployment correlation ID")
    outputs: List[DeploymentOutput] = Field(default_factory=list, description="Deployment outputs")
    error: str = Field(default="", description="Error message if failed")
    error_details: Dict[str, Any] = Field(default_factory=dict, description="Detailed error info")


class AzureDeploymentsGetStatusInput(BaseModel):
    """Input schema for azure_deployments_get_status."""
    deployment_name: str = Field(description="Deployment name")
    scope: str = Field(
        default="resource_group",
        description="Deployment scope: 'resource_group' or 'subscription'"
    )
    resource_group: Optional[str] = Field(
        default=None,
        description="Resource group name (required if scope is 'resource_group')"
    )
    subscription_id: Optional[str] = Field(
        default=None,
        description="Subscription ID (uses default if not provided)"
    )


class DeploymentOperation(BaseModel):
    """Details of a deployment operation."""
    id: str = Field(description="Operation ID")
    operation_id: str = Field(default="", description="Operation ID")
    resource_type: str = Field(default="", description="Target resource type")
    resource_name: str = Field(default="", description="Target resource name")
    provisioning_state: str = Field(default="", description="Operation state")
    status_code: str = Field(default="", description="HTTP status code")
    status_message: str = Field(default="", description="Status message")


class AzureDeploymentsGetStatusOutput(BaseModel):
    """Output schema for azure_deployments_get_status."""
    success: bool = Field(description="Whether status was retrieved successfully")
    deployment_name: str = Field(default="", description="Deployment name")
    provisioning_state: str = Field(default="", description="Deployment state")
    timestamp: str = Field(default="", description="Deployment timestamp")
    duration: str = Field(default="", description="Deployment duration")
    correlation_id: str = Field(default="", description="Correlation ID")
    outputs: List[DeploymentOutput] = Field(default_factory=list, description="Deployment outputs")
    operations: List[DeploymentOperation] = Field(default_factory=list, description="Deployment operations")
    error: str = Field(default="", description="Error message if failed")
    error_details: Dict[str, Any] = Field(default_factory=dict, description="Detailed error info")


class AzureDeploymentsListInput(BaseModel):
    """Input schema for azure_deployments_list."""
    scope: str = Field(
        default="resource_group",
        description="Deployment scope: 'resource_group' or 'subscription'"
    )
    resource_group: Optional[str] = Field(
        default=None,
        description="Resource group name (required if scope is 'resource_group')"
    )
    subscription_id: Optional[str] = Field(
        default=None,
        description="Subscription ID (uses default if not provided)"
    )
    top: int = Field(default=25, description="Maximum number of deployments to return")


class DeploymentSummary(BaseModel):
    """Summary of a deployment."""
    name: str = Field(description="Deployment name")
    provisioning_state: str = Field(default="", description="Deployment state")
    timestamp: str = Field(default="", description="Deployment timestamp")
    duration: str = Field(default="", description="Deployment duration")
    mode: str = Field(default="", description="Deployment mode")


class AzureDeploymentsListOutput(BaseModel):
    """Output schema for azure_deployments_list."""
    success: bool = Field(description="Whether the request succeeded")
    deployments: List[DeploymentSummary] = Field(default_factory=list, description="List of deployments")
    count: int = Field(default=0, description="Number of deployments returned")
    scope: str = Field(default="", description="Scope searched")
    error: str = Field(default="", description="Error message if failed")


# =============================================================================
# Helper Functions
# =============================================================================

def _format_parameters_for_deployment(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Format parameters for ARM deployment.
    
    ARM expects parameters in format: {"paramName": {"value": "paramValue"}}
    This function handles both raw values and the ARM format.
    """
    formatted = {}
    for key, value in parameters.items():
        if isinstance(value, dict) and "value" in value:
            # Already in ARM format
            formatted[key] = value
        else:
            # Wrap in ARM format
            formatted[key] = {"value": value}
    return formatted


def _extract_outputs(outputs: Any) -> List[DeploymentOutput]:
    """Extract deployment outputs into our schema."""
    result = []
    if outputs:
        if isinstance(outputs, dict):
            for key, val in outputs.items():
                if isinstance(val, dict):
                    result.append(DeploymentOutput(
                        key=key,
                        value=val.get("value"),
                        type=val.get("type", ""),
                    ))
                else:
                    result.append(DeploymentOutput(key=key, value=val))
    return result


def _format_duration(start: Optional[datetime], end: Optional[datetime]) -> str:
    """Format deployment duration as human-readable string."""
    if not start or not end:
        return ""
    duration = end - start
    seconds = int(duration.total_seconds())
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    secs = seconds % 60
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m"


# =============================================================================
# Tool Implementations
# =============================================================================

async def azure_deployments_deploy_to_resource_group(
    params: AzureDeploymentsDeployToResourceGroupInput
) -> AzureDeploymentsDeployToResourceGroupOutput:
    """Deploy an ARM template to a resource group.
    
    Args:
        params.resource_group: Target resource group
        params.deployment_name: Unique deployment name
        params.template: ARM template as dict
        params.parameters: Template parameters
        params.mode: Deployment mode (Incremental or Complete)
        params.subscription_id: Subscription ID
        
    Returns:
        Deployment result with outputs
    """
    logger.info(f"Deploying to resource group: {params.resource_group}, deployment: {params.deployment_name}")
    
    try:
        from azure.mgmt.resource import ResourceManagementClient
        from azure.mgmt.resource.resources.models import (
            DeploymentMode,
            Deployment,
            DeploymentProperties,
        )
        
        credential, subscription_id = get_credential_and_subscription(params.subscription_id)
        client = ResourceManagementClient(credential, subscription_id)
        
        # Format parameters
        formatted_params = _format_parameters_for_deployment(params.parameters)
        
        # Determine mode
        mode = DeploymentMode.INCREMENTAL
        if params.mode.lower() == "complete":
            mode = DeploymentMode.COMPLETE
        
        # Create deployment
        deployment = Deployment(
            properties=DeploymentProperties(
                mode=mode,
                template=params.template,
                parameters=formatted_params,
            )
        )
        
        # Start deployment
        poller = client.deployments.begin_create_or_update(
            params.resource_group,
            params.deployment_name,
            deployment,
        )
        
        # Wait for result (with timeout awareness)
        result = poller.result()
        
        # Extract outputs
        outputs = _extract_outputs(result.properties.outputs if result.properties else None)
        
        logger.info(f"Deployment completed: {params.deployment_name}, state: {result.properties.provisioning_state}")
        
        return AzureDeploymentsDeployToResourceGroupOutput(
            success=True,
            deployment_name=result.name,
            resource_group=params.resource_group,
            provisioning_state=result.properties.provisioning_state if result.properties else "",
            timestamp=result.properties.timestamp.isoformat() if result.properties and result.properties.timestamp else "",
            correlation_id=result.properties.correlation_id if result.properties else "",
            outputs=outputs,
        )
        
    except AzureError as e:
        logger.error(f"Azure error during deployment: {e}")
        return AzureDeploymentsDeployToResourceGroupOutput(
            success=False,
            deployment_name=params.deployment_name,
            resource_group=params.resource_group,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to deploy: {e}")
        
        # Try to extract detailed error info
        error_details = {}
        if hasattr(e, 'error') and e.error:
            if hasattr(e.error, 'details'):
                error_details = {"details": str(e.error.details)}
        
        wrapped = wrap_azure_error(e)
        return AzureDeploymentsDeployToResourceGroupOutput(
            success=False,
            deployment_name=params.deployment_name,
            resource_group=params.resource_group,
            error=wrapped.message,
            error_details=error_details,
        )


async def azure_deployments_deploy_to_subscription(
    params: AzureDeploymentsDeployToSubscriptionInput
) -> AzureDeploymentsDeployToSubscriptionOutput:
    """Deploy an ARM template at subscription scope.
    
    Used for deploying resources like resource groups, policies, and
    management groups that exist at subscription level.
    
    Args:
        params.deployment_name: Unique deployment name
        params.location: Azure region for deployment metadata
        params.template: ARM template as dict
        params.parameters: Template parameters
        params.mode: Deployment mode (Incremental or Complete)
        params.subscription_id: Subscription ID
        
    Returns:
        Deployment result with outputs
    """
    logger.info(f"Deploying at subscription scope: {params.deployment_name}")
    
    try:
        from azure.mgmt.resource import ResourceManagementClient
        from azure.mgmt.resource.resources.models import (
            DeploymentMode,
            Deployment,
            DeploymentProperties,
        )
        
        credential, subscription_id = get_credential_and_subscription(params.subscription_id)
        client = ResourceManagementClient(credential, subscription_id)
        
        # Format parameters
        formatted_params = _format_parameters_for_deployment(params.parameters)
        
        # Determine mode
        mode = DeploymentMode.INCREMENTAL
        if params.mode.lower() == "complete":
            mode = DeploymentMode.COMPLETE
        
        # Create deployment
        deployment = Deployment(
            location=params.location,
            properties=DeploymentProperties(
                mode=mode,
                template=params.template,
                parameters=formatted_params,
            )
        )
        
        # Start subscription-level deployment
        poller = client.deployments.begin_create_or_update_at_subscription_scope(
            params.deployment_name,
            deployment,
        )
        
        # Wait for result
        result = poller.result()
        
        # Extract outputs
        outputs = _extract_outputs(result.properties.outputs if result.properties else None)
        
        logger.info(f"Subscription deployment completed: {params.deployment_name}")
        
        return AzureDeploymentsDeployToSubscriptionOutput(
            success=True,
            deployment_name=result.name,
            location=params.location,
            provisioning_state=result.properties.provisioning_state if result.properties else "",
            timestamp=result.properties.timestamp.isoformat() if result.properties and result.properties.timestamp else "",
            correlation_id=result.properties.correlation_id if result.properties else "",
            outputs=outputs,
        )
        
    except AzureError as e:
        logger.error(f"Azure error during subscription deployment: {e}")
        return AzureDeploymentsDeployToSubscriptionOutput(
            success=False,
            deployment_name=params.deployment_name,
            location=params.location,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to deploy at subscription scope: {e}")
        wrapped = wrap_azure_error(e)
        return AzureDeploymentsDeployToSubscriptionOutput(
            success=False,
            deployment_name=params.deployment_name,
            location=params.location,
            error=wrapped.message,
        )


async def azure_deployments_get_status(
    params: AzureDeploymentsGetStatusInput
) -> AzureDeploymentsGetStatusOutput:
    """Get the status of a deployment.
    
    Args:
        params.deployment_name: Deployment name
        params.scope: 'resource_group' or 'subscription'
        params.resource_group: Resource group (required for resource_group scope)
        params.subscription_id: Subscription ID
        
    Returns:
        Deployment status with operations
    """
    logger.info(f"Getting deployment status: {params.deployment_name}, scope: {params.scope}")
    
    if params.scope == "resource_group" and not params.resource_group:
        return AzureDeploymentsGetStatusOutput(
            success=False,
            deployment_name=params.deployment_name,
            error="resource_group is required when scope is 'resource_group'",
        )
    
    try:
        from azure.mgmt.resource import ResourceManagementClient
        
        credential, subscription_id = get_credential_and_subscription(params.subscription_id)
        client = ResourceManagementClient(credential, subscription_id)
        
        # Get deployment based on scope
        if params.scope == "subscription":
            deployment = client.deployments.get_at_subscription_scope(params.deployment_name)
        else:
            deployment = client.deployments.get(params.resource_group, params.deployment_name)
        
        props = deployment.properties
        
        # Calculate duration
        duration = ""
        if props and props.timestamp:
            if hasattr(props, 'duration') and props.duration:
                duration = props.duration
        
        # Extract outputs
        outputs = _extract_outputs(props.outputs if props else None)
        
        # Get operations (limited)
        operations = []
        try:
            if params.scope == "subscription":
                ops = client.deployment_operations.list_at_subscription_scope(params.deployment_name)
            else:
                ops = client.deployment_operations.list(params.resource_group, params.deployment_name)
            
            for op in list(ops)[:10]:  # Limit to 10 operations
                op_props = op.properties if op.properties else None
                operations.append(DeploymentOperation(
                    id=op.id or "",
                    operation_id=op.operation_id or "",
                    resource_type=op_props.target_resource.resource_type if op_props and op_props.target_resource else "",
                    resource_name=op_props.target_resource.resource_name if op_props and op_props.target_resource else "",
                    provisioning_state=op_props.provisioning_state if op_props else "",
                    status_code=op_props.status_code if op_props else "",
                    status_message=str(op_props.status_message)[:200] if op_props and op_props.status_message else "",
                ))
        except Exception as e:
            logger.warning(f"Could not get deployment operations: {e}")
        
        return AzureDeploymentsGetStatusOutput(
            success=True,
            deployment_name=deployment.name,
            provisioning_state=props.provisioning_state if props else "",
            timestamp=props.timestamp.isoformat() if props and props.timestamp else "",
            duration=duration,
            correlation_id=props.correlation_id if props else "",
            outputs=outputs,
            operations=operations,
        )
        
    except AzureError as e:
        logger.error(f"Azure error getting deployment status: {e}")
        return AzureDeploymentsGetStatusOutput(
            success=False,
            deployment_name=params.deployment_name,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to get deployment status: {e}")
        wrapped = wrap_azure_error(e)
        return AzureDeploymentsGetStatusOutput(
            success=False,
            deployment_name=params.deployment_name,
            error=wrapped.message,
        )


async def azure_deployments_list(
    params: AzureDeploymentsListInput
) -> AzureDeploymentsListOutput:
    """List deployments in a scope.
    
    Args:
        params.scope: 'resource_group' or 'subscription'
        params.resource_group: Resource group (required for resource_group scope)
        params.subscription_id: Subscription ID
        params.top: Maximum number to return
        
    Returns:
        List of deployments
    """
    logger.info(f"Listing deployments, scope: {params.scope}")
    
    if params.scope == "resource_group" and not params.resource_group:
        return AzureDeploymentsListOutput(
            success=False,
            scope=params.scope,
            error="resource_group is required when scope is 'resource_group'",
        )
    
    try:
        from azure.mgmt.resource import ResourceManagementClient
        
        credential, subscription_id = get_credential_and_subscription(params.subscription_id)
        client = ResourceManagementClient(credential, subscription_id)
        
        deployments = []
        
        if params.scope == "subscription":
            items = client.deployments.list_at_subscription_scope(top=params.top)
        else:
            items = client.deployments.list_by_resource_group(
                params.resource_group,
                top=params.top
            )
        
        for deployment in items:
            props = deployment.properties
            deployments.append(DeploymentSummary(
                name=deployment.name,
                provisioning_state=props.provisioning_state if props else "",
                timestamp=props.timestamp.isoformat() if props and props.timestamp else "",
                duration=props.duration if props and hasattr(props, 'duration') else "",
                mode=props.mode.value if props and props.mode else "",
            ))
            
            if len(deployments) >= params.top:
                break
        
        logger.info(f"Found {len(deployments)} deployments")
        
        return AzureDeploymentsListOutput(
            success=True,
            deployments=deployments,
            count=len(deployments),
            scope=params.scope,
        )
        
    except AzureError as e:
        logger.error(f"Azure error listing deployments: {e}")
        return AzureDeploymentsListOutput(
            success=False,
            scope=params.scope,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to list deployments: {e}")
        wrapped = wrap_azure_error(e)
        return AzureDeploymentsListOutput(
            success=False,
            scope=params.scope,
            error=wrapped.message,
        )

