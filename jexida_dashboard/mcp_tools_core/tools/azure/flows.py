"""Azure orchestration flows for high-level operations.

Provides MCP tools that orchestrate multiple low-level Azure tools
to perform complete operations like:
- Creating a full app environment (RG + Plan + WebApp)
- Adding data services (Storage + SQL)
- Deploying ARM templates

These flows are designed to be:
- Idempotent where possible (ensure vs always create)
- Return consistent structured output
- Be callable from CLI, web dashboard, or other MCP orchestrations
"""

import json
import logging
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field

from .auth import AzureError, wrap_azure_error

logger = logging.getLogger(__name__)


# =============================================================================
# Naming Convention Helpers
# =============================================================================

def build_resource_names(base_name: str, environment: str = "dev") -> Dict[str, str]:
    """Build deterministic resource names from base_name.
    
    Args:
        base_name: Base name for resources (e.g., "myapp", "dd-staging")
        environment: Environment name (dev, staging, prod)
        
    Returns:
        Dictionary of resource names
    """
    # Sanitize base_name for different naming requirements
    safe_name = base_name.lower().replace("-", "").replace("_", "")[:20]
    env_suffix = environment[:4]  # Shorten environment for storage accounts
    
    return {
        "resource_group": f"rg-{base_name}-{environment}",
        "app_service_plan": f"plan-{base_name}-{environment}",
        "web_app": f"{base_name}-{environment}",
        "storage_account": f"st{safe_name}{env_suffix}"[:24],  # 3-24 chars, lowercase, no hyphens
        "blob_container": "assets",
        "sql_server": f"sql-{base_name}-{environment}",
        "sql_database": f"db-{base_name}-{environment}",
    }


def build_default_tags(
    environment: str = "dev",
    owner: Optional[str] = None,
    extra_tags: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
    """Build standard tags for resources.
    
    Args:
        environment: Environment name
        owner: Owner email or identifier
        extra_tags: Additional tags to merge
        
    Returns:
        Dictionary of tags
    """
    tags = {
        "system": "jexida-mcp",
        "environment": environment,
        "managed-by": "jexida-flows",
    }
    
    if owner:
        tags["owner"] = owner
    
    if extra_tags:
        tags.update(extra_tags)
    
    return tags


# =============================================================================
# Flow Input/Output Schemas
# =============================================================================

class AzureFlowCreateAppEnvironmentInput(BaseModel):
    """Input schema for azure_flow_create_app_environment."""
    base_name: str = Field(
        description="Base name for all resources (e.g., 'myapp', 'dd-staging')"
    )
    location: str = Field(
        description="Azure region (e.g., 'eastus', 'westus2')"
    )
    environment: str = Field(
        default="dev",
        description="Environment name: dev, staging, prod"
    )
    tags: Optional[Dict[str, str]] = Field(
        default=None,
        description="Additional tags to apply to all resources"
    )
    sku: Dict[str, Any] = Field(
        default_factory=lambda: {"name": "B1", "tier": "Basic", "capacity": 1},
        description="App Service plan SKU configuration"
    )
    is_linux: bool = Field(
        default=True,
        description="True for Linux, False for Windows"
    )
    runtime_stack: Optional[str] = Field(
        default="PYTHON|3.11",
        description="Runtime stack (e.g., 'PYTHON|3.11', 'NODE|18-lts')"
    )


class CreatedResource(BaseModel):
    """Information about a created/found resource."""
    name: str = Field(description="Resource name")
    type: str = Field(description="Resource type")
    resource_id: str = Field(default="", description="Full resource ID")
    status: str = Field(default="created", description="created, existing, or failed")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional details")


class AzureFlowCreateAppEnvironmentOutput(BaseModel):
    """Output schema for azure_flow_create_app_environment."""
    ok: bool = Field(description="Whether the flow completed successfully")
    error: str = Field(default="", description="Error message if failed")
    resource_group: str = Field(default="", description="Resource group name")
    app_service_plan: str = Field(default="", description="App Service plan name")
    web_app: str = Field(default="", description="Web app name")
    web_app_url: str = Field(default="", description="Web app URL")
    resources: List[CreatedResource] = Field(
        default_factory=list,
        description="List of created/found resources"
    )
    summary: str = Field(default="", description="Human-readable summary")


class AzureFlowAddDataServicesInput(BaseModel):
    """Input schema for azure_flow_add_data_services."""
    resource_group: str = Field(description="Target resource group name")
    base_name: str = Field(description="Base name for resources")
    location: str = Field(description="Azure region")
    include_storage: bool = Field(
        default=True,
        description="Create storage account and container"
    )
    include_sql: bool = Field(
        default=True,
        description="Create SQL Server and database"
    )
    sql_admin_login: str = Field(
        default="sqladmin",
        description="SQL Server admin login name"
    )
    sql_admin_password_secret_ref: str = Field(
        default="azure:sql_admin_password",
        description="Secret reference for SQL admin password"
    )
    tags: Optional[Dict[str, str]] = Field(
        default=None,
        description="Tags to apply to resources"
    )
    environment: str = Field(
        default="dev",
        description="Environment name for naming convention"
    )


class AzureFlowAddDataServicesOutput(BaseModel):
    """Output schema for azure_flow_add_data_services."""
    ok: bool = Field(description="Whether the flow completed successfully")
    error: str = Field(default="", description="Error message if failed")
    storage_account: str = Field(default="", description="Storage account name")
    storage_endpoint: str = Field(default="", description="Storage blob endpoint")
    blob_container: str = Field(default="", description="Blob container name")
    sql_server: str = Field(default="", description="SQL server name")
    sql_server_fqdn: str = Field(default="", description="SQL server FQDN")
    sql_database: str = Field(default="", description="SQL database name")
    resources: List[CreatedResource] = Field(
        default_factory=list,
        description="List of created/found resources"
    )
    summary: str = Field(default="", description="Human-readable summary")


class AzureFlowDeployStandardTemplateInput(BaseModel):
    """Input schema for azure_flow_deploy_standard_template."""
    resource_group: str = Field(description="Target resource group name")
    deployment_name: str = Field(description="Unique deployment name")
    template_source: str = Field(
        description="Template as JSON string, file path, or URL"
    )
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Template parameters"
    )
    mode: str = Field(
        default="Incremental",
        description="Deployment mode: Incremental or Complete"
    )
    wait_for_completion: bool = Field(
        default=True,
        description="Wait for deployment to complete"
    )


