# Azure MCP Tools Documentation

This document describes the Azure SDK-based MCP tools available in JexidaMCP.

## Overview

JexidaMCP provides comprehensive Azure infrastructure management tools using the Azure SDK. These tools enable:

- Infrastructure provisioning (resource groups, storage, SQL, web apps)
- ARM/Bicep template deployments
- Resource management and discovery
- Monitoring and cost analysis

## Authentication Setup

### Environment Variables

Set these environment variables on the MCP server:

| Variable | Description | Required |
|----------|-------------|----------|
| `AZURE_TENANT_ID` | Azure AD tenant ID | For service principal |
| `AZURE_CLIENT_ID` | Service principal client ID | For service principal |
| `AZURE_CLIENT_SECRET` | Service principal secret | For service principal |
| `AZURE_SUBSCRIPTION_ID` | Default subscription ID | Recommended |

### Authentication Methods

The tools use `DefaultAzureCredential` which tries multiple auth methods:

1. **Environment Variables** - If `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, and `AZURE_TENANT_ID` are set
2. **Managed Identity** - If running on Azure VM/App Service
3. **Azure CLI** - If logged in via `az login`
4. **Visual Studio Code** - If logged in via VS Code extension

#### Quick Setup (Service Principal)

```bash
# Create a service principal
az ad sp create-for-rbac --name "jexidamcp-sp" --role Contributor --scopes /subscriptions/{subscription-id}

# Set environment variables
export AZURE_TENANT_ID="your-tenant-id"
export AZURE_CLIENT_ID="your-client-id"
export AZURE_CLIENT_SECRET="your-secret"
export AZURE_SUBSCRIPTION_ID="your-subscription-id"
```

## Tool Reference

### Core Tools

#### azure_core_get_connection_info

Get current Azure connection status.

```json
// Request
POST /tools/api/tools/azure_core_get_connection_info/run/
{}

// Response
{
  "success": true,
  "subscription_id": "12345678-...",
  "tenant_id": "87654321-...",
  "auth_method": "ServicePrincipal",
  "is_valid": true,
  "message": "Service principal authentication configured"
}
```

#### azure_core_list_subscriptions

List accessible subscriptions.

```json
// Request
POST /tools/api/tools/azure_core_list_subscriptions/run/
{}

// Response
{
  "success": true,
  "subscriptions": [
    {
      "subscription_id": "12345678-...",
      "display_name": "Production",
      "state": "Enabled"
    }
  ],
  "count": 1
}
```

#### azure_core_list_resource_groups

List resource groups in a subscription.

```json
// Request
POST /tools/api/tools/azure_core_list_resource_groups/run/
{
  "subscription_id": "12345678-..."  // optional, uses default
}

// Response
{
  "success": true,
  "resource_groups": [
    {
      "name": "rg-production",
      "location": "eastus",
      "tags": {"Environment": "Production"},
      "provisioning_state": "Succeeded"
    }
  ],
  "count": 1
}
```

#### azure_core_create_resource_group

Create a new resource group.

```json
// Request
POST /tools/api/tools/azure_core_create_resource_group/run/
{
  "name": "rg-myapp",
  "location": "eastus",
  "tags": {"Environment": "Development", "Project": "MyApp"}
}

// Response
{
  "success": true,
  "created": true,
  "name": "rg-myapp",
  "location": "eastus",
  "provisioning_state": "Succeeded"
}
```

#### azure_core_delete_resource_group

Delete a resource group (requires `force=true`).

```json
// Request
POST /tools/api/tools/azure_core_delete_resource_group/run/
{
  "name": "rg-myapp",
  "force": true
}

// Response
{
  "success": true,
  "deleted": true,
  "name": "rg-myapp",
  "message": "Deletion initiated..."
}
```

### Resources Tools

#### azure_resources_get_resource

Get resource details by ID.

```json
// Request
POST /tools/api/tools/azure_resources_get_resource/run/
{
  "resource_id": "/subscriptions/.../resourceGroups/.../providers/Microsoft.Web/sites/myapp"
}

