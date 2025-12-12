"""Azure tools package.

Contains Azure-related MCP tools organized by function:

Phase 1 (Implemented):
- auth: Authentication and credential management
- core: Subscriptions, resource groups, locations
- resources: Generic ARM resource operations
- deployments: ARM/Bicep deployments
- app_platform: App Service and Functions
- data: Storage accounts and SQL
- monitoring: Metrics, logs, and alerts
- cost: Cost management and analysis
- cli: Azure CLI command execution (existing)
- monitor: HTTP health probes (existing)

Phase 2 (Stubs):
- network: Virtual networks, subnets, load balancers
- security: Key Vault, secrets, RBAC
- compute: Virtual machines
- kubernetes: AKS clusters
"""

# Existing tools
from . import cli
from . import cost
from . import monitor
from . import utils

# Phase 1: Core infrastructure tools
from . import auth
from . import core
from . import resources
from . import deployments
from . import app_platform
from . import data
from . import monitoring

# Phase 2: Stub modules
from . import network
from . import security
from . import compute
from . import kubernetes

# Export specific functions for convenience
from .auth import (
    get_azure_credential,
    get_subscription_id,
    get_credential_and_subscription,
    AzureError,
    AzureAuthError,
    AzureConfigError,
    AzureNotFoundError,
    AzureValidationError,
    AzureAPIError,
    AzureAuthorizationError,
)

from .core import (
    azure_core_get_connection_info,
    azure_core_list_subscriptions,
    azure_core_list_locations,
    azure_core_list_resource_groups,
    azure_core_create_resource_group,
    azure_core_delete_resource_group,
)

from .resources import (
    azure_resources_get_resource,
    azure_resources_delete_resource,
    azure_resources_list_by_type,
    azure_resources_search,
)

from .deployments import (
    azure_deployments_deploy_to_resource_group,
    azure_deployments_deploy_to_subscription,
    azure_deployments_get_status,
    azure_deployments_list,
)

from .app_platform import (
    azure_app_platform_create_app_service_plan,
    azure_app_platform_create_web_app,
    azure_app_platform_update_web_app_settings,
    azure_app_platform_restart_web_app,
    azure_app_platform_create_function_app,
)

from .data import (
    azure_data_create_storage_account,
    azure_data_create_blob_container,
    azure_data_create_sql_server,
    azure_data_create_sql_database,
    azure_data_set_sql_firewall_rule_allow_azure_services,
)

from .monitoring import (
    azure_monitoring_get_metrics,
    azure_monitoring_query_logs,
    azure_monitoring_list_alerts,
)

from .cost import (
    azure_cost_get_summary,
    azure_cost_get_top_cost_drivers,
)

# Flows: High-level orchestration tools
from . import flows
from .flows import (
    azure_flow_create_app_environment,
    azure_flow_add_data_services,
    azure_flow_deploy_standard_template,
    build_resource_names,
    build_default_tags,
)

__all__ = [
    # Modules
    "auth",
    "cli",
    "core",
    "resources",
    "deployments",
    "app_platform",
    "data",
    "monitoring",
    "cost",
    "monitor",
    "utils",
    "network",
    "security",
    "compute",
    "kubernetes",
    
    # Auth helpers
    "get_azure_credential",
    "get_subscription_id",
    "get_credential_and_subscription",
    "AzureError",
    "AzureAuthError",
    "AzureConfigError",
    "AzureNotFoundError",
    "AzureValidationError",
    "AzureAPIError",
    "AzureAuthorizationError",
    
    # Core tools
    "azure_core_get_connection_info",
    "azure_core_list_subscriptions",
    "azure_core_list_locations",
    "azure_core_list_resource_groups",
    "azure_core_create_resource_group",
    "azure_core_delete_resource_group",
    
    # Resources tools
    "azure_resources_get_resource",
    "azure_resources_delete_resource",
    "azure_resources_list_by_type",
    "azure_resources_search",
    
    # Deployments tools
    "azure_deployments_deploy_to_resource_group",
    "azure_deployments_deploy_to_subscription",
    "azure_deployments_get_status",
    "azure_deployments_list",
    
    # App Platform tools
    "azure_app_platform_create_app_service_plan",
    "azure_app_platform_create_web_app",
    "azure_app_platform_update_web_app_settings",
    "azure_app_platform_restart_web_app",
    "azure_app_platform_create_function_app",
    
    # Data tools
    "azure_data_create_storage_account",
    "azure_data_create_blob_container",
    "azure_data_create_sql_server",
    "azure_data_create_sql_database",
    "azure_data_set_sql_firewall_rule_allow_azure_services",
    
    # Monitoring tools
    "azure_monitoring_get_metrics",
    "azure_monitoring_query_logs",
    "azure_monitoring_list_alerts",
    
    # Cost tools
    "azure_cost_get_summary",
    "azure_cost_get_top_cost_drivers",
    
    # Flow tools (orchestration)
    "flows",
    "azure_flow_create_app_environment",
    "azure_flow_add_data_services",
    "azure_flow_deploy_standard_template",
    "build_resource_names",
    "build_default_tags",
]