class AzureFlowDeployStandardTemplateOutput(BaseModel):
    """Output schema for azure_flow_deploy_standard_template."""
    ok: bool = Field(description="Whether the deployment succeeded")
    error: str = Field(default="", description="Error message if failed")
    deployment_name: str = Field(default="", description="Deployment name")
    provisioning_state: str = Field(default="", description="Final provisioning state")
    outputs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Deployment outputs"
    )
    correlation_id: str = Field(default="", description="Deployment correlation ID")
    summary: str = Field(default="", description="Human-readable summary")


# =============================================================================
# Flow Implementations
# =============================================================================

async def azure_flow_create_app_environment(
    params: AzureFlowCreateAppEnvironmentInput
) -> AzureFlowCreateAppEnvironmentOutput:
    """Create a complete web app environment.
    
    Creates:
    1. Resource Group
    2. App Service Plan
    3. Web App
    
    Resources are named using a deterministic convention based on base_name
    and environment. The flow is idempotent - existing resources are reused.
    
    Args:
        params: Flow configuration
        
    Returns:
        Flow result with created resources
    """
    logger.info(f"Creating app environment: {params.base_name} in {params.location}")
    
    # Import low-level tools
    from .core import (
        azure_core_create_resource_group,
        AzureCoreCreateResourceGroupInput,
    )
    from .app_platform import (
        azure_app_platform_create_app_service_plan,
        azure_app_platform_create_web_app,
        AzureAppPlatformCreateAppServicePlanInput,
        AzureAppPlatformCreateWebAppInput,
    )
    
    resources = []
    names = build_resource_names(params.base_name, params.environment)
    tags = build_default_tags(params.environment, extra_tags=params.tags)
    
    try:
        # Step 1: Create Resource Group
        logger.info(f"Step 1: Creating resource group {names['resource_group']}")
        rg_result = await azure_core_create_resource_group(
            AzureCoreCreateResourceGroupInput(
                name=names["resource_group"],
                location=params.location,
                tags=tags,
            )
        )
        
        if not rg_result.success:
            return AzureFlowCreateAppEnvironmentOutput(
                ok=False,
                error=f"Failed to create resource group: {rg_result.error}",
            )
        
        resources.append(CreatedResource(
            name=names["resource_group"],
            type="Microsoft.Resources/resourceGroups",
            status="created" if rg_result.created else "existing",
            details={"location": params.location},
        ))
        
        # Step 2: Create App Service Plan
        logger.info(f"Step 2: Creating App Service plan {names['app_service_plan']}")
        plan_result = await azure_app_platform_create_app_service_plan(
            AzureAppPlatformCreateAppServicePlanInput(
                resource_group=names["resource_group"],
                name=names["app_service_plan"],
                location=params.location,
                sku=params.sku,
                is_linux=params.is_linux,
            )
        )
        
        if not plan_result.success:
            return AzureFlowCreateAppEnvironmentOutput(
                ok=False,
                error=f"Failed to create App Service plan: {plan_result.error}",
                resource_group=names["resource_group"],
                resources=resources,
            )
        
        resources.append(CreatedResource(
            name=names["app_service_plan"],
            type="Microsoft.Web/serverfarms",
            resource_id=plan_result.resource_id,
            status="created",
            details={"sku": plan_result.sku_name, "tier": plan_result.sku_tier},
        ))
        
        # Step 3: Create Web App
        logger.info(f"Step 3: Creating web app {names['web_app']}")
        app_result = await azure_app_platform_create_web_app(
            AzureAppPlatformCreateWebAppInput(
                resource_group=names["resource_group"],
                name=names["web_app"],
                plan_name=names["app_service_plan"],
                runtime_stack=params.runtime_stack,
                https_only=True,
            )
        )
        
        if not app_result.success:
            return AzureFlowCreateAppEnvironmentOutput(
                ok=False,
                error=f"Failed to create web app: {app_result.error}",
                resource_group=names["resource_group"],
                app_service_plan=names["app_service_plan"],
                resources=resources,
            )
        
        resources.append(CreatedResource(
            name=names["web_app"],
            type="Microsoft.Web/sites",
            resource_id=app_result.resource_id,
            status="created",
            details={
                "hostname": app_result.default_hostname,
                "state": app_result.state,
            },
        ))
        
        web_app_url = f"https://{app_result.default_hostname}"
        
        summary = (
            f"Successfully created app environment '{params.base_name}' in {params.location}:\n"
            f"  - Resource Group: {names['resource_group']}\n"
            f"  - App Service Plan: {names['app_service_plan']} ({params.sku.get('name', 'B1')})\n"
            f"  - Web App: {names['web_app']}\n"
            f"  - URL: {web_app_url}"
        )
        
        logger.info(f"App environment created successfully: {names['web_app']}")
        
        return AzureFlowCreateAppEnvironmentOutput(
            ok=True,
            resource_group=names["resource_group"],
            app_service_plan=names["app_service_plan"],
            web_app=names["web_app"],
            web_app_url=web_app_url,
            resources=resources,
            summary=summary,
        )
        
    except AzureError as e:
        logger.error(f"Azure error in create_app_environment: {e}")
        return AzureFlowCreateAppEnvironmentOutput(
            ok=False,
            error=str(e),
            resources=resources,
        )
    except Exception as e:
        logger.error(f"Unexpected error in create_app_environment: {e}")
        return AzureFlowCreateAppEnvironmentOutput(
            ok=False,
            error=f"Unexpected error: {str(e)}",
            resources=resources,
        )