// Response
{
  "success": true,
  "resource": {
    "id": "/subscriptions/...",
    "name": "myapp",
    "type": "Microsoft.Web/sites",
    "location": "eastus",
    "tags": {},
    "properties": {...}
  }
}
```

#### azure_resources_list_by_type

List resources of a specific type.

```json
// Request
POST /tools/api/tools/azure_resources_list_by_type/run/
{
  "resource_type": "Microsoft.Web/sites"
}

// Response
{
  "success": true,
  "resources": [
    {
      "id": "/subscriptions/...",
      "name": "myapp",
      "type": "Microsoft.Web/sites",
      "location": "eastus",
      "resource_group": "rg-production"
    }
  ],
  "count": 1
}
```

#### azure_resources_search

Search resources with Resource Graph.

```json
// Request
POST /tools/api/tools/azure_resources_search/run/
{
  "query": "Resources | where type == 'microsoft.web/sites' | project name, resourceGroup"
}

// Response
{
  "success": true,
  "resources": [
    {"name": "myapp", "resourceGroup": "rg-production"}
  ],
  "count": 1
}
```

### Deployments Tools

#### azure_deployments_deploy_to_resource_group

Deploy an ARM template.

```json
// Request
POST /tools/api/tools/azure_deployments_deploy_to_resource_group/run/
{
  "resource_group": "rg-myapp",
  "deployment_name": "myapp-deploy-001",
  "template": {
    "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
    "contentVersion": "1.0.0.0",
    "resources": [...]
  },
  "parameters": {
    "appName": "myapp"
  }
}

// Response
{
  "success": true,
  "deployment_name": "myapp-deploy-001",
  "provisioning_state": "Succeeded",
  "outputs": [...]
}
```

### App Platform Tools

#### azure_app_platform_create_app_service_plan

Create an App Service plan.

```json
// Request
POST /tools/api/tools/azure_app_platform_create_app_service_plan/run/
{
  "resource_group": "rg-myapp",
  "name": "plan-myapp",
  "location": "eastus",
  "sku": {"name": "B1", "tier": "Basic", "capacity": 1},
  "is_linux": true
}

// Response
{
  "success": true,
  "name": "plan-myapp",
  "sku_name": "B1",
  "sku_tier": "Basic"
}
```

#### azure_app_platform_create_web_app

Create a web app.

```json
// Request
POST /tools/api/tools/azure_app_platform_create_web_app/run/
{
  "resource_group": "rg-myapp",
  "name": "myapp-webapp",
  "plan_name": "plan-myapp",
  "runtime_stack": "PYTHON|3.11"
}

// Response
{
  "success": true,
  "name": "myapp-webapp",
  "default_hostname": "myapp-webapp.azurewebsites.net",
  "state": "Running"
}
```

#### azure_app_platform_update_web_app_settings

Update app settings.

```json
// Request
POST /tools/api/tools/azure_app_platform_update_web_app_settings/run/
{
  "resource_group": "rg-myapp",
  "name": "myapp-webapp",
  "app_settings": {
    "DATABASE_URL": "postgresql://...",
    "SECRET_KEY": "..."
  }
}

// Response
{
  "success": true,
  "settings_updated": 2
}
```

### Data Tools

#### azure_data_create_storage_account

Create a storage account.

```json
// Request
POST /tools/api/tools/azure_data_create_storage_account/run/
{
  "resource_group": "rg-myapp",
  "name": "stmyappprod",
  "location": "eastus",
  "sku": "Standard_LRS"
}

// Response
{
  "success": true,
  "name": "stmyappprod",
  "primary_endpoint": "https://stmyappprod.blob.core.windows.net/"
}
```

#### azure_data_create_sql_server

Create a SQL server.

```json
// Request
POST /tools/api/tools/azure_data_create_sql_server/run/
{
  "resource_group": "rg-myapp",
  "name": "sql-myapp-prod",
  "location": "eastus",
  "admin_login": "sqladmin",
  "admin_password_secret_ref": "azure:sql_admin_password"
}

// Response
{
  "success": true,
  "name": "sql-myapp-prod",
  "fqdn": "sql-myapp-prod.database.windows.net"
}
```

### Monitoring Tools

#### azure_monitoring_get_metrics

Get resource metrics.

```json
// Request
POST /tools/api/tools/azure_monitoring_get_metrics/run/
{
  "resource_id": "/subscriptions/.../Microsoft.Web/sites/myapp",
  "metric_names": ["CpuPercentage", "MemoryPercentage"],
  "timespan": "PT1H",
  "interval": "PT5M"
}

