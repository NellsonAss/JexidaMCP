#!/usr/bin/env python3
"""Register Azure SDK MCP tools in the database.

Run this on the MCP server after deploying the Azure tools modules.

Usage:
    python scripts/register_azure_sdk_tools.py
"""

import os
import sys
import django

# Add the jexida_dashboard to the path
sys.path.insert(0, '/opt/jexida-mcp/jexida_dashboard')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jexida_dashboard.settings')

django.setup()

from mcp_tools_core.models import Tool

# =============================================================================
# Phase 1: Implemented Tools
# =============================================================================

PHASE_1_TOOLS = [
    # Core Tools
    {
        "name": "azure_core_get_connection_info",
        "description": "Get current Azure connection information including subscription, tenant, and auth status.",
        "handler_path": "mcp_tools_core.tools.azure.core.azure_core_get_connection_info",
        "tags": "azure,core,config,connection",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "azure_core_list_subscriptions",
        "description": "List all Azure subscriptions accessible with current credentials.",
        "handler_path": "mcp_tools_core.tools.azure.core.azure_core_list_subscriptions",
        "tags": "azure,core,subscriptions",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "azure_core_list_locations",
        "description": "List available Azure locations/regions.",
        "handler_path": "mcp_tools_core.tools.azure.core.azure_core_list_locations",
        "tags": "azure,core,locations,regions",
        "input_schema": {
            "type": "object",
            "properties": {
                "subscription_id": {
                    "type": "string",
                    "description": "Subscription ID (uses default if not provided)"
                }
            },
            "required": []
        }
    },
    {
        "name": "azure_core_list_resource_groups",
        "description": "List resource groups in a subscription.",
        "handler_path": "mcp_tools_core.tools.azure.core.azure_core_list_resource_groups",
        "tags": "azure,core,resourcegroups",
        "input_schema": {
            "type": "object",
            "properties": {
                "subscription_id": {
                    "type": "string",
                    "description": "Subscription ID (uses default if not provided)"
                }
            },
            "required": []
        }
    },
    {
        "name": "azure_core_create_resource_group",
        "description": "Create a new resource group in Azure.",
        "handler_path": "mcp_tools_core.tools.azure.core.azure_core_create_resource_group",
        "tags": "azure,core,resourcegroups,create",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Resource group name"},
                "location": {"type": "string", "description": "Azure region"},
                "tags": {"type": "object", "description": "Optional tags"},
                "subscription_id": {"type": "string", "description": "Subscription ID"}
            },
            "required": ["name", "location"]
        }
    },
    {
        "name": "azure_core_delete_resource_group",
        "description": "Delete a resource group. DESTRUCTIVE: requires force=true.",
        "handler_path": "mcp_tools_core.tools.azure.core.azure_core_delete_resource_group",
        "tags": "azure,core,resourcegroups,delete,destructive",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Resource group name"},
                "force": {"type": "boolean", "default": False, "description": "Must be true to confirm deletion"},
                "subscription_id": {"type": "string", "description": "Subscription ID"}
            },
            "required": ["name"]
        }
    },
    
    # Resources Tools
    {
        "name": "azure_resources_get_resource",
        "description": "Get details of an Azure resource by its full resource ID.",
        "handler_path": "mcp_tools_core.tools.azure.resources.azure_resources_get_resource",
        "tags": "azure,resources,get",
        "input_schema": {
            "type": "object",
            "properties": {
                "resource_id": {"type": "string", "description": "Full Azure resource ID"}
            },
            "required": ["resource_id"]
        }
    },
    {
        "name": "azure_resources_delete_resource",
        "description": "Delete an Azure resource by ID. DESTRUCTIVE: requires force=true.",
        "handler_path": "mcp_tools_core.tools.azure.resources.azure_resources_delete_resource",
        "tags": "azure,resources,delete,destructive",
        "input_schema": {
            "type": "object",
            "properties": {
                "resource_id": {"type": "string", "description": "Full Azure resource ID"},
                "force": {"type": "boolean", "default": False, "description": "Must be true to confirm deletion"}
            },
            "required": ["resource_id"]
        }
    },
    {
        "name": "azure_resources_list_by_type",
        "description": "List Azure resources of a specific type (e.g., Microsoft.Web/sites).",
        "handler_path": "mcp_tools_core.tools.azure.resources.azure_resources_list_by_type",
        "tags": "azure,resources,list",
        "input_schema": {
            "type": "object",
            "properties": {
                "resource_type": {"type": "string", "description": "Resource type (e.g., Microsoft.Web/sites)"},
                "subscription_id": {"type": "string", "description": "Subscription ID"},
                "resource_group": {"type": "string", "description": "Optional resource group filter"}
            },
            "required": ["resource_type"]
        }
    },
    {
        "name": "azure_resources_search",
        "description": "Search Azure resources using Resource Graph queries (Kusto-like syntax).",
        "handler_path": "mcp_tools_core.tools.azure.resources.azure_resources_search",
        "tags": "azure,resources,search,resourcegraph",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Azure Resource Graph query"},
                "subscription_id": {"type": "string", "description": "Subscription ID"},
                "top": {"type": "integer", "default": 100, "description": "Max results"}
            },
            "required": ["query"]
        }
    },
    
    # Deployments Tools
    {
        "name": "azure_deployments_deploy_to_resource_group",
        "description": "Deploy an ARM template to a resource group.",
        "handler_path": "mcp_tools_core.tools.azure.deployments.azure_deployments_deploy_to_resource_group",
        "tags": "azure,deployments,arm,bicep",
        "input_schema": {
            "type": "object",
            "properties": {
                "resource_group": {"type": "string", "description": "Target resource group"},
                "deployment_name": {"type": "string", "description": "Deployment name"},
                "template": {"type": "object", "description": "ARM template as JSON"},
                "parameters": {"type": "object", "description": "Template parameters"},
                "mode": {"type": "string", "default": "Incremental", "description": "Incremental or Complete"},
                "subscription_id": {"type": "string", "description": "Subscription ID"}
            },
            "required": ["resource_group", "deployment_name", "template"]
        }
    },
    {
        "name": "azure_deployments_deploy_to_subscription",
        "description": "Deploy an ARM template at subscription scope.",
        "handler_path": "mcp_tools_core.tools.azure.deployments.azure_deployments_deploy_to_subscription",
        "tags": "azure,deployments,arm,bicep,subscription",
        "input_schema": {
            "type": "object",
            "properties": {
                "deployment_name": {"type": "string", "description": "Deployment name"},
                "location": {"type": "string", "description": "Azure region for metadata"},
                "template": {"type": "object", "description": "ARM template as JSON"},
                "parameters": {"type": "object", "description": "Template parameters"},
                "mode": {"type": "string", "default": "Incremental", "description": "Incremental or Complete"},
                "subscription_id": {"type": "string", "description": "Subscription ID"}
            },
            "required": ["deployment_name", "location", "template"]
        }
    },
    {
        "name": "azure_deployments_get_status",
        "description": "Get the status of an ARM deployment.",
        "handler_path": "mcp_tools_core.tools.azure.deployments.azure_deployments_get_status",
        "tags": "azure,deployments,status",
        "input_schema": {
            "type": "object",
            "properties": {
                "deployment_name": {"type": "string", "description": "Deployment name"},
                "scope": {"type": "string", "default": "resource_group", "description": "resource_group or subscription"},
                "resource_group": {"type": "string", "description": "Resource group (if scope is resource_group)"},
                "subscription_id": {"type": "string", "description": "Subscription ID"}
            },
            "required": ["deployment_name"]
        }
    },
    {
        "name": "azure_deployments_list",
        "description": "List deployments in a scope.",
        "handler_path": "mcp_tools_core.tools.azure.deployments.azure_deployments_list",
        "tags": "azure,deployments,list",
        "input_schema": {
            "type": "object",
            "properties": {
                "scope": {"type": "string", "default": "resource_group", "description": "resource_group or subscription"},
                "resource_group": {"type": "string", "description": "Resource group (if scope is resource_group)"},
                "subscription_id": {"type": "string", "description": "Subscription ID"},
                "top": {"type": "integer", "default": 25, "description": "Max results"}
            },
            "required": []
        }
    },
    
    # App Platform Tools
    {
        "name": "azure_app_platform_create_app_service_plan",
        "description": "Create an Azure App Service plan.",
        "handler_path": "mcp_tools_core.tools.azure.app_platform.azure_app_platform_create_app_service_plan",
        "tags": "azure,appservice,plan,create",
        "input_schema": {
            "type": "object",
            "properties": {
                "resource_group": {"type": "string", "description": "Resource group name"},
                "name": {"type": "string", "description": "Plan name"},
                "location": {"type": "string", "description": "Azure region"},
                "sku": {"type": "object", "description": "SKU config (name, tier, capacity)"},
                "is_linux": {"type": "boolean", "default": False, "description": "Linux plan"},
                "subscription_id": {"type": "string", "description": "Subscription ID"}
            },
            "required": ["resource_group", "name", "location"]
        }
    },
    {
        "name": "azure_app_platform_create_web_app",
        "description": "Create an Azure Web App.",
        "handler_path": "mcp_tools_core.tools.azure.app_platform.azure_app_platform_create_web_app",
        "tags": "azure,appservice,webapp,create",
        "input_schema": {
            "type": "object",
            "properties": {
                "resource_group": {"type": "string", "description": "Resource group name"},
                "name": {"type": "string", "description": "Web app name (globally unique)"},
                "plan_name": {"type": "string", "description": "App Service plan name"},
                "runtime_stack": {"type": "string", "description": "Runtime (e.g., PYTHON|3.11)"},
                "https_only": {"type": "boolean", "default": True, "description": "Require HTTPS"},
                "subscription_id": {"type": "string", "description": "Subscription ID"}
            },
            "required": ["resource_group", "name", "plan_name"]
        }
    },
    {
        "name": "azure_app_platform_update_web_app_settings",
        "description": "Update web app settings and connection strings.",
        "handler_path": "mcp_tools_core.tools.azure.app_platform.azure_app_platform_update_web_app_settings",
        "tags": "azure,appservice,webapp,settings",
        "input_schema": {
            "type": "object",
            "properties": {
                "resource_group": {"type": "string", "description": "Resource group name"},
                "name": {"type": "string", "description": "Web app name"},
                "app_settings": {"type": "object", "description": "App settings key-value pairs"},
                "connection_strings": {"type": "object", "description": "Connection strings"},
                "subscription_id": {"type": "string", "description": "Subscription ID"}
            },
            "required": ["resource_group", "name"]
        }
    },
    {
        "name": "azure_app_platform_restart_web_app",
        "description": "Restart an Azure Web App.",
        "handler_path": "mcp_tools_core.tools.azure.app_platform.azure_app_platform_restart_web_app",
        "tags": "azure,appservice,webapp,restart",
        "input_schema": {
            "type": "object",
            "properties": {
                "resource_group": {"type": "string", "description": "Resource group name"},
                "name": {"type": "string", "description": "Web app name"},
                "subscription_id": {"type": "string", "description": "Subscription ID"}
            },
            "required": ["resource_group", "name"]
        }
    },
    {
        "name": "azure_app_platform_create_function_app",
        "description": "Create an Azure Function App.",
        "handler_path": "mcp_tools_core.tools.azure.app_platform.azure_app_platform_create_function_app",
        "tags": "azure,functions,create",
        "input_schema": {
            "type": "object",
            "properties": {
                "resource_group": {"type": "string", "description": "Resource group name"},
                "name": {"type": "string", "description": "Function app name (globally unique)"},
                "storage_account_name": {"type": "string", "description": "Storage account for functions"},
                "plan_name": {"type": "string", "description": "App Service plan (None for Consumption)"},
                "runtime_stack": {"type": "string", "default": "python", "description": "Runtime"},
                "runtime_version": {"type": "string", "default": "3.11", "description": "Version"},
                "location": {"type": "string", "description": "Azure region"},
                "subscription_id": {"type": "string", "description": "Subscription ID"}
            },
            "required": ["resource_group", "name", "storage_account_name", "location"]
        }
    },
    
    # Data Tools
    {
        "name": "azure_data_create_storage_account",
        "description": "Create an Azure Storage account.",
        "handler_path": "mcp_tools_core.tools.azure.data.azure_data_create_storage_account",
        "tags": "azure,storage,create",
        "input_schema": {
            "type": "object",
            "properties": {
                "resource_group": {"type": "string", "description": "Resource group name"},
                "name": {"type": "string", "description": "Storage account name (3-24 chars, lowercase)"},
                "location": {"type": "string", "description": "Azure region"},
                "sku": {"type": "string", "default": "Standard_LRS", "description": "Storage SKU"},
                "kind": {"type": "string", "default": "StorageV2", "description": "Storage kind"},
                "access_tier": {"type": "string", "default": "Hot", "description": "Hot or Cool"},
                "tags": {"type": "object", "description": "Tags"},
                "subscription_id": {"type": "string", "description": "Subscription ID"}
            },
            "required": ["resource_group", "name", "location"]
        }
    },
    {
        "name": "azure_data_create_blob_container",
        "description": "Create a blob container in a storage account.",
        "handler_path": "mcp_tools_core.tools.azure.data.azure_data_create_blob_container",
        "tags": "azure,storage,blob,container",
        "input_schema": {
            "type": "object",
            "properties": {
                "resource_group": {"type": "string", "description": "Resource group name"},
                "account_name": {"type": "string", "description": "Storage account name"},
                "container_name": {"type": "string", "description": "Container name"},
                "public_access": {"type": "string", "default": "None", "description": "None, Container, or Blob"},
                "subscription_id": {"type": "string", "description": "Subscription ID"}
            },
            "required": ["resource_group", "account_name", "container_name"]
        }
    },
    {
        "name": "azure_data_create_sql_server",
        "description": "Create an Azure SQL Server.",
        "handler_path": "mcp_tools_core.tools.azure.data.azure_data_create_sql_server",
        "tags": "azure,sql,server,create",
        "input_schema": {
            "type": "object",
            "properties": {
                "resource_group": {"type": "string", "description": "Resource group name"},
                "name": {"type": "string", "description": "SQL server name (globally unique)"},
                "location": {"type": "string", "description": "Azure region"},
                "admin_login": {"type": "string", "description": "Administrator login"},
                "admin_password_secret_ref": {"type": "string", "description": "Secret reference for password"},
                "version": {"type": "string", "default": "12.0", "description": "SQL version"},
                "tags": {"type": "object", "description": "Tags"},
                "subscription_id": {"type": "string", "description": "Subscription ID"}
            },
            "required": ["resource_group", "name", "location", "admin_login", "admin_password_secret_ref"]
        }
    },
    {
        "name": "azure_data_create_sql_database",
        "description": "Create an Azure SQL Database.",
        "handler_path": "mcp_tools_core.tools.azure.data.azure_data_create_sql_database",
        "tags": "azure,sql,database,create",
        "input_schema": {
            "type": "object",
            "properties": {
                "resource_group": {"type": "string", "description": "Resource group name"},
                "server_name": {"type": "string", "description": "SQL server name"},
                "database_name": {"type": "string", "description": "Database name"},
                "sku_name": {"type": "string", "default": "Basic", "description": "SKU (Basic, S0, P1, etc.)"},
                "max_size_bytes": {"type": "integer", "description": "Max size in bytes"},
                "collation": {"type": "string", "default": "SQL_Latin1_General_CP1_CI_AS", "description": "Collation"},
                "subscription_id": {"type": "string", "description": "Subscription ID"}
            },
            "required": ["resource_group", "server_name", "database_name"]
        }
    },
    {
        "name": "azure_data_set_sql_firewall_rule_allow_azure_services",
        "description": "Allow Azure services to access SQL Server via firewall rule.",
        "handler_path": "mcp_tools_core.tools.azure.data.azure_data_set_sql_firewall_rule_allow_azure_services",
        "tags": "azure,sql,firewall",
        "input_schema": {
            "type": "object",
            "properties": {
                "resource_group": {"type": "string", "description": "Resource group name"},
                "server_name": {"type": "string", "description": "SQL server name"},
                "subscription_id": {"type": "string", "description": "Subscription ID"}
            },
            "required": ["resource_group", "server_name"]
        }
    },
    
    # Monitoring Tools
    {
        "name": "azure_monitoring_get_metrics",
        "description": "Get metrics for an Azure resource.",
        "handler_path": "mcp_tools_core.tools.azure.monitoring.azure_monitoring_get_metrics",
        "tags": "azure,monitoring,metrics",
        "input_schema": {
            "type": "object",
            "properties": {
                "resource_id": {"type": "string", "description": "Full Azure resource ID"},
                "metric_names": {"type": "array", "items": {"type": "string"}, "description": "Metric names"},
                "timespan": {"type": "string", "default": "PT1H", "description": "ISO 8601 duration"},
                "interval": {"type": "string", "default": "PT5M", "description": "Metric granularity"},
                "aggregation": {"type": "array", "items": {"type": "string"}, "description": "Aggregation types"}
            },
            "required": ["resource_id", "metric_names"]
        }
    },
    {
        "name": "azure_monitoring_query_logs",
        "description": "Query logs from Log Analytics using Kusto Query Language.",
        "handler_path": "mcp_tools_core.tools.azure.monitoring.azure_monitoring_query_logs",
        "tags": "azure,monitoring,logs,loganalytics,kusto",
        "input_schema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "Log Analytics workspace ID"},
                "kusto_query": {"type": "string", "description": "KQL query"},
                "timespan": {"type": "string", "default": "P1D", "description": "Query timespan"}
            },
            "required": ["workspace_id", "kusto_query"]
        }
    },
    {
        "name": "azure_monitoring_list_alerts",
        "description": "List active alerts in a subscription.",
        "handler_path": "mcp_tools_core.tools.azure.monitoring.azure_monitoring_list_alerts",
        "tags": "azure,monitoring,alerts",
        "input_schema": {
            "type": "object",
            "properties": {
                "subscription_id": {"type": "string", "description": "Subscription ID"},
                "filter": {"type": "string", "description": "OData filter"},
                "state_filter": {"type": "string", "description": "Alert state: New, Acknowledged, Closed"}
            },
            "required": []
        }
    },
    
    # Cost Tools
    {
        "name": "azure_cost_get_summary",
        "description": "Get Azure cost summary for a subscription or resource group.",
        "handler_path": "mcp_tools_core.tools.azure.cost.azure_cost_get_summary",
        "tags": "azure,cost,billing",
        "input_schema": {
            "type": "object",
            "properties": {
                "subscription_id": {"type": "string", "description": "Subscription ID"},
                "resource_group": {"type": "string", "description": "Optional resource group filter"},
                "time_period": {"type": "string", "default": "Last30Days", "description": "Last7Days, Last30Days, MonthToDate"}
            },
            "required": ["subscription_id"]
        }
    },
    {
        "name": "azure_cost_get_top_cost_drivers",
        "description": "Get top cost drivers for a scope.",
        "handler_path": "mcp_tools_core.tools.azure.cost.azure_cost_get_top_cost_drivers",
        "tags": "azure,cost,billing,analysis",
        "input_schema": {
            "type": "object",
            "properties": {
                "scope": {"type": "string", "description": "Cost scope (/subscriptions/{id} or .../resourceGroups/{name})"},
                "time_period": {"type": "object", "description": "{'from': 'YYYY-MM-DD', 'to': 'YYYY-MM-DD'}"},
                "top_n": {"type": "integer", "default": 10, "description": "Number of top drivers"},
                "group_by": {"type": "string", "default": "ResourceGroup", "description": "Grouping dimension"}
            },
            "required": ["scope", "time_period"]
        }
    },
    
    # Flow Tools (High-level Orchestration)
    {
        "name": "azure_flow_create_app_environment",
        "description": "Create a complete app environment: Resource Group + App Service Plan + Web App. Uses deterministic naming based on base_name and environment.",
        "handler_path": "mcp_tools_core.tools.azure.flows.azure_flow_create_app_environment",
        "tags": "azure,flow,orchestration,webapp,appservice",
        "input_schema": {
            "type": "object",
            "properties": {
                "base_name": {"type": "string", "description": "Base name for resources (e.g., 'myapp')"},
                "location": {"type": "string", "description": "Azure region (e.g., 'eastus')"},
                "environment": {"type": "string", "default": "dev", "description": "Environment: dev, staging, prod"},
                "tags": {"type": "object", "description": "Additional tags to apply"},
                "sku": {"type": "object", "description": "App Service plan SKU (name, tier, capacity)"},
                "is_linux": {"type": "boolean", "default": True, "description": "Linux or Windows plan"},
                "runtime_stack": {"type": "string", "default": "PYTHON|3.11", "description": "Runtime stack"}
            },
            "required": ["base_name", "location"]
        }
    },
    {
        "name": "azure_flow_add_data_services",
        "description": "Add data services to an existing environment: Storage Account + Blob Container + SQL Server + Database.",
        "handler_path": "mcp_tools_core.tools.azure.flows.azure_flow_add_data_services",
        "tags": "azure,flow,orchestration,storage,sql",
        "input_schema": {
            "type": "object",
            "properties": {
                "resource_group": {"type": "string", "description": "Target resource group"},
                "base_name": {"type": "string", "description": "Base name for resources"},
                "location": {"type": "string", "description": "Azure region"},
                "include_storage": {"type": "boolean", "default": True, "description": "Create storage account"},
                "include_sql": {"type": "boolean", "default": True, "description": "Create SQL server and database"},
                "sql_admin_login": {"type": "string", "default": "sqladmin", "description": "SQL admin login"},
                "sql_admin_password_secret_ref": {"type": "string", "description": "Secret ref for SQL password"},
                "tags": {"type": "object", "description": "Tags to apply"},
                "environment": {"type": "string", "default": "dev", "description": "Environment name"}
            },
            "required": ["resource_group", "base_name", "location"]
        }
    },
    {
        "name": "azure_flow_deploy_standard_template",
        "description": "Deploy an ARM template with a simplified interface. Accepts template as JSON string or file path.",
        "handler_path": "mcp_tools_core.tools.azure.flows.azure_flow_deploy_standard_template",
        "tags": "azure,flow,orchestration,deployment,arm",
        "input_schema": {
            "type": "object",
            "properties": {
                "resource_group": {"type": "string", "description": "Target resource group"},
                "deployment_name": {"type": "string", "description": "Deployment name"},
                "template_source": {"type": "string", "description": "Template JSON string or file path"},
                "parameters": {"type": "object", "description": "Template parameters"},
                "mode": {"type": "string", "default": "Incremental", "description": "Incremental or Complete"},
                "wait_for_completion": {"type": "boolean", "default": True, "description": "Wait for completion"}
            },
            "required": ["resource_group", "deployment_name", "template_source"]
        }
    },
]

