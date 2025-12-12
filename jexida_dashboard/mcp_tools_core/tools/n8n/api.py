"""n8n REST API tools for workflow management.

Provides MCP tools for:
- Health checks
- Listing and viewing workflows
- Running workflows
- Getting execution details
- Triggering webhooks
"""

import logging
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field

from .client import N8nClient

logger = logging.getLogger(__name__)


# =============================================================================
# Health Check Tool
# =============================================================================

class N8nHealthCheckInput(BaseModel):
    """Input schema for n8n_health_check."""
    pass  # No parameters needed


class N8nHealthCheckOutput(BaseModel):
    """Output schema for n8n_health_check."""
    
    success: bool = Field(description="Whether the check completed")
    healthy: bool = Field(default=False, description="Whether n8n is healthy")
    base_url: str = Field(default="", description="n8n base URL checked")
    status_code: int = Field(default=0, description="HTTP status code")
    error: str = Field(default="", description="Error message if failed")


async def n8n_health_check(params: N8nHealthCheckInput) -> N8nHealthCheckOutput:
    """Check n8n instance health status.
    
    Verifies the n8n server is running and responsive.
    
    Returns:
        Health check result
    """
    logger.info("Checking n8n health")
    
    try:
        with N8nClient() as client:
            result = client.health_check()
            
            return N8nHealthCheckOutput(
                success=True,
                healthy=result.get("healthy", False),
                base_url=client.config.base_url,
                status_code=result.get("status_code", 0),
                error=result.get("error", ""),
            )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return N8nHealthCheckOutput(
            success=False,
            error=str(e),
        )


# =============================================================================
# List Workflows Tool
# =============================================================================

class N8nListWorkflowsInput(BaseModel):
    """Input schema for n8n_list_workflows."""
    
    active_only: bool = Field(
        default=False,
        description="Only return active workflows"
    )


class WorkflowSummary(BaseModel):
    """Summary of a workflow."""
    
    id: str = Field(description="Workflow ID")
    name: str = Field(description="Workflow name")
    active: bool = Field(description="Whether workflow is active")
    created_at: str = Field(default="", description="Creation timestamp")
    updated_at: str = Field(default="", description="Last update timestamp")


class N8nListWorkflowsOutput(BaseModel):
    """Output schema for n8n_list_workflows."""
    
    success: bool = Field(description="Whether the request succeeded")
    workflows: List[WorkflowSummary] = Field(default_factory=list, description="List of workflows")
    count: int = Field(default=0, description="Number of workflows")
    error: str = Field(default="", description="Error message if failed")


async def n8n_list_workflows(params: N8nListWorkflowsInput) -> N8nListWorkflowsOutput:
    """List all n8n workflows.
    
    Retrieves the list of workflows from the n8n instance.
    
    Args:
        params: Filter options
        
    Returns:
        List of workflows
    """
    logger.info(f"Listing n8n workflows (active_only={params.active_only})")
    
    try:
        with N8nClient() as client:
            result = client.list_workflows()
            
            if not result.get("success"):
                return N8nListWorkflowsOutput(
                    success=False,
                    error=result.get("error", "Unknown error"),
                )
            
            workflows = []
            for wf in result.get("workflows", []):
                # Filter by active if requested
                if params.active_only and not wf.get("active", False):
                    continue
                
                workflows.append(WorkflowSummary(
                    id=str(wf.get("id", "")),
                    name=wf.get("name", "Unnamed"),
                    active=wf.get("active", False),
                    created_at=wf.get("createdAt", ""),
                    updated_at=wf.get("updatedAt", ""),
                ))
            
            return N8nListWorkflowsOutput(
                success=True,
                workflows=workflows,
                count=len(workflows),
            )
    except Exception as e:
        logger.error(f"Failed to list workflows: {e}")
        return N8nListWorkflowsOutput(
            success=False,
            error=str(e),
        )


# =============================================================================
# Get Workflow Tool
# =============================================================================

class N8nGetWorkflowInput(BaseModel):
    """Input schema for n8n_get_workflow."""
    
    workflow_id: str = Field(description="ID of the workflow to retrieve")


class N8nGetWorkflowOutput(BaseModel):
    """Output schema for n8n_get_workflow."""
    
    success: bool = Field(description="Whether the request succeeded")
    workflow: Dict[str, Any] = Field(default_factory=dict, description="Workflow details")
    error: str = Field(default="", description="Error message if failed")


async def n8n_get_workflow(params: N8nGetWorkflowInput) -> N8nGetWorkflowOutput:
    """Get details of a specific workflow.
    
    Retrieves the full workflow definition including nodes and connections.
    
    Args:
        params: Workflow ID
        
    Returns:
        Workflow details
    """
    logger.info(f"Getting n8n workflow: {params.workflow_id}")
    
    try:
        with N8nClient() as client:
            result = client.get_workflow(params.workflow_id)
            
            if not result.get("success"):
                return N8nGetWorkflowOutput(
                    success=False,
                    error=result.get("error", "Unknown error"),
                )
            
            return N8nGetWorkflowOutput(
                success=True,
                workflow=result.get("workflow", {}),
            )
    except Exception as e:
        logger.error(f"Failed to get workflow: {e}")
        return N8nGetWorkflowOutput(
            success=False,
            error=str(e),
        )