async def azure_flow_add_data_services(
    params: AzureFlowAddDataServicesInput
) -> AzureFlowAddDataServicesOutput:
    """Add data services to an existing environment.
    
    Creates:
    1. Storage Account (if include_storage=True)
    2. Blob Container (if include_storage=True)
    3. SQL Server (if include_sql=True)
    4. SQL Database (if include_sql=True)
    5. SQL Firewall Rule for Azure Services (if include_sql=True)
    
    Args:
        params: Flow configuration
        
    Returns:
        Flow result with created resources
    """
    logger.info(f"Adding data services to {params.resource_group}")
    
    from .data import (
        azure_data_create_storage_account,
        azure_data_create_blob_container,
        azure_data_create_sql_server,
        azure_data_create_sql_database,
        azure_data_set_sql_firewall_rule_allow_azure_services,
        AzureDataCreateStorageAccountInput,
        AzureDataCreateBlobContainerInput,
        AzureDataCreateSqlServerInput,
        AzureDataCreateSqlDatabaseInput,
        AzureDataSetSqlFirewallRuleInput,
    )
    
    resources = []
    names = build_resource_names(params.base_name, params.environment)
    tags = build_default_tags(params.environment, extra_tags=params.tags)
    
    storage_account = ""
    storage_endpoint = ""
    blob_container = ""
    sql_server = ""
    sql_server_fqdn = ""
    sql_database = ""
    
    try:
        # Storage Account
        if params.include_storage:
            logger.info(f"Creating storage account {names['storage_account']}")
            
            storage_result = await azure_data_create_storage_account(
                AzureDataCreateStorageAccountInput(
                    resource_group=params.resource_group,
                    name=names["storage_account"],
                    location=params.location,
                    sku="Standard_LRS",
                    kind="StorageV2",
                    tags=tags,
                )
            )
            
            if not storage_result.success:
                return AzureFlowAddDataServicesOutput(
                    ok=False,
                    error=f"Failed to create storage account: {storage_result.error}",
                    resources=resources,
                )
            
            storage_account = names["storage_account"]
            storage_endpoint = storage_result.primary_endpoint
            
            resources.append(CreatedResource(
                name=storage_account,
                type="Microsoft.Storage/storageAccounts",
                resource_id=storage_result.resource_id,
                status="created",
                details={"endpoint": storage_endpoint},
            ))
            
            # Blob Container
            logger.info(f"Creating blob container {names['blob_container']}")
            
            container_result = await azure_data_create_blob_container(
                AzureDataCreateBlobContainerInput(
                    resource_group=params.resource_group,
                    account_name=storage_account,
                    container_name=names["blob_container"],
                    public_access="None",
                )
            )
            
            if not container_result.success:
                return AzureFlowAddDataServicesOutput(
                    ok=False,
                    error=f"Failed to create blob container: {container_result.error}",
                    storage_account=storage_account,
                    storage_endpoint=storage_endpoint,
                    resources=resources,
                )
            
            blob_container = names["blob_container"]
            
            resources.append(CreatedResource(
                name=blob_container,
                type="Microsoft.Storage/blobContainers",
                resource_id=container_result.resource_id,
                status="created",
            ))
        
        # SQL Server and Database
        if params.include_sql:
            logger.info(f"Creating SQL server {names['sql_server']}")
            
            sql_server_result = await azure_data_create_sql_server(
                AzureDataCreateSqlServerInput(
                    resource_group=params.resource_group,
                    name=names["sql_server"],
                    location=params.location,
                    admin_login=params.sql_admin_login,
                    admin_password_secret_ref=params.sql_admin_password_secret_ref,
                    tags=tags,
                )
            )
            
            if not sql_server_result.success:
                return AzureFlowAddDataServicesOutput(
                    ok=False,
                    error=f"Failed to create SQL server: {sql_server_result.error}",
                    storage_account=storage_account,
                    storage_endpoint=storage_endpoint,
                    blob_container=blob_container,
                    resources=resources,
                )
            
            sql_server = names["sql_server"]
            sql_server_fqdn = sql_server_result.fqdn
            
            resources.append(CreatedResource(
                name=sql_server,
                type="Microsoft.Sql/servers",
                resource_id=sql_server_result.resource_id,
                status="created",
                details={"fqdn": sql_server_fqdn},
            ))
            
            # SQL Database
            logger.info(f"Creating SQL database {names['sql_database']}")
            
            db_result = await azure_data_create_sql_database(
                AzureDataCreateSqlDatabaseInput(
                    resource_group=params.resource_group,
                    server_name=sql_server,
                    database_name=names["sql_database"],
                    sku_name="Basic",
                )
            )
            
            if not db_result.success:
                return AzureFlowAddDataServicesOutput(
                    ok=False,
                    error=f"Failed to create SQL database: {db_result.error}",
                    storage_account=storage_account,
                    storage_endpoint=storage_endpoint,
                    blob_container=blob_container,
                    sql_server=sql_server,
                    sql_server_fqdn=sql_server_fqdn,
                    resources=resources,
                )
            
            sql_database = names["sql_database"]
            
            resources.append(CreatedResource(
                name=sql_database,
                type="Microsoft.Sql/databases",
                resource_id=db_result.resource_id,
                status="created",
            ))
            
            # Firewall rule
            logger.info("Setting SQL firewall rule for Azure services")
            
            fw_result = await azure_data_set_sql_firewall_rule_allow_azure_services(
                AzureDataSetSqlFirewallRuleInput(
                    resource_group=params.resource_group,
                    server_name=sql_server,
                )
            )
            
            if not fw_result.success:
                logger.warning(f"Firewall rule failed (non-fatal): {fw_result.error}")
            else:
                resources.append(CreatedResource(
                    name=fw_result.rule_name,
                    type="Microsoft.Sql/firewallRules",
                    status="created",
                ))
        
        # Build summary
        summary_parts = [f"Added data services to '{params.resource_group}':"]
        if params.include_storage:
            summary_parts.append(f"  - Storage Account: {storage_account}")
            summary_parts.append(f"  - Blob Container: {blob_container}")
        if params.include_sql:
            summary_parts.append(f"  - SQL Server: {sql_server} ({sql_server_fqdn})")
            summary_parts.append(f"  - SQL Database: {sql_database}")
        
        summary = "\n".join(summary_parts)
        
        logger.info("Data services added successfully")
        
        return AzureFlowAddDataServicesOutput(
            ok=True,
            storage_account=storage_account,
            storage_endpoint=storage_endpoint,
            blob_container=blob_container,
            sql_server=sql_server,
            sql_server_fqdn=sql_server_fqdn,
            sql_database=sql_database,
            resources=resources,
            summary=summary,
        )
        
    except AzureError as e:
        logger.error(f"Azure error in add_data_services: {e}")
        return AzureFlowAddDataServicesOutput(
            ok=False,
            error=str(e),
            resources=resources,
        )
    except Exception as e:
        logger.error(f"Unexpected error in add_data_services: {e}")
        return AzureFlowAddDataServicesOutput(
            ok=False,
            error=f"Unexpected error: {str(e)}",
            resources=resources,
        )


