"""Azure App Platform tools for App Service and Functions.

Provides MCP tools for:
- Creating App Service plans
- Creating and managing web apps
- Updating app settings
- Creating Function Apps
"""

import logging
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

class AzureAppPlatformCreateAppServicePlanInput(BaseModel):
    """Input schema for azure_app_platform_create_app_service_plan."""
    resource_group: str = Field(description="Resource group name")
    name: str = Field(description="App Service plan name")
    location: str = Field(description="Azure region (e.g., 'eastus')")
    sku: Dict[str, Any] = Field(
        default_factory=lambda: {"name": "B1", "tier": "Basic", "capacity": 1},
        description="SKU configuration (name, tier, capacity)"
    )
    is_linux: bool = Field(default=False, description="True for Linux, False for Windows")
    subscription_id: Optional[str] = Field(
        default=None,
        description="Subscription ID (uses default if not provided)"
    )


class AzureAppPlatformCreateAppServicePlanOutput(BaseModel):
    """Output schema for azure_app_platform_create_app_service_plan."""
    success: bool = Field(description="Whether creation succeeded")
    name: str = Field(default="", description="App Service plan name")
    resource_group: str = Field(default="", description="Resource group")
    location: str = Field(default="", description="Azure region")
    sku_name: str = Field(default="", description="SKU name")
    sku_tier: str = Field(default="", description="SKU tier")
    provisioning_state: str = Field(default="", description="Provisioning state")
    resource_id: str = Field(default="", description="Full resource ID")
    error: str = Field(default="", description="Error message if failed")


class AzureAppPlatformCreateWebAppInput(BaseModel):
    """Input schema for azure_app_platform_create_web_app."""
    resource_group: str = Field(description="Resource group name")
    name: str = Field(description="Web app name (must be globally unique)")
    plan_name: str = Field(description="App Service plan name")
    runtime_stack: Optional[str] = Field(
        default=None,
        description="Runtime stack (e.g., 'PYTHON|3.11', 'NODE|18-lts', 'DOTNETCORE|7.0')"
    )
    https_only: bool = Field(default=True, description="Require HTTPS")
    subscription_id: Optional[str] = Field(
        default=None,
        description="Subscription ID (uses default if not provided)"
    )


class AzureAppPlatformCreateWebAppOutput(BaseModel):
    """Output schema for azure_app_platform_create_web_app."""
    success: bool = Field(description="Whether creation succeeded")
    name: str = Field(default="", description="Web app name")
    resource_group: str = Field(default="", description="Resource group")
    default_hostname: str = Field(default="", description="Default hostname (e.g., myapp.azurewebsites.net)")
    state: str = Field(default="", description="App state (Running, Stopped, etc.)")
    resource_id: str = Field(default="", description="Full resource ID")
    error: str = Field(default="", description="Error message if failed")


class AzureAppPlatformUpdateWebAppSettingsInput(BaseModel):
    """Input schema for azure_app_platform_update_web_app_settings."""
    resource_group: str = Field(description="Resource group name")
    name: str = Field(description="Web app name")
    app_settings: Dict[str, str] = Field(
        default_factory=dict,
        description="Application settings (key-value pairs)"
    )
    connection_strings: Optional[Dict[str, Dict[str, str]]] = Field(
        default=None,
        description="Connection strings (name -> {type, value})"
    )
    subscription_id: Optional[str] = Field(
        default=None,
        description="Subscription ID (uses default if not provided)"
    )


class AzureAppPlatformUpdateWebAppSettingsOutput(BaseModel):
    """Output schema for azure_app_platform_update_web_app_settings."""
    success: bool = Field(description="Whether update succeeded")
    name: str = Field(default="", description="Web app name")
    settings_updated: int = Field(default=0, description="Number of app settings updated")
    connection_strings_updated: int = Field(default=0, description="Number of connection strings updated")
    error: str = Field(default="", description="Error message if failed")


class AzureAppPlatformRestartWebAppInput(BaseModel):
    """Input schema for azure_app_platform_restart_web_app."""
    resource_group: str = Field(description="Resource group name")
    name: str = Field(description="Web app name")
    subscription_id: Optional[str] = Field(
        default=None,
        description="Subscription ID (uses default if not provided)"
    )


class AzureAppPlatformRestartWebAppOutput(BaseModel):
    """Output schema for azure_app_platform_restart_web_app."""
    success: bool = Field(description="Whether restart was initiated")
    name: str = Field(default="", description="Web app name")
    message: str = Field(default="", description="Status message")
    error: str = Field(default="", description="Error message if failed")