# =============================================================================
# Run Workflow Tool
# =============================================================================

class N8nRunWorkflowInput(BaseModel):
    """Input schema for n8n_run_workflow."""
    
    workflow_id: str = Field(description="ID of the workflow to run")
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional input data for the workflow"
    )


class N8nRunWorkflowOutput(BaseModel):
    """Output schema for n8n_run_workflow."""
    
    success: bool = Field(description="Whether the workflow was triggered")
    execution_id: str = Field(default="", description="Execution ID for tracking")
    execution: Dict[str, Any] = Field(default_factory=dict, description="Execution details")
    error: str = Field(default="", description="Error message if failed")


async def n8n_run_workflow(params: N8nRunWorkflowInput) -> N8nRunWorkflowOutput:
    """Execute an n8n workflow.
    
    Triggers a workflow execution and returns the execution ID for tracking.
    
    Args:
        params: Workflow ID and optional payload
        
    Returns:
        Execution result
    """
    logger.info(f"Running n8n workflow: {params.workflow_id}")
    
    try:
        with N8nClient() as client:
            result = client.run_workflow(params.workflow_id, params.payload)
            
            if not result.get("success"):
                return N8nRunWorkflowOutput(
                    success=False,
                    error=result.get("error", "Unknown error"),
                )
            
            execution = result.get("execution", {})
            execution_id = str(execution.get("id", execution.get("executionId", "")))
            
            return N8nRunWorkflowOutput(
                success=True,
                execution_id=execution_id,
                execution=execution,
            )
    except Exception as e:
        logger.error(f"Failed to run workflow: {e}")
        return N8nRunWorkflowOutput(
            success=False,
            error=str(e),
        )


# =============================================================================
# Get Execution Tool
# =============================================================================

class N8nGetExecutionInput(BaseModel):
    """Input schema for n8n_get_execution."""
    
    execution_id: str = Field(description="ID of the execution to retrieve")


class N8nGetExecutionOutput(BaseModel):
    """Output schema for n8n_get_execution."""
    
    success: bool = Field(description="Whether the request succeeded")
    execution: Dict[str, Any] = Field(default_factory=dict, description="Execution details")
    status: str = Field(default="", description="Execution status")
    finished: bool = Field(default=False, description="Whether execution is complete")
    error: str = Field(default="", description="Error message if failed")


async def n8n_get_execution(params: N8nGetExecutionInput) -> N8nGetExecutionOutput:
    """Get details of a workflow execution.
    
    Retrieves the status and results of a workflow execution.
    
    Args:
        params: Execution ID
        
    Returns:
        Execution details
    """
    logger.info(f"Getting n8n execution: {params.execution_id}")
    
    try:
        with N8nClient() as client:
            result = client.get_execution(params.execution_id)
            
            if not result.get("success"):
                return N8nGetExecutionOutput(
                    success=False,
                    error=result.get("error", "Unknown error"),
                )
            
            execution = result.get("execution", {})
            
            return N8nGetExecutionOutput(
                success=True,
                execution=execution,
                status=execution.get("status", "unknown"),
                finished=execution.get("finished", False),
            )
    except Exception as e:
        logger.error(f"Failed to get execution: {e}")
        return N8nGetExecutionOutput(
            success=False,
            error=str(e),
        )


# =============================================================================
# Trigger Webhook Tool
# =============================================================================

class N8nTriggerWebhookInput(BaseModel):
    """Input schema for n8n_trigger_webhook."""
    
    path: str = Field(description="Webhook path (after /webhook/)")
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON payload to send to the webhook"
    )


class N8nTriggerWebhookOutput(BaseModel):
    """Output schema for n8n_trigger_webhook."""
    
    success: bool = Field(description="Whether the webhook was triggered")
    status_code: int = Field(default=0, description="HTTP response status code")
    response: Any = Field(default=None, description="Webhook response")
    error: str = Field(default="", description="Error message if failed")


async def n8n_trigger_webhook(params: N8nTriggerWebhookInput) -> N8nTriggerWebhookOutput:
    """Trigger an n8n webhook endpoint.
    
    Sends a POST request to the specified webhook path with optional payload.
    
    Args:
        params: Webhook path and payload
        
    Returns:
        Webhook response
    """
    logger.info(f"Triggering n8n webhook: {params.path}")
    
    try:
        with N8nClient() as client:
            result = client.trigger_webhook(params.path, params.payload)
            
            if not result.get("success"):
                return N8nTriggerWebhookOutput(
                    success=False,
                    error=result.get("error", "Unknown error"),
                )
            
            return N8nTriggerWebhookOutput(
                success=True,
                status_code=result.get("status_code", 0),
                response=result.get("response"),
            )
    except Exception as e:
        logger.error(f"Failed to trigger webhook: {e}")
        return N8nTriggerWebhookOutput(
            success=False,
            error=str(e),
        )

