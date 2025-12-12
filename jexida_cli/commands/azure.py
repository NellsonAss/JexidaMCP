"""Azure CLI command handlers.

Provides CLI commands for Azure orchestration flows via MCP tools.
"""

import json
import re
from typing import TYPE_CHECKING, Dict, Any, List, Tuple

if TYPE_CHECKING:
    from ..ui.renderer import Renderer
    from ..mcp_client import MCPClient


def parse_key_value_pairs(args: str) -> Tuple[Dict[str, str], List[str]]:
    """Parse key=value pairs from argument string.
    
    Args:
        args: Argument string like "--tag env=prod --tag owner=me"
        
    Returns:
        Tuple of (parsed_dict, remaining_args)
    """
    result = {}
    remaining = []
    
    # Match key=value patterns
    parts = args.split()
    i = 0
    while i < len(parts):
        part = parts[i]
        if "=" in part and not part.startswith("--"):
            key, value = part.split("=", 1)
            result[key] = value
        elif part.startswith("--") and i + 1 < len(parts) and "=" in parts[i + 1]:
            # Skip flag, next part is key=value
            i += 1
            key, value = parts[i].split("=", 1)
            result[key] = value
        else:
            remaining.append(part)
        i += 1
    
    return result, remaining


def parse_azure_args(args: str) -> Dict[str, Any]:
    """Parse Azure command arguments.
    
    Supports:
    - --flag value
    - --flag=value
    - --no-flag (boolean false)
    - key=value (for tags and params)
    
    Args:
        args: Argument string
        
    Returns:
        Parsed arguments dict
    """
    result = {
        "tags": {},
        "params": {},
        "flags": {},
    }
    
    # Split into tokens
    tokens = args.split()
    i = 0
    
    while i < len(tokens):
        token = tokens[i]
        
        if token.startswith("--no-"):
            # Boolean false flag
            flag_name = token[5:].replace("-", "_")
            result["flags"][flag_name] = False
            
        elif token.startswith("--"):
            # Flag with value
            if "=" in token:
                # --flag=value format
                flag_name, value = token[2:].split("=", 1)
                flag_name = flag_name.replace("-", "_")
            elif i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                # --flag value format
                flag_name = token[2:].replace("-", "_")
                i += 1
                value = tokens[i]
            else:
                # Boolean true flag
                flag_name = token[2:].replace("-", "_")
                result["flags"][flag_name] = True
                i += 1
                continue
            
            # Handle special flags
            if flag_name == "tag":
                if "=" in value:
                    k, v = value.split("=", 1)
                    result["tags"][k] = v
            elif flag_name == "param":
                if "=" in value:
                    k, v = value.split("=", 1)
                    result["params"][k] = v
            else:
                result["flags"][flag_name] = value
        
        i += 1
    
    return result


def handle_azure_help(renderer: "Renderer") -> str:
    """Show Azure command help."""
    help_text = """
[bold]Azure Orchestration Commands[/bold]

[cyan]/azure[/cyan]                              Show this help

[bold]Environment Management:[/bold]
[cyan]/azure create-env[/cyan]                   Create a complete app environment
  --base-name <name>                Base name for resources (required)
  --location <region>               Azure region (required)
  --environment <env>               dev, staging, prod (default: dev)
  --tag key=value                   Add tag (repeatable)

[cyan]/azure add-data[/cyan]                     Add data services to environment
  --resource-group <rg>             Resource group (required)
  --base-name <name>                Base name for resources (required)
  --location <region>               Azure region (required)
  --no-storage                      Skip storage account
  --no-sql                          Skip SQL database

[bold]Deployments:[/bold]
[cyan]/azure deploy[/cyan]                       Deploy ARM template
  --resource-group <rg>             Resource group (required)
  --name <name>                     Deployment name (required)
  --template <path>                 Template file path (required)
  --param key=value                 Parameter (repeatable)

[bold]Status:[/bold]
[cyan]/azure status[/cyan]                       Check Azure connection status

[dim]Examples:[/dim]
  /azure create-env --base-name myapp --location eastus --environment staging
  /azure add-data --resource-group rg-myapp-staging --base-name myapp --location eastus
  /azure deploy --resource-group rg-myapp --name deploy-001 --template ./template.json
"""
    renderer.info(help_text.strip(), title="AZURE COMMANDS")
    return "continue"


def handle_azure_status(renderer: "Renderer", mcp_client: "MCPClient") -> str:
    """Handle /azure status - check Azure connection."""
    renderer.info("Checking Azure connection...", title="AZURE")
    
    result = mcp_client.run_tool("azure_core_get_connection_info", {})
    
    if result.get("success"):
        inner = result.get("result", {})
        if inner.get("is_valid"):
            renderer.success(
                f"Azure connection is configured\n\n"
                f"Subscription: {inner.get('subscription_id', 'not set')}\n"
                f"Tenant: {inner.get('tenant_id', 'not set')}\n"
                f"Auth Method: {inner.get('auth_method', 'unknown')}\n"
                f"Message: {inner.get('message', '')}",
                title="CONNECTION STATUS"
            )
        else:
            renderer.warning(
                f"Azure connection not fully configured\n\n"
                f"Message: {inner.get('message', 'Unknown issue')}",
                title="CONNECTION STATUS"
            )
    else:
        renderer.error(f"Failed to check status: {result.get('error', 'Unknown error')}")
    
    return "continue"