class AzureAppPlatformCreateFunctionAppInput(BaseModel):
    """Input schema for azure_app_platform_create_function_app."""
    resource_group: str = Field(description="Resource group name")
    name: str = Field(description="Function app name (must be globally unique)")
    storage_account_name: str = Field(description="Storage account name for function app")
    plan_name: Optional[str] = Field(
        default=None,
        description="App Service plan name (if None, uses Consumption plan)"
    )
    runtime_stack: str = Field(
        default="python",
        description="Runtime (python, node, dotnet, java)"
    )
    runtime_version: str = Field(
        default="3.11",
        description="Runtime version"
    )
    location: str = Field(description="Azure region")
    subscription_id: Optional[str] = Field(
        default=None,
        description="Subscription ID (uses default if not provided)"
    )


class AzureAppPlatformCreateFunctionAppOutput(BaseModel):
    """Output schema for azure_app_platform_create_function_app."""
    success: bool = Field(description="Whether creation succeeded")
    name: str = Field(default="", description="Function app name")
    resource_group: str = Field(default="", description="Resource group")
    default_hostname: str = Field(default="", description="Default hostname")
    state: str = Field(default="", description="App state")
    resource_id: str = Field(default="", description="Full resource ID")
    error: str = Field(default="", description="Error message if failed")


# =============================================================================
# Tool Implementations
# =============================================================================

