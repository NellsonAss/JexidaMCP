# MCP Tool Registration Guide

## Overview

The JexidaMCP platform uses a **self-extending tool registry** where new tools can be registered via the MCP API without requiring SSH access or direct database access.

## Registration Method

**ALWAYS use the `register_mcp_tool` API endpoint** to register new tools. This is the preferred and recommended method.

### API Endpoint

```
POST http://192.168.1.224:8080/tools/api/tools/register_mcp_tool/run/
```

### Request Format

```json
{
  "name": "tool_name",
  "description": "Tool description",
  "handler_path": "mcp_tools_core.tools.category.module.function_name",
  "tags": "tag1,tag2,tag3",
  "input_schema": {
    "type": "object",
    "properties": {
      "param1": {"type": "string", "description": "Parameter description"},
      "param2": {"type": "integer", "description": "Another parameter"}
    },
    "required": ["param1"]
  },
  "is_active": true,
  "restart_service": false
}
```

### Example: PowerShell Registration

```powershell
$body = @{
    name = "unifi_controller_get_config"
    description = "Retrieve full UniFi controller configuration"
    handler_path = "mcp_tools_core.tools.unifi.controller.unifi_controller_get_config"
    tags = "unifi,controller,config"
    input_schema = @{
        type = "object"
        properties = @{
            scope = @{
                type = "string"
                enum = @("all", "networks", "wlans", "firewall", "devices", "vlans", "settings")
                default = "all"
                description = "Configuration scope"
            }
            site_id = @{
                type = "string"
                description = "UniFi site ID (optional)"
            }
        }
        required = @()
    }
    is_active = $true
    restart_service = $false
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Uri "http://192.168.1.224:8080/tools/api/tools/register_mcp_tool/run/" `
    -Method POST -ContentType "application/json" -Body $body
```

### Example: Python Registration

```python
import httpx
import json
from pydantic import BaseModel

def pydantic_to_json_schema(model: type[BaseModel]) -> dict:
    """Convert Pydantic model to JSON Schema."""
    schema = model.model_json_schema()
    return {
        "type": "object",
        "properties": schema.get("properties", {}),
        "required": schema.get("required", []),
    }

# Register tool
payload = {
    "name": "unifi_controller_get_config",
    "description": "Retrieve full UniFi controller configuration",
    "handler_path": "mcp_tools_core.tools.unifi.controller.unifi_controller_get_config",
    "tags": "unifi,controller,config",
    "input_schema": pydantic_to_json_schema(UniFiControllerGetConfigInput),
    "is_active": True,
    "restart_service": False,
}

response = httpx.post(
    "http://192.168.1.224:8080/tools/api/tools/register_mcp_tool/run/",
    json=payload,
    timeout=30
)
result = response.json()
```

## Workflow

1. **Create Tool Code**: Write the tool function in the appropriate module
   - Location: `jexida_dashboard/mcp_tools_core/tools/{category}/{module}.py`
   - Function signature: `async def tool_name(params: InputModel) -> OutputModel:`
   - Use Pydantic models for input/output validation

2. **Deploy Code**: Copy tool files to the server
   ```bash
   scp file.py jexida@192.168.1.224:/opt/jexida-mcp/jexida_dashboard/mcp_tools_core/tools/{category}/
   ```

3. **Register Tool**: Use the API to register the tool
   - Convert Pydantic input model to JSON Schema
   - Call `register_mcp_tool` API endpoint
   - Verify registration success

4. **Restart Service** (if needed):
   ```bash
   ssh jexida@192.168.1.224 "sudo systemctl restart jexida-mcp.service"
   ```

## Important Notes

- **Code must be deployed first**: The registration API validates that the handler function exists
- **Handler path format**: `mcp_tools_core.tools.{category}.{module}.{function_name}`
- **Input schema**: Must be valid JSON Schema (convert from Pydantic models)
- **Tags**: Use comma-separated tags for categorization
- **Service restart**: Only restart after registering all tools (set `restart_service: false` during bulk registration)

## Alternative Methods (NOT RECOMMENDED)

- ❌ Direct database access
- ❌ SSH + manual Django shell
- ❌ Direct file editing

**Always use the API registration method** - it's safer, validated, and the standard approach.

## For LLMs Connecting to MCP

When you need to add a new tool to the JexidaMCP platform:

1. **Create the tool function** with proper Pydantic input/output models
2. **Deploy the code** to the server
3. **Register via API** using `register_mcp_tool` endpoint at `http://192.168.1.224:8080/tools/api/tools/register_mcp_tool/run/`
4. **Verify** the tool appears in the tool list

Do NOT attempt to register tools through other methods. The API registration is the only supported and validated approach.

