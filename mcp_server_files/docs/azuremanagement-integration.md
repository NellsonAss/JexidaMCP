# AzureManagement Integration Guide

This document shows how the AzureManagement Django/HTMX app can call MCP tools on JexidaMCP.

## Overview

The AzureManagement app acts as a control plane UI. It does NOT hold Azure credentials - it calls tools on JexidaMCP which handles authentication and execution.

## API Endpoints

### List Available Tools

```
GET http://192.168.1.224:8080/api/tools
```

Returns a list of all available tools with their schemas.

**Response:**
```json
[
  {
    "name": "azure_cli.run",
    "description": "Execute an Azure CLI command safely with subscription context",
    "tags": ["azure", "cli"],
    "parameters": [
      {"name": "subscription_id", "type": "string", "required": true},
      {"name": "command", "type": "string", "required": true},
      {"name": "dry_run", "type": "boolean", "required": false, "default": false}
    ],
    "returns": [
      {"name": "stdout", "type": "string"},
      {"name": "stderr", "type": "string"},
      {"name": "exit_code", "type": "integer"}
    ]
  },
  ...
]
```

### Execute a Tool

```
POST http://192.168.1.224:8080/api/tools/{tool_name}/execute
Content-Type: application/json

{request body with parameters}
```

**Response:**
```json
{
  "success": true,
  "result": { ... tool output ... }
}
```

Or on error:
```json
{
  "success": false,
  "error": "Error message"
}
```

## Example Calls from Django

### Python Client Example

```python
import httpx

MCP_SERVER = "http://192.168.1.224:8080"

def call_mcp_tool(tool_name: str, params: dict) -> dict:
    """Call an MCP tool and return the result."""
    response = httpx.post(
        f"{MCP_SERVER}/api/tools/{tool_name}/execute",
        json=params,
        timeout=120.0
    )
    response.raise_for_status()
    return response.json()
```

### azure_cli.run Examples

**List resource groups:**
```python
result = call_mcp_tool("azure_cli.run", {
    "subscription_id": "12345678-1234-1234-1234-123456789abc",
    "command": "group list --output json"
})

if result["success"]:
    import json
    resource_groups = json.loads(result["result"]["stdout"])
    for rg in resource_groups:
        print(f"Resource Group: {rg['name']} in {rg['location']}")
```

**Create a resource group (dry run first):**
```python
# First, dry run to see what would be executed
dry_run = call_mcp_tool("azure_cli.run", {
    "subscription_id": "12345678-1234-1234-1234-123456789abc",
    "command": "group create --name my-new-rg --location eastus",
    "dry_run": True
})
print(f"Would execute: {dry_run['result']['command_executed']}")

# Then actually execute
result = call_mcp_tool("azure_cli.run", {
    "subscription_id": "12345678-1234-1234-1234-123456789abc",
    "command": "group create --name my-new-rg --location eastus --output json"
})
```

**List web apps:**
```python
result = call_mcp_tool("azure_cli.run", {
    "subscription_id": "12345678-1234-1234-1234-123456789abc",
    "command": "webapp list --resource-group my-rg --output json"
})
```

### azure_cost.get_summary Examples

**Get monthly costs:**
```python
result = call_mcp_tool("azure_cost.get_summary", {
    "subscription_id": "12345678-1234-1234-1234-123456789abc",
    "time_period": "MonthToDate"
})

if result["success"]:
    cost_data = result["result"]
    print(f"Total: {cost_data['currency']} {cost_data['total_cost']}")
    for item in cost_data["breakdown"]:
        print(f"  {item['name']}: {cost_data['currency']} {item['cost']}")
```

**Get costs for specific resource group:**
```python
result = call_mcp_tool("azure_cost.get_summary", {
    "subscription_id": "12345678-1234-1234-1234-123456789abc",
    "resource_group": "my-production-rg",
    "time_period": "Last30Days"
})
```