async def azure_app_platform_create_app_service_plan(
    params: AzureAppPlatformCreateAppServicePlanInput
) -> AzureAppPlatformCreateAppServicePlanOutput:
    """Create an App Service plan.
    
    Args:
        params.resource_group: Resource group name
        params.name: Plan name
        params.location: Azure region
        params.sku: SKU configuration
        params.is_linux: True for Linux plan
        params.subscription_id: Subscription ID
        
    Returns:
        Created plan details
    """
    logger.info(f"Creating App Service plan: {params.name} in {params.resource_group}")
    
    try:
        from azure.mgmt.web import WebSiteManagementClient
        from azure.mgmt.web.models import AppServicePlan, SkuDescription
        
        credential, subscription_id = get_credential_and_subscription(params.subscription_id)
        client = WebSiteManagementClient(credential, subscription_id)
        
        # Build SKU
        sku = SkuDescription(
            name=params.sku.get("name", "B1"),
            tier=params.sku.get("tier", "Basic"),
            capacity=params.sku.get("capacity", 1),
        )
        
        # Build plan
        plan = AppServicePlan(
            location=params.location,
            sku=sku,
            reserved=params.is_linux,  # reserved=True means Linux
        )
        
        # Create plan
        poller = client.app_service_plans.begin_create_or_update(
            params.resource_group,
            params.name,
            plan,
        )
        result = poller.result()
        
        logger.info(f"Created App Service plan: {result.name}")
        
        return AzureAppPlatformCreateAppServicePlanOutput(
            success=True,
            name=result.name,
            resource_group=params.resource_group,
            location=result.location,
            sku_name=result.sku.name if result.sku else "",
            sku_tier=result.sku.tier if result.sku else "",
            provisioning_state=result.provisioning_state or "",
            resource_id=result.id or "",
        )
        
    except AzureError as e:
        logger.error(f"Azure error creating App Service plan: {e}")
        return AzureAppPlatformCreateAppServicePlanOutput(
            success=False,
            name=params.name,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create App Service plan: {e}")
        wrapped = wrap_azure_error(e)
        return AzureAppPlatformCreateAppServicePlanOutput(
            success=False,
            name=params.name,
            error=wrapped.message,
        )


async def azure_app_platform_create_web_app(
    params: AzureAppPlatformCreateWebAppInput
) -> AzureAppPlatformCreateWebAppOutput:
    """Create a web app.
    
    Args:
        params.resource_group: Resource group name
        params.name: Web app name (globally unique)
        params.plan_name: App Service plan name
        params.runtime_stack: Runtime stack (e.g., 'PYTHON|3.11')
        params.https_only: Require HTTPS
        params.subscription_id: Subscription ID
        
    Returns:
        Created web app details
    """
    logger.info(f"Creating web app: {params.name} in {params.resource_group}")
    
    try:
        from azure.mgmt.web import WebSiteManagementClient
        from azure.mgmt.web.models import Site, SiteConfig
        
        credential, subscription_id = get_credential_and_subscription(params.subscription_id)
        client = WebSiteManagementClient(credential, subscription_id)
        
        # Get the App Service plan
        plan = client.app_service_plans.get(params.resource_group, params.plan_name)
        
        # Build site config
        site_config = SiteConfig()
        if params.runtime_stack:
            # Parse runtime stack (format: RUNTIME|VERSION)
            if "|" in params.runtime_stack:
                runtime, version = params.runtime_stack.split("|", 1)
                site_config.linux_fx_version = f"{runtime}|{version}"
        
        # Build site
        site = Site(
            location=plan.location,
            server_farm_id=plan.id,
            site_config=site_config,
            https_only=params.https_only,
        )
        
        # Create web app
        poller = client.web_apps.begin_create_or_update(
            params.resource_group,
            params.name,
            site,
        )
        result = poller.result()
        
        logger.info(f"Created web app: {result.name}")
        
        return AzureAppPlatformCreateWebAppOutput(
            success=True,
            name=result.name,
            resource_group=params.resource_group,
            default_hostname=result.default_host_name or "",
            state=result.state or "",
            resource_id=result.id or "",
        )
        
    except AzureError as e:
        logger.error(f"Azure error creating web app: {e}")
        return AzureAppPlatformCreateWebAppOutput(
            success=False,
            name=params.name,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create web app: {e}")
        wrapped = wrap_azure_error(e)
        return AzureAppPlatformCreateWebAppOutput(
            success=False,
            name=params.name,
            error=wrapped.message,
        )


async def azure_app_platform_update_web_app_settings(
    params: AzureAppPlatformUpdateWebAppSettingsInput
) -> AzureAppPlatformUpdateWebAppSettingsOutput:
    """Update web app settings.
    
    Args:
        params.resource_group: Resource group name
        params.name: Web app name
        params.app_settings: Application settings to update
        params.connection_strings: Connection strings to update
        params.subscription_id: Subscription ID
        
    Returns:
        Update result
    """
    logger.info(f"Updating web app settings: {params.name}")
    
    try:
        from azure.mgmt.web import WebSiteManagementClient
        from azure.mgmt.web.models import StringDictionary, ConnectionStringDictionary
        
        credential, subscription_id = get_credential_and_subscription(params.subscription_id)
        client = WebSiteManagementClient(credential, subscription_id)
        
        settings_updated = 0
        conn_strings_updated = 0
        
        # Update app settings
        if params.app_settings:
            # Get existing settings first
            existing = client.web_apps.list_application_settings(
                params.resource_group,
                params.name
            )
            
            # Merge with new settings
            merged = existing.properties or {}
            merged.update(params.app_settings)
            
            # Update
            client.web_apps.update_application_settings(
                params.resource_group,
                params.name,
                StringDictionary(properties=merged)
            )
            settings_updated = len(params.app_settings)
        
        # Update connection strings
        if params.connection_strings:
            from azure.mgmt.web.models import ConnStringValueTypePair, ConnectionStringType
            
            # Build connection string objects
            conn_dict = {}
            for name, config in params.connection_strings.items():
                conn_type = getattr(
                    ConnectionStringType,
                    config.get("type", "SQLAzure").upper(),
                    ConnectionStringType.SQL_AZURE
                )
                conn_dict[name] = ConnStringValueTypePair(
                    value=config.get("value", ""),
                    type=conn_type
                )
            
            client.web_apps.update_connection_strings(
                params.resource_group,
                params.name,
                ConnectionStringDictionary(properties=conn_dict)
            )
            conn_strings_updated = len(params.connection_strings)
        
        logger.info(f"Updated {settings_updated} settings and {conn_strings_updated} connection strings")
        
        return AzureAppPlatformUpdateWebAppSettingsOutput(
            success=True,
            name=params.name,
            settings_updated=settings_updated,
            connection_strings_updated=conn_strings_updated,
        )
        
    except AzureError as e:
        logger.error(f"Azure error updating web app settings: {e}")
        return AzureAppPlatformUpdateWebAppSettingsOutput(
            success=False,
            name=params.name,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to update web app settings: {e}")
        wrapped = wrap_azure_error(e)
        return AzureAppPlatformUpdateWebAppSettingsOutput(
            success=False,
            name=params.name,
            error=wrapped.message,
        )


async def azure_app_platform_restart_web_app(
    params: AzureAppPlatformRestartWebAppInput
) -> AzureAppPlatformRestartWebAppOutput:
    """Restart a web app.
    
    Args:
        params.resource_group: Resource group name
        params.name: Web app name
        params.subscription_id: Subscription ID
        
    Returns:
        Restart result
    """
    logger.info(f"Restarting web app: {params.name}")
    
    try:
        from azure.mgmt.web import WebSiteManagementClient
        
        credential, subscription_id = get_credential_and_subscription(params.subscription_id)
        client = WebSiteManagementClient(credential, subscription_id)
        
        # Restart the web app
        client.web_apps.restart(params.resource_group, params.name)
        
        logger.info(f"Restarted web app: {params.name}")
        
        return AzureAppPlatformRestartWebAppOutput(
            success=True,
            name=params.name,
            message=f"Web app '{params.name}' restart initiated",
        )
        
    except AzureError as e:
        logger.error(f"Azure error restarting web app: {e}")
        return AzureAppPlatformRestartWebAppOutput(
            success=False,
            name=params.name,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to restart web app: {e}")
        wrapped = wrap_azure_error(e)
        return AzureAppPlatformRestartWebAppOutput(
            success=False,
            name=params.name,
            error=wrapped.message,
        )


async def azure_app_platform_create_function_app(
    params: AzureAppPlatformCreateFunctionAppInput
) -> AzureAppPlatformCreateFunctionAppOutput:
    """Create a Function App.
    
    Creates a Function App with the specified runtime. If no plan is specified,
    uses the Consumption plan.
    
    Args:
        params.resource_group: Resource group name
        params.name: Function app name (globally unique)
        params.storage_account_name: Storage account for the function app
        params.plan_name: Optional App Service plan (None for Consumption)
        params.runtime_stack: Runtime (python, node, dotnet, java)
        params.runtime_version: Runtime version
        params.location: Azure region
        params.subscription_id: Subscription ID
        
    Returns:
        Created function app details
    """
    logger.info(f"Creating Function App: {params.name}")
    
    try:
        from azure.mgmt.web import WebSiteManagementClient
        from azure.mgmt.web.models import Site, SiteConfig, NameValuePair
        
        credential, subscription_id = get_credential_and_subscription(params.subscription_id)
        client = WebSiteManagementClient(credential, subscription_id)
        
        # Get storage account connection string
        # Note: In a real implementation, you'd fetch this from the storage account
        storage_connection = f"DefaultEndpointsProtocol=https;AccountName={params.storage_account_name};EndpointSuffix=core.windows.net"
        
        # Build app settings
        app_settings = [
            NameValuePair(name="AzureWebJobsStorage", value=storage_connection),
            NameValuePair(name="FUNCTIONS_EXTENSION_VERSION", value="~4"),
            NameValuePair(name="FUNCTIONS_WORKER_RUNTIME", value=params.runtime_stack),
        ]
        
        # Build site config
        site_config = SiteConfig(
            app_settings=app_settings,
        )
        
        # Set runtime version for Linux
        runtime_map = {
            "python": "PYTHON",
            "node": "NODE",
            "dotnet": "DOTNET",
            "java": "JAVA",
        }
        runtime = runtime_map.get(params.runtime_stack.lower(), params.runtime_stack.upper())
        site_config.linux_fx_version = f"{runtime}|{params.runtime_version}"
        
        # Get plan if specified
        server_farm_id = None
        if params.plan_name:
            plan = client.app_service_plans.get(params.resource_group, params.plan_name)
            server_farm_id = plan.id
        
        # Build site
        site = Site(
            location=params.location,
            server_farm_id=server_farm_id,
            site_config=site_config,
            kind="functionapp,linux",
            reserved=True,  # Linux
        )
        
        # Create function app
        poller = client.web_apps.begin_create_or_update(
            params.resource_group,
            params.name,
            site,
        )
        result = poller.result()
        
        logger.info(f"Created Function App: {result.name}")
        
        return AzureAppPlatformCreateFunctionAppOutput(
            success=True,
            name=result.name,
            resource_group=params.resource_group,
            default_hostname=result.default_host_name or "",
            state=result.state or "",
            resource_id=result.id or "",
        )
        
    except AzureError as e:
        logger.error(f"Azure error creating Function App: {e}")
        return AzureAppPlatformCreateFunctionAppOutput(
            success=False,
            name=params.name,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create Function App: {e}")
        wrapped = wrap_azure_error(e)
        return AzureAppPlatformCreateFunctionAppOutput(
            success=False,
            name=params.name,
            error=wrapped.message,
        )

