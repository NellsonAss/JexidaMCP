# Azure Tools Documentation

This document describes the Azure-related MCP tools available in JexidaMCP.

## Overview

JexidaMCP provides three Azure tools in Phase 1:

1. **azure_cli.run** - Execute Azure CLI commands safely
2. **azure_cost.get_summary** - Get cost summaries for subscriptions
3. **monitor.http_health_probe** - Check HTTP endpoint health

## Authentication Setup

### Option 1: Azure CLI Login (Interactive)

For development and testing, use interactive login:

```bash
az login
```

This opens a browser for authentication. The session persists until logout.

### Option 2: Service Principal (Automated)

For production/automated scenarios, use a service principal:

1. Create a service principal:
   ```bash
   az ad sp create-for-rbac --name "jexidamcp-sp" --role Contributor
   ```

2. Set environment variables:
   ```bash
   export AZURE_TENANT_ID="your-tenant-id"
   export AZURE_CLIENT_ID="your-client-id"
   export AZURE_CLIENT_SECRET="your-client-secret"
   ```

3. Login with service principal:
   ```bash
   az login --service-principal -u $AZURE_CLIENT_ID -p $AZURE_CLIENT_SECRET --tenant $AZURE_TENANT_ID
   ```

### Option 3: Managed Identity (Azure VMs)

If running on an Azure VM with managed identity:

```bash
az login --identity
```

No credentials needed - Azure handles authentication automatically.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AZURE_CLI_PATH` | Path to Azure CLI binary | `az` |
| `AZURE_CLI_TIMEOUT` | Command timeout in seconds | `300` |
| `AZURE_COMMAND_MAX_LENGTH` | Maximum command length | `4096` |
| `AZURE_TENANT_ID` | Azure tenant ID | (none) |
| `AZURE_CLIENT_ID` | Azure client ID | (none) |
| `AZURE_CLIENT_SECRET` | Azure client secret | (none) |
| `AZURE_DEFAULT_SUBSCRIPTION` | Default subscription ID | (none) |

## Tool Reference

### azure_cli.run

Execute Azure CLI commands with subscription context.

**Input Schema:**
```json
{
  "subscription_id": "string (GUID format, required)",
  "command": "string (az command without 'az' prefix, required)",
  "dry_run": "boolean (default: false)"
}
```

**Output Schema:**
```json
{
  "stdout": "string",
  "stderr": "string",
  "exit_code": "integer",
  "command_executed": "string (full command, only in dry_run mode)"
}
```

**Security:**
- Commands are sanitized to prevent shell injection
- Dangerous patterns are rejected: `;`, `&&`, `|`, `>`, `<`, backticks, `$()`
- Command length is limited (default 4096 characters)
- Timeouts prevent hanging commands

**Example:**
```json
// Request
{
  "subscription_id": "12345678-1234-1234-1234-123456789abc",
  "command": "group list --output json",
  "dry_run": false
}

// Response
{
  "stdout": "[{\"name\": \"my-resource-group\", ...}]",
  "stderr": "",
  "exit_code": 0
}
```

### azure_cost.get_summary

Get cost summary for a subscription or resource group.

> **Note:** Currently returns mock data. Real Azure Cost Management API integration is planned.

**Input Schema:**
```json
{
  "subscription_id": "string (GUID format, required)",
  "resource_group": "string (optional)",
  "time_period": "enum: Last7Days | Last30Days | MonthToDate (default: Last30Days)"
}
```

**Output Schema:**
```json
{
  "total_cost": "number",
  "currency": "string",
  "breakdown": [
    {"name": "string", "cost": "number"}
  ],
  "time_period": "string",
  "is_mock_data": "boolean"
}
```

**Example:**
```json
// Request
{
  "subscription_id": "12345678-1234-1234-1234-123456789abc",
  "time_period": "Last7Days"
}

// Response
{
  "total_cost": 250.98,
  "currency": "USD",
  "breakdown": [
    {"name": "rg-production", "cost": 130.86},
    {"name": "rg-staging", "cost": 39.20},
    {"name": "rg-development", "cost": 22.28},
    {"name": "rg-shared", "cost": 58.64}
  ],
  "time_period": "Last7Days",
  "is_mock_data": true
}
```

### monitor.http_health_probe

Check HTTP endpoint health status.

**Input Schema:**
```json
{
  "url": "string (http/https URL, required)",
  "method": "string (HTTP method, default: GET)",
  "expected_status": "integer (default: 200)",
  "timeout_seconds": "integer (optional)"
}
```

**Output Schema:**
```json
{
  "status": "enum: healthy | unhealthy",
  "http_status": "integer or null",
  "response_time_ms": "integer",
  "error": "string or null"
}
```

**Example:**
```json
// Request
{
  "url": "https://myapp.azurewebsites.net/health",
  "method": "GET",
  "expected_status": 200,
  "timeout_seconds": 10
}

// Response (healthy)
{
  "status": "healthy",
  "http_status": 200,
  "response_time_ms": 145,
  "error": null
}

// Response (unhealthy)
{
  "status": "unhealthy",
  "http_status": 503,
  "response_time_ms": 2034,
  "error": "Expected status 200, got 503"
}
```

## Security Considerations

1. **Secrets are never logged** - stdout/stderr may contain secrets, so they're not included in logs
2. **Command sanitization** - All Azure CLI commands are validated before execution
3. **Environment variables** - Use env vars for credentials, never hardcode
4. **Timeouts** - All operations have configurable timeouts to prevent hanging
5. **Subscription validation** - Subscription IDs are validated as GUIDs

## Troubleshooting

### "Azure CLI not logged in"
Run `az login` on the server to authenticate.

### "Subscription not found"
Verify the subscription ID is correct and accessible:
```bash
az account list --output table
```

### Command timeout
Increase `AZURE_CLI_TIMEOUT` or simplify the command.

### "Command contains dangerous pattern"
The command includes shell operators that are blocked for security.
Restructure the command to avoid `;`, `&&`, `|`, etc.