def handle_azure_create_env(renderer: "Renderer", mcp_client: "MCPClient", args: str) -> str:
    """Handle /azure create-env - create app environment."""
    parsed = parse_azure_args(args)
    flags = parsed["flags"]
    tags = parsed["tags"]
    
    # Validate required args
    base_name = flags.get("base_name")
    location = flags.get("location")
    
    if not base_name:
        renderer.error("Missing required argument: --base-name")
        return "continue"
    
    if not location:
        renderer.error("Missing required argument: --location")
        return "continue"
    
    environment = flags.get("environment", "dev")
    
    renderer.info(
        f"Creating app environment...\n\n"
        f"Base Name: {base_name}\n"
        f"Location: {location}\n"
        f"Environment: {environment}",
        title="AZURE CREATE-ENV"
    )
    
    # Call the flow
    result = mcp_client.run_tool("azure_flow_create_app_environment", {
        "base_name": base_name,
        "location": location,
        "environment": environment,
        "tags": tags if tags else None,
    })
    
    if result.get("success"):
        inner = result.get("result", {})
        if inner.get("ok"):
            renderer.success(
                f"{inner.get('summary', 'Environment created')}\n\n"
                f"Web App URL: {inner.get('web_app_url', 'N/A')}",
                title="SUCCESS"
            )
        else:
            renderer.error(f"Flow failed: {inner.get('error', 'Unknown error')}")
    else:
        renderer.error(f"Tool failed: {result.get('error', 'Unknown error')}")
    
    return "continue"


def handle_azure_add_data(renderer: "Renderer", mcp_client: "MCPClient", args: str) -> str:
    """Handle /azure add-data - add data services."""
    parsed = parse_azure_args(args)
    flags = parsed["flags"]
    tags = parsed["tags"]
    
    # Validate required args
    resource_group = flags.get("resource_group")
    base_name = flags.get("base_name")
    location = flags.get("location")
    
    if not resource_group:
        renderer.error("Missing required argument: --resource-group")
        return "continue"
    
    if not base_name:
        renderer.error("Missing required argument: --base-name")
        return "continue"
    
    if not location:
        renderer.error("Missing required argument: --location")
        return "continue"
    
    include_storage = flags.get("storage", True)
    include_sql = flags.get("sql", True)
    
    renderer.info(
        f"Adding data services...\n\n"
        f"Resource Group: {resource_group}\n"
        f"Base Name: {base_name}\n"
        f"Location: {location}\n"
        f"Storage: {'Yes' if include_storage else 'No'}\n"
        f"SQL: {'Yes' if include_sql else 'No'}",
        title="AZURE ADD-DATA"
    )
    
    # Call the flow
    result = mcp_client.run_tool("azure_flow_add_data_services", {
        "resource_group": resource_group,
        "base_name": base_name,
        "location": location,
        "include_storage": include_storage,
        "include_sql": include_sql,
        "tags": tags if tags else None,
    })
    
    if result.get("success"):
        inner = result.get("result", {})
        if inner.get("ok"):
            renderer.success(inner.get("summary", "Data services added"), title="SUCCESS")
        else:
            renderer.error(f"Flow failed: {inner.get('error', 'Unknown error')}")
    else:
        renderer.error(f"Tool failed: {result.get('error', 'Unknown error')}")
    
    return "continue"


def handle_azure_deploy(renderer: "Renderer", mcp_client: "MCPClient", args: str) -> str:
    """Handle /azure deploy - deploy ARM template."""
    parsed = parse_azure_args(args)
    flags = parsed["flags"]
    params = parsed["params"]
    
    # Validate required args
    resource_group = flags.get("resource_group")
    deployment_name = flags.get("name")
    template_path = flags.get("template")
    
    if not resource_group:
        renderer.error("Missing required argument: --resource-group")
        return "continue"
    
    if not deployment_name:
        renderer.error("Missing required argument: --name")
        return "continue"
    
    if not template_path:
        renderer.error("Missing required argument: --template")
        return "continue"
    
    # Load template
    try:
        with open(template_path, 'r') as f:
            template_content = f.read()
    except FileNotFoundError:
        renderer.error(f"Template file not found: {template_path}")
        return "continue"
    except Exception as e:
        renderer.error(f"Failed to read template: {e}")
        return "continue"
    
    renderer.info(
        f"Deploying template...\n\n"
        f"Resource Group: {resource_group}\n"
        f"Deployment Name: {deployment_name}\n"
        f"Template: {template_path}\n"
        f"Parameters: {len(params)} provided",
        title="AZURE DEPLOY"
    )
    
    # Call the flow
    result = mcp_client.run_tool("azure_flow_deploy_standard_template", {
        "resource_group": resource_group,
        "deployment_name": deployment_name,
        "template_source": template_content,
        "parameters": params if params else None,
    })
    
    if result.get("success"):
        inner = result.get("result", {})
        if inner.get("ok"):
            renderer.success(
                f"{inner.get('summary', 'Deployment completed')}\n\n"
                f"State: {inner.get('provisioning_state', 'Unknown')}",
                title="SUCCESS"
            )
        else:
            renderer.error(f"Deployment failed: {inner.get('error', 'Unknown error')}")
    else:
        renderer.error(f"Tool failed: {result.get('error', 'Unknown error')}")
    
    return "continue"