### monitor.http_health_probe Examples

**Check web app health:**
```python
result = call_mcp_tool("monitor.http_health_probe", {
    "url": "https://my-app.azurewebsites.net/health",
    "expected_status": 200,
    "timeout_seconds": 10
})

if result["success"]:
    health = result["result"]
    if health["status"] == "healthy":
        print(f"✓ Healthy ({health['response_time_ms']}ms)")
    else:
        print(f"✗ Unhealthy: {health['error']}")
```

**Check multiple endpoints:**
```python
endpoints = [
    "https://app1.azurewebsites.net/health",
    "https://app2.azurewebsites.net/health",
    "https://api.myservice.com/status",
]

for url in endpoints:
    result = call_mcp_tool("monitor.http_health_probe", {
        "url": url,
        "timeout_seconds": 5
    })
    status = result["result"]["status"]
    print(f"{url}: {status}")
```

## Django View Example

```python
# views.py
import httpx
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

MCP_SERVER = "http://192.168.1.224:8080"

@require_http_methods(["POST"])
def list_resource_groups(request):
    """List Azure resource groups via MCP."""
    subscription_id = request.POST.get("subscription_id")
    
    try:
        response = httpx.post(
            f"{MCP_SERVER}/api/tools/azure_cli.run/execute",
            json={
                "subscription_id": subscription_id,
                "command": "group list --output json"
            },
            timeout=60.0
        )
        response.raise_for_status()
        result = response.json()
        
        if result["success"]:
            import json
            rgs = json.loads(result["result"]["stdout"])
            return JsonResponse({"resource_groups": rgs})
        else:
            return JsonResponse({"error": result["error"]}, status=500)
            
    except httpx.RequestError as e:
        return JsonResponse({"error": f"MCP server error: {e}"}, status=503)
```

## HTMX Integration Example

```html
<!-- Template: resource_groups.html -->
<div id="resource-groups">
  <button hx-post="{% url 'list_resource_groups' %}"
          hx-target="#rg-list"
          hx-indicator="#loading">
    Refresh Resource Groups
  </button>
  
  <div id="loading" class="htmx-indicator">Loading...</div>
  
  <div id="rg-list">
    {% for rg in resource_groups %}
    <div class="rg-card">
      <h3>{{ rg.name }}</h3>
      <p>Location: {{ rg.location }}</p>
    </div>
    {% endfor %}
  </div>
</div>
```

## Error Handling

Always handle these error cases:

1. **MCP server unreachable** - Network error, server down
2. **Tool not found** - 404 response
3. **Validation error** - 400 response with details
4. **Tool execution failure** - success=false in response
5. **Azure CLI errors** - Non-zero exit_code in result

```python
def safe_mcp_call(tool_name: str, params: dict) -> tuple[bool, dict]:
    """Safely call MCP tool with error handling."""
    try:
        response = httpx.post(
            f"{MCP_SERVER}/api/tools/{tool_name}/execute",
            json=params,
            timeout=120.0
        )
        
        if response.status_code == 404:
            return False, {"error": f"Tool '{tool_name}' not found"}
        
        if response.status_code == 400:
            return False, {"error": "Invalid parameters", "details": response.json()}
        
        response.raise_for_status()
        result = response.json()
        
        if not result.get("success", False):
            return False, {"error": result.get("error", "Unknown error")}
        
        return True, result["result"]
        
    except httpx.TimeoutException:
        return False, {"error": "Request timed out"}
    except httpx.RequestError as e:
        return False, {"error": f"Connection error: {e}"}
```

## Security Notes

1. **No credentials in AzureManagement** - All Azure auth is on MCP server
2. **Validate subscription IDs** - Only allow known subscriptions
3. **Rate limiting** - Consider adding rate limits to MCP calls
4. **Audit logging** - Log all MCP tool invocations
5. **HTTPS** - Use HTTPS for production MCP server communication