// Response
{
  "success": true,
  "metrics": [
    {
      "name": "CpuPercentage",
      "unit": "Percent",
      "timeseries": [
        {"timestamp": "2024-01-01T12:00:00Z", "average": 5.2}
      ]
    }
  ]
}
```

#### azure_monitoring_query_logs

Query Log Analytics.

```json
// Request
POST /tools/api/tools/azure_monitoring_query_logs/run/
{
  "workspace_id": "12345678-...",
  "kusto_query": "AppExceptions | where timestamp > ago(1h) | take 10"
}

// Response
{
  "success": true,
  "result": {
    "columns": ["timestamp", "message", "severityLevel"],
    "rows": [...],
    "row_count": 10
  }
}
```

### Cost Tools

#### azure_cost_get_summary

Get cost summary.

```json
// Request
POST /tools/api/tools/azure_cost_get_summary/run/
{
  "subscription_id": "12345678-...",
  "time_period": "Last30Days"
}

// Response
{
  "success": true,
  "total_cost": 1234.56,
  "currency": "USD",
  "breakdown": [
    {"name": "rg-production", "cost": 789.00},
    {"name": "rg-staging", "cost": 345.56}
  ]
}
```

#### azure_cost_get_top_cost_drivers

Get top cost drivers.

```json
// Request
POST /tools/api/tools/azure_cost_get_top_cost_drivers/run/
{
  "scope": "/subscriptions/12345678-...",
  "time_period": {"from": "2024-01-01", "to": "2024-01-31"},
  "top_n": 5
}

// Response
{
  "success": true,
  "cost_drivers": [
    {"name": "Virtual Machines", "cost": 500.00, "percentage": 40.5},
    {"name": "Storage", "cost": 300.00, "percentage": 24.3}
  ],
  "total_cost": 1234.56
}
```

## Phase 2 Tools (Planned)

These tools are defined but not yet implemented. Use `azure_cli_run` as a fallback.

### Network Tools
- `azure_network_create_vnet` - Create virtual network
- `azure_network_create_subnet` - Create subnet
- `azure_network_attach_nsg` - Attach NSG
- `azure_network_create_public_ip` - Create public IP
- `azure_network_create_basic_load_balancer` - Create load balancer

### Security Tools
- `azure_security_create_key_vault` - Create Key Vault
- `azure_security_set_secret` - Set secret
- `azure_security_get_secret` - Get secret
- `azure_security_assign_role_to_principal` - Assign RBAC role

### Compute Tools
- `azure_compute_create_vm` - Create VM
- `azure_compute_delete_vm` - Delete VM
- `azure_compute_list_vms_in_resource_group` - List VMs

### Kubernetes Tools
- `azure_kubernetes_create_aks_cluster` - Create AKS cluster
- `azure_kubernetes_scale_aks_nodepool` - Scale node pool
- `azure_kubernetes_get_aks_credentials` - Get kubeconfig

## Error Handling

All tools return consistent error responses:

```json
{
  "success": false,
  "error": "Error message",
  "error_type": "AuthenticationError|NotFoundError|ValidationError|AzureAPIError"
}
```

### Error Types

| Type | Description |
|------|-------------|
| `AuthenticationError` | Azure authentication failed |
| `AuthorizationError` | Insufficient permissions |
| `NotFoundError` | Resource not found |
| `ValidationError` | Invalid input parameters |
| `ConfigurationError` | Missing configuration |
| `AzureAPIError` | General Azure API error |

## Safety Features

1. **Destructive Operations**: Tools that delete resources require `force=true` parameter
2. **Idempotency**: Create operations check for existing resources first
3. **Logging**: All operations are logged with timestamps and durations
4. **Error Wrapping**: Azure SDK exceptions are wrapped in consistent format

## CLI Fallback

For operations not yet covered by SDK tools, use `azure_cli_run`:

```json
POST /tools/api/tools/azure_cli_run/run/
{
  "subscription_id": "12345678-...",
  "command": "vm list --resource-group rg-myapp --output json"
}
```