# =============================================================================
# Phase 2: Stub Tools (Not Yet Implemented)
# =============================================================================

PHASE_2_STUBS = [
    # Network Stubs
    {
        "name": "azure_network_create_vnet",
        "description": "[PLANNED] Create an Azure Virtual Network. Not yet implemented - use azure_cli_run.",
        "handler_path": "mcp_tools_core.tools.azure.network.azure_network_create_vnet",
        "tags": "azure,network,vnet,planned",
        "input_schema": {"type": "object", "properties": {}, "required": []},
        "is_active": False
    },
    {
        "name": "azure_network_create_subnet",
        "description": "[PLANNED] Create a subnet. Not yet implemented - use azure_cli_run.",
        "handler_path": "mcp_tools_core.tools.azure.network.azure_network_create_subnet",
        "tags": "azure,network,subnet,planned",
        "input_schema": {"type": "object", "properties": {}, "required": []},
        "is_active": False
    },
    {
        "name": "azure_network_attach_nsg",
        "description": "[PLANNED] Attach NSG to subnet/NIC. Not yet implemented - use azure_cli_run.",
        "handler_path": "mcp_tools_core.tools.azure.network.azure_network_attach_nsg",
        "tags": "azure,network,nsg,planned",
        "input_schema": {"type": "object", "properties": {}, "required": []},
        "is_active": False
    },
    {
        "name": "azure_network_create_public_ip",
        "description": "[PLANNED] Create a public IP. Not yet implemented - use azure_cli_run.",
        "handler_path": "mcp_tools_core.tools.azure.network.azure_network_create_public_ip",
        "tags": "azure,network,publicip,planned",
        "input_schema": {"type": "object", "properties": {}, "required": []},
        "is_active": False
    },
    {
        "name": "azure_network_create_basic_load_balancer",
        "description": "[PLANNED] Create a load balancer. Not yet implemented - use azure_cli_run.",
        "handler_path": "mcp_tools_core.tools.azure.network.azure_network_create_basic_load_balancer",
        "tags": "azure,network,loadbalancer,planned",
        "input_schema": {"type": "object", "properties": {}, "required": []},
        "is_active": False
    },
    
    # Security Stubs
    {
        "name": "azure_security_create_key_vault",
        "description": "[PLANNED] Create Key Vault. Not yet implemented - use azure_cli_run.",
        "handler_path": "mcp_tools_core.tools.azure.security.azure_security_create_key_vault",
        "tags": "azure,security,keyvault,planned",
        "input_schema": {"type": "object", "properties": {}, "required": []},
        "is_active": False
    },
    {
        "name": "azure_security_set_secret",
        "description": "[PLANNED] Set Key Vault secret. Not yet implemented - use azure_cli_run.",
        "handler_path": "mcp_tools_core.tools.azure.security.azure_security_set_secret",
        "tags": "azure,security,keyvault,secrets,planned",
        "input_schema": {"type": "object", "properties": {}, "required": []},
        "is_active": False
    },
    {
        "name": "azure_security_get_secret",
        "description": "[PLANNED] Get Key Vault secret. Not yet implemented - use azure_cli_run.",
        "handler_path": "mcp_tools_core.tools.azure.security.azure_security_get_secret",
        "tags": "azure,security,keyvault,secrets,planned",
        "input_schema": {"type": "object", "properties": {}, "required": []},
        "is_active": False
    },
    {
        "name": "azure_security_assign_role_to_principal",
        "description": "[PLANNED] Assign RBAC role. Not yet implemented - use azure_cli_run.",
        "handler_path": "mcp_tools_core.tools.azure.security.azure_security_assign_role_to_principal",
        "tags": "azure,security,rbac,planned",
        "input_schema": {"type": "object", "properties": {}, "required": []},
        "is_active": False
    },
    
    # Compute Stubs
    {
        "name": "azure_compute_create_vm",
        "description": "[PLANNED] Create a VM. Not yet implemented - use azure_cli_run.",
        "handler_path": "mcp_tools_core.tools.azure.compute.azure_compute_create_vm",
        "tags": "azure,compute,vm,planned",
        "input_schema": {"type": "object", "properties": {}, "required": []},
        "is_active": False
    },
    {
        "name": "azure_compute_delete_vm",
        "description": "[PLANNED] Delete a VM. Not yet implemented - use azure_cli_run.",
        "handler_path": "mcp_tools_core.tools.azure.compute.azure_compute_delete_vm",
        "tags": "azure,compute,vm,delete,planned",
        "input_schema": {"type": "object", "properties": {}, "required": []},
        "is_active": False
    },
    {
        "name": "azure_compute_list_vms_in_resource_group",
        "description": "[PLANNED] List VMs in RG. Not yet implemented - use azure_cli_run.",
        "handler_path": "mcp_tools_core.tools.azure.compute.azure_compute_list_vms_in_resource_group",
        "tags": "azure,compute,vm,list,planned",
        "input_schema": {"type": "object", "properties": {}, "required": []},
        "is_active": False
    },
    
    # Kubernetes Stubs
    {
        "name": "azure_kubernetes_create_aks_cluster",
        "description": "[PLANNED] Create AKS cluster. Not yet implemented - use azure_cli_run.",
        "handler_path": "mcp_tools_core.tools.azure.kubernetes.azure_kubernetes_create_aks_cluster",
        "tags": "azure,kubernetes,aks,planned",
        "input_schema": {"type": "object", "properties": {}, "required": []},
        "is_active": False
    },
    {
        "name": "azure_kubernetes_scale_aks_nodepool",
        "description": "[PLANNED] Scale AKS nodepool. Not yet implemented - use azure_cli_run.",
        "handler_path": "mcp_tools_core.tools.azure.kubernetes.azure_kubernetes_scale_aks_nodepool",
        "tags": "azure,kubernetes,aks,scale,planned",
        "input_schema": {"type": "object", "properties": {}, "required": []},
        "is_active": False
    },
    {
        "name": "azure_kubernetes_get_aks_credentials",
        "description": "[PLANNED] Get AKS credentials. Not yet implemented - use azure_cli_run.",
        "handler_path": "mcp_tools_core.tools.azure.kubernetes.azure_kubernetes_get_aks_credentials",
        "tags": "azure,kubernetes,aks,credentials,planned",
        "input_schema": {"type": "object", "properties": {}, "required": []},
        "is_active": False
    },
]