async def azure_flow_deploy_standard_template(
    params: AzureFlowDeployStandardTemplateInput
) -> AzureFlowDeployStandardTemplateOutput:
    """Deploy an ARM template with a simplified interface.
    
    Accepts template as:
    - JSON string
    - Local file path
    - URL (not implemented yet)
    
    Args:
        params: Flow configuration
        
    Returns:
        Deployment result
    """
    logger.info(f"Deploying template to {params.resource_group}: {params.deployment_name}")
    
    from .deployments import (
        azure_deployments_deploy_to_resource_group,
        AzureDeploymentsDeployToResourceGroupInput,
    )
    
    try:
        # Parse template source
        template = None
        
        # Try to parse as JSON first
        try:
            template = json.loads(params.template_source)
            logger.info("Template parsed as JSON string")
        except json.JSONDecodeError:
            pass
        
        # Try to read as file path
        if template is None:
            import os
            if os.path.isfile(params.template_source):
                with open(params.template_source, 'r') as f:
                    template = json.load(f)
                logger.info(f"Template loaded from file: {params.template_source}")
        
        # Check if template was loaded
        if template is None:
            return AzureFlowDeployStandardTemplateOutput(
                ok=False,
                error=f"Could not parse template_source as JSON or load from file: {params.template_source[:100]}",
                deployment_name=params.deployment_name,
            )
        
        # Validate template has minimum structure
        if "$schema" not in template and "resources" not in template:
            return AzureFlowDeployStandardTemplateOutput(
                ok=False,
                error="Template does not appear to be a valid ARM template (missing $schema or resources)",
                deployment_name=params.deployment_name,
            )
        
        # Deploy
        logger.info(f"Starting deployment: {params.deployment_name}")
        
        deploy_result = await azure_deployments_deploy_to_resource_group(
            AzureDeploymentsDeployToResourceGroupInput(
                resource_group=params.resource_group,
                deployment_name=params.deployment_name,
                template=template,
                parameters=params.parameters or {},
                mode=params.mode,
            )
        )
        
        if not deploy_result.success:
            return AzureFlowDeployStandardTemplateOutput(
                ok=False,
                error=f"Deployment failed: {deploy_result.error}",
                deployment_name=params.deployment_name,
            )
        
        # Build outputs dict
        outputs = {}
        for output in deploy_result.outputs:
            outputs[output.key] = output.value
        
        # Build summary
        summary = (
            f"Deployment '{params.deployment_name}' completed:\n"
            f"  - Resource Group: {params.resource_group}\n"
            f"  - State: {deploy_result.provisioning_state}\n"
            f"  - Mode: {params.mode}"
        )
        
        if outputs:
            summary += "\n  - Outputs:"
            for key, value in outputs.items():
                summary += f"\n    - {key}: {value}"
        
        logger.info(f"Deployment completed: {deploy_result.provisioning_state}")
        
        return AzureFlowDeployStandardTemplateOutput(
            ok=True,
            deployment_name=params.deployment_name,
            provisioning_state=deploy_result.provisioning_state,
            outputs=outputs,
            correlation_id=deploy_result.correlation_id,
            summary=summary,
        )
        
    except AzureError as e:
        logger.error(f"Azure error in deploy_standard_template: {e}")
        return AzureFlowDeployStandardTemplateOutput(
            ok=False,
            error=str(e),
            deployment_name=params.deployment_name,
        )
    except Exception as e:
        logger.error(f"Unexpected error in deploy_standard_template: {e}")
        return AzureFlowDeployStandardTemplateOutput(
            ok=False,
            error=f"Unexpected error: {str(e)}",
            deployment_name=params.deployment_name,
        )