def main():
    print("Registering Azure SDK MCP tools...")
    print("=" * 70)
    
    created_count = 0
    updated_count = 0
    
    # Register Phase 1 tools (active)
    print("\nPhase 1: Implemented Tools")
    print("-" * 70)
    for tool_data in PHASE_1_TOOLS:
        tool, created = Tool.objects.update_or_create(
            name=tool_data["name"],
            defaults={
                "description": tool_data["description"],
                "handler_path": tool_data["handler_path"],
                "tags": tool_data["tags"],
                "input_schema": tool_data["input_schema"],
                "is_active": True,
            }
        )
        action = "Created" if created else "Updated"
        if created:
            created_count += 1
        else:
            updated_count += 1
        print(f"  {action}: {tool.name}")
    
    # Register Phase 2 stubs (inactive)
    print("\nPhase 2: Stub Tools (Inactive)")
    print("-" * 70)
    for tool_data in PHASE_2_STUBS:
        tool, created = Tool.objects.update_or_create(
            name=tool_data["name"],
            defaults={
                "description": tool_data["description"],
                "handler_path": tool_data["handler_path"],
                "tags": tool_data["tags"],
                "input_schema": tool_data["input_schema"],
                "is_active": tool_data.get("is_active", False),
            }
        )
        action = "Created" if created else "Updated"
        if created:
            created_count += 1
        else:
            updated_count += 1
        print(f"  {action}: {tool.name} (inactive)")
    
    print()
    print("=" * 70)
    print(f"Summary: {created_count} created, {updated_count} updated")
    print(f"Phase 1 (active): {len(PHASE_1_TOOLS)} tools")
    print(f"Phase 2 (stubs): {len(PHASE_2_STUBS)} tools")
    print()
    print("Don't forget to restart the jexida-mcp service:")
    print("  sudo systemctl restart jexida-mcp.service")


if __name__ == "__main__":
    main()

