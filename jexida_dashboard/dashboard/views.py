"""Dashboard views for main pages."""

import asyncio
import httpx
from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings

# Import from core services
import sys
sys.path.insert(0, str(__file__).replace('/jexida_dashboard/dashboard/views.py', ''))
from core.services.monitoring import get_monitoring_data


def home(request):
    """Dashboard home page with comprehensive overview.
    
    Shows:
    - MCP connection status
    - Worker nodes summary with health
    - Jobs summary (running, queued, recent)
    - Secret counts by service
    - Quick actions
    """
    from secrets_app.models import Secret
    from mcp_tools_core.models import Tool, WorkerNode, Job
    
    # Get secret counts dynamically from all service types in the database
    # This allows new categories to appear automatically
    from django.db.models import Count
    
    secret_categories = []
    service_type_counts = (
        Secret.objects
        .values('service_type')
        .annotate(count=Count('id'))
        .order_by('service_type')
    )
    
    # Build category list with display names and styling
    service_type_styles = {
        'azure': {'color': '#0078d4', 'icon': 'cloud'},
        'unifi': {'color': '#00a4e4', 'icon': 'router'},
        'synology': {'color': '#b5b500', 'icon': 'hdd'},
        'n8n': {'color': '#ff6d5a', 'icon': 'diagram-3'},
        'generic': {'color': '#8b949e', 'icon': 'key'},
    }
    
    # Get display names from model choices
    service_type_names = dict(Secret.SERVICE_TYPE_CHOICES)
    
    for item in service_type_counts:
        stype = item['service_type']
        style = service_type_styles.get(stype, {'color': '#8b949e', 'icon': 'key'})
        secret_categories.append({
            'type': stype,
            'name': service_type_names.get(stype, stype.title()),
            'count': item['count'],
            'color': style['color'],
            'icon': style['icon'],
        })
    
    # Also include types with 0 count that are in choices but not in DB
    existing_types = {item['service_type'] for item in service_type_counts}
    for stype, name in Secret.SERVICE_TYPE_CHOICES:
        if stype not in existing_types:
            style = service_type_styles.get(stype, {'color': '#8b949e', 'icon': 'key'})
            secret_categories.append({
                'type': stype,
                'name': name,
                'count': 0,
                'color': style['color'],
                'icon': style['icon'],
            })
    
    # Sort by name for consistent display
    secret_categories.sort(key=lambda x: x['name'])
    
    total_secrets = sum(cat['count'] for cat in secret_categories)
    
    # Get MCP tools summary
    mcp_tools_total = Tool.objects.filter(is_active=True).count()
    
    # Get tool categories by tag
    tool_categories = {}
    for tool in Tool.objects.filter(is_active=True):
        for tag in tool.get_tags_list():
            tag = tag.lower().strip()
            if tag:
                tool_categories[tag] = tool_categories.get(tag, 0) + 1
    
    # Sort by count and take top 5
    top_categories = sorted(
        tool_categories.items(),
        key=lambda x: x[1],
        reverse=True,
    )[:5]
    
    # Get worker nodes summary
    nodes = WorkerNode.objects.all()
    nodes_total = nodes.count()
    nodes_active = nodes.filter(is_active=True).count()
    recent_nodes = nodes.order_by("-last_seen")[:3]
    
    # Get jobs summary
    jobs_total = Job.objects.count()
    jobs_running = Job.objects.filter(status=Job.STATUS_RUNNING).count()
    jobs_queued = Job.objects.filter(status=Job.STATUS_QUEUED).count()
    recent_jobs = Job.objects.select_related("target_node").order_by("-created_at")[:5]
    
    # Calculate success rate for recent jobs
    completed_jobs = Job.objects.filter(
        status__in=[Job.STATUS_SUCCEEDED, Job.STATUS_FAILED]
    ).order_by("-created_at")[:20]
    
    if completed_jobs:
        success_count = sum(1 for j in completed_jobs if j.status == Job.STATUS_SUCCEEDED)
        success_rate = int((success_count / len(completed_jobs)) * 100)
    else:
        success_rate = None
    
    # Get MCP server status
    mcp_status = _check_mcp_status()
    
    # Get monitoring data (run async function)
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        monitoring_data = loop.run_until_complete(get_monitoring_data())
        loop.close()
    except Exception:
        monitoring_data = {}
    
    return render(request, "dashboard/home.html", {
        "page_title": "Dashboard",
        # Secrets (dynamic categories)
        "secret_categories": secret_categories,
        "total_secrets": total_secrets,
        # MCP Tools
        "mcp_tools_total": mcp_tools_total,
        "top_categories": top_categories,
        "mcp_status": mcp_status,
        # Nodes
        "nodes_total": nodes_total,
        "nodes_active": nodes_active,
        "recent_nodes": recent_nodes,
        # Jobs
        "jobs_total": jobs_total,
        "jobs_running": jobs_running,
        "jobs_queued": jobs_queued,
        "recent_jobs": recent_jobs,
        "success_rate": success_rate,
        # Monitoring
        "monitoring_data": monitoring_data,
    })


def _check_mcp_status():
    """Check if MCP server (this server) is responding.
    
    Returns a dict with status info.
    """
    # Since we ARE the MCP server, we check internal health
    from mcp_tools_core.models import Tool
    from core.providers import get_provider
    
    try:
        tool_count = Tool.objects.filter(is_active=True).count()
        provider = get_provider()
        
        return {
            "connected": True,
            "tools_available": tool_count,
            "provider": provider.provider_name,
            "provider_configured": provider.is_configured(),
            "model": getattr(provider, "default_model", "unknown"),
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
        }


def monitoring(request):
    """Monitoring dashboard with live data."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        monitoring_data = loop.run_until_complete(get_monitoring_data())
        loop.close()
    except Exception:
        monitoring_data = {}
    
    return render(request, "dashboard/monitoring.html", {
        "page_title": "Monitoring",
        "monitoring_data": monitoring_data,
    })


def health(request):
    """Health check endpoint."""
    from mcp_tools_core.models import Tool, WorkerNode, Job
    
    return JsonResponse({
        "status": "healthy",
        "version": "0.1.0",
        "mcp_tools": Tool.objects.filter(is_active=True).count(),
        "worker_nodes": WorkerNode.objects.filter(is_active=True).count(),
        "active_jobs": Job.objects.filter(status=Job.STATUS_RUNNING).count(),
    })


def models_view(request):
    """Models and orchestration selection page.
    
    Shows available LLM models/strategies and allows selection.
    """
    from core.providers import get_provider
    from mcp_tools_core.models import Fact
    
    provider = get_provider()
    
    # Get current model configuration from Facts
    try:
        model_fact = Fact.objects.get(key="config.active_model")
        current_model = model_fact.value.get("model_id", provider.default_model)
        current_mode = model_fact.value.get("mode", "direct")
    except Fact.DoesNotExist:
        current_model = getattr(provider, "default_model", "default")
        current_mode = "direct"
    
    # Define available models (these would come from config/discovery in production)
    available_models = [
        {
            "id": "gpt-4",
            "name": "GPT-4",
            "source": "cloud",
            "provider": "openai",
            "description": "Most capable OpenAI model",
        },
        {
            "id": "gpt-3.5-turbo",
            "name": "GPT-3.5 Turbo", 
            "source": "cloud",
            "provider": "openai",
            "description": "Fast and cost-effective",
        },
        {
            "id": "llama3:latest",
            "name": "Llama 3",
            "source": "local",
            "provider": "ollama",
            "description": "Local model via Ollama",
        },
        {
            "id": "phi3:latest",
            "name": "Phi-3",
            "source": "local",
            "provider": "ollama",
            "description": "Compact local model",
        },
        {
            "id": "mock",
            "name": "Mock Provider",
            "source": "local",
            "provider": "mock",
            "description": "Testing provider (no API needed)",
        },
    ]
    
    # Available orchestration modes
    modes = [
        {
            "id": "direct",
            "name": "Direct",
            "description": "Use the selected model directly",
            "icon": "arrow-right",
        },
        {
            "id": "cascade",
            "name": "Cascade",
            "description": "Try cheaper models first, fall back to expensive ones",
            "icon": "sort-down",
        },
        {
            "id": "router",
            "name": "Router",
            "description": "Automatically route to the best model for each task",
            "icon": "signpost-split",
        },
    ]
    
    return render(request, "dashboard/models.html", {
        "page_title": "Models & Orchestration",
        "provider": provider,
        "current_model": current_model,
        "current_mode": current_mode,
        "available_models": available_models,
        "modes": modes,
    })


def models_set(request):
    """Set the active model and orchestration mode.
    
    Accepts POST with model_id and mode.
    """
    from mcp_tools_core.models import Fact
    from django.contrib import messages
    from django.shortcuts import redirect
    
    if request.method != "POST":
        return redirect("dashboard:models")
    
    model_id = request.POST.get("model_id")
    mode = request.POST.get("mode", "direct")
    
    if not model_id:
        messages.error(request, "No model selected")
        return redirect("dashboard:models")
    
    # Save to Facts
    Fact.objects.update_or_create(
        key="config.active_model",
        defaults={
            "value": {
                "model_id": model_id,
                "mode": mode,
            },
            "source": "dashboard",
        },
    )
    
    messages.success(request, f"Model set to {model_id} in {mode} mode")
    
    # For HTMX requests, return a partial
    if request.headers.get("HX-Request"):
        return render(request, "dashboard/partials/model_status.html", {
            "current_model": model_id,
            "current_mode": mode,
            "success": True,
        })
    
    return redirect("dashboard:models")


def network_hardening(request):
    """Network hardening dashboard with UniFi evaluations.
    
    Shows available security evaluations and their status.
    """
    from mcp_tools_core.models import Tool, Fact, ExecutionLog
    
    # Define available evaluations based on UniFi security tools
    evaluations = [
        {
            "id": "vlan_architecture",
            "name": "VLAN Architecture",
            "description": "Evaluate network segmentation, VLAN isolation, and guest networks",
            "tool": "security_audit_unifi",
            "section": 1,
            "icon": "diagram-3",
        },
        {
            "id": "wifi_hardening",
            "name": "WiFi Hardening",
            "description": "Check WPA3, PMF, legacy protocols, and VLAN assignment",
            "tool": "security_audit_unifi",
            "section": 2,
            "icon": "wifi",
        },
        {
            "id": "firewall_rules",
            "name": "Firewall Rules",
            "description": "Analyze inter-VLAN rules, allow-all detection, rule validation",
            "tool": "security_audit_unifi",
            "section": 3,
            "icon": "shield-lock",
        },
        {
            "id": "threat_management",
            "name": "Threat Management",
            "description": "Verify IDS/IPS settings, mode, and threat categories",
            "tool": "security_audit_unifi",
            "section": 4,
            "icon": "shield-exclamation",
        },
        {
            "id": "dns_dhcp",
            "name": "DNS/DHCP Protection",
            "description": "Check UPnP, NAT-PMP, and DNS server configuration",
            "tool": "security_audit_unifi",
            "section": 5,
            "icon": "globe",
        },
        {
            "id": "switch_ap",
            "name": "Switch & AP Settings",
            "description": "Audit unused ports, PoE configuration, channel settings",
            "tool": "security_audit_unifi",
            "section": 6,
            "icon": "router",
        },
        {
            "id": "remote_access",
            "name": "Remote Access",
            "description": "Check SSH, cloud access, WAN UI, and MFA settings",
            "tool": "security_audit_unifi",
            "section": 7,
            "icon": "key",
        },
        {
            "id": "backups_drift",
            "name": "Backups & Drift",
            "description": "Verify backup status and configuration drift protection",
            "tool": "security_audit_unifi",
            "section": 8,
            "icon": "cloud-arrow-up",
        },
    ]
    
    # Get last execution status for each
    for eval_info in evaluations:
        fact_key = f"hardening.{eval_info['id']}.last_run"
        try:
            fact = Fact.objects.get(key=fact_key)
            eval_info["last_run"] = fact.value.get("run_at")
            eval_info["last_status"] = fact.value.get("status", "unknown")
            eval_info["finding_count"] = fact.value.get("finding_count", 0)
        except Fact.DoesNotExist:
            eval_info["last_run"] = None
            eval_info["last_status"] = "never"
            eval_info["finding_count"] = 0
    
    # Check if security_audit_unifi tool exists
    tool_available = Tool.objects.filter(
        name="security_audit_unifi",
        is_active=True
    ).exists()
    
    return render(request, "dashboard/network_hardening.html", {
        "page_title": "Network Hardening",
        "evaluations": evaluations,
        "tool_available": tool_available,
    })


def run_evaluation(request, evaluation):
    """Run a specific security evaluation.
    
    This triggers the security_audit_unifi tool and stores results.
    """
    from mcp_tools_core.executor import execute_tool
    from mcp_tools_core.models import Fact
    from django.utils import timezone
    import json
    
    if request.method != "POST" and not request.headers.get("HX-Request"):
        return redirect("dashboard:network_hardening")
    
    # Map evaluation ID to section number
    section_map = {
        "vlan_architecture": 1,
        "wifi_hardening": 2,
        "firewall_rules": 3,
        "threat_management": 4,
        "dns_dhcp": 5,
        "switch_ap": 6,
        "remote_access": 7,
        "backups_drift": 8,
    }
    
    section = section_map.get(evaluation)
    if not section:
        return render(request, "dashboard/partials/evaluation_result.html", {
            "success": False,
            "error": f"Unknown evaluation: {evaluation}",
            "evaluation": evaluation,
        })
    
    # Run the security audit tool
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(execute_tool(
            "security_audit_unifi",
            {"depth": "quick", "sections": [section]},
        ))
        loop.close()
        
        # Store the result
        findings = result.get("findings", [])
        Fact.objects.update_or_create(
            key=f"hardening.{evaluation}.last_run",
            defaults={
                "value": {
                    "run_at": timezone.now().isoformat(),
                    "status": "pass" if len(findings) == 0 else "findings",
                    "finding_count": len(findings),
                    "risk_score": result.get("risk_score", {}).get("score", 0),
                },
                "source": "network_hardening",
            },
        )
        
        # Store detailed results
        Fact.objects.update_or_create(
            key=f"hardening.{evaluation}.results",
            defaults={
                "value": result,
                "source": "network_hardening",
            },
        )
        
        return render(request, "dashboard/partials/evaluation_result.html", {
            "success": True,
            "evaluation": evaluation,
            "result": result,
            "findings": findings,
            "risk_score": result.get("risk_score", {}),
        })
        
    except Exception as e:
        return render(request, "dashboard/partials/evaluation_result.html", {
            "success": False,
            "error": str(e),
            "evaluation": evaluation,
        })


# =============================================================================
# Azure Flow Views
# =============================================================================

def azure_dashboard(request):
    """Azure flows dashboard with status and quick actions.
    
    Shows:
    - Azure connection status
    - Available flows
    - Recent operations
    """
    from mcp_tools_core.models import Tool, ExecutionLog
    from mcp_tools_core.executor import execute_tool
    
    # Check Azure connection status
    azure_status = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(execute_tool(
            "azure_core_get_connection_info",
            {},
        ))
        loop.close()
        azure_status = {
            "connected": result.get("success", False) and result.get("is_valid", False),
            "subscription_id": result.get("subscription_id", ""),
            "tenant_id": result.get("tenant_id", ""),
            "auth_method": result.get("auth_method", ""),
            "message": result.get("message", ""),
        }
    except Exception as e:
        azure_status = {
            "connected": False,
            "error": str(e),
        }
    
    # Get available Azure flow tools
    azure_flows = [
        {
            "id": "create_app_environment",
            "name": "Create App Environment",
            "description": "Creates Resource Group + App Service Plan + Web App",
            "tool": "azure_flow_create_app_environment",
            "icon": "cloud-plus",
            "color": "#0078d4",
        },
        {
            "id": "add_data_services",
            "name": "Add Data Services",
            "description": "Add Storage Account, SQL Server, and Database",
            "tool": "azure_flow_add_data_services",
            "icon": "database",
            "color": "#00a4e4",
        },
        {
            "id": "deploy_template",
            "name": "Deploy Template",
            "description": "Deploy an ARM/Bicep template",
            "tool": "azure_flow_deploy_standard_template",
            "icon": "file-earmark-code",
            "color": "#3fb950",
        },
    ]
    
    # Get recent Azure operations
    recent_logs = ExecutionLog.objects.filter(
        tool__name__startswith="azure_flow_"
    ).select_related("tool").order_by("-run_at")[:10]
    
    # Get resource groups for selection
    resource_groups = []
    if azure_status.get("connected"):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            rg_result = loop.run_until_complete(execute_tool(
                "azure_core_list_resource_groups",
                {},
            ))
            loop.close()
            if rg_result.get("success"):
                resource_groups = rg_result.get("resource_groups", [])
        except Exception:
            pass
    
    return render(request, "dashboard/azure.html", {
        "page_title": "Azure",
        "azure_status": azure_status,
        "azure_flows": azure_flows,
        "recent_logs": recent_logs,
        "resource_groups": resource_groups,
    })


def azure_create_env(request):
    """Azure Create App Environment form and handler."""
    from mcp_tools_core.executor import execute_tool
    from mcp_tools_core.models import ExecutionLog
    
    if request.method == "POST":
        # Get form data
        base_name = request.POST.get("base_name", "").strip()
        location = request.POST.get("location", "eastus")
        environment = request.POST.get("environment", "dev")
        
        # Parse tags from form
        tags = {}
        tag_keys = request.POST.getlist("tag_key")
        tag_values = request.POST.getlist("tag_value")
        for key, value in zip(tag_keys, tag_values):
            if key and value:
                tags[key] = value
        
        # Validate
        if not base_name:
            return render(request, "dashboard/partials/azure_result.html", {
                "success": False,
                "error": "Base name is required",
            })
        
        # Execute the flow
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(execute_tool(
                "azure_flow_create_app_environment",
                {
                    "base_name": base_name,
                    "location": location,
                    "environment": environment,
                    "tags": tags if tags else None,
                },
            ))
            loop.close()
            
            return render(request, "dashboard/partials/azure_result.html", {
                "success": result.get("ok", False),
                "result": result,
                "error": result.get("error", ""),
                "flow": "create_app_environment",
            })
        except Exception as e:
            return render(request, "dashboard/partials/azure_result.html", {
                "success": False,
                "error": str(e),
            })
    
    # GET - show form
    locations = [
        {"id": "eastus", "name": "East US"},
        {"id": "eastus2", "name": "East US 2"},
        {"id": "westus", "name": "West US"},
        {"id": "westus2", "name": "West US 2"},
        {"id": "centralus", "name": "Central US"},
        {"id": "northeurope", "name": "North Europe"},
        {"id": "westeurope", "name": "West Europe"},
        {"id": "uksouth", "name": "UK South"},
        {"id": "australiaeast", "name": "Australia East"},
    ]
    
    return render(request, "dashboard/azure_create_env.html", {
        "page_title": "Create App Environment",
        "locations": locations,
    })


def azure_add_data(request):
    """Azure Add Data Services form and handler."""
    from mcp_tools_core.executor import execute_tool
    
    if request.method == "POST":
        resource_group = request.POST.get("resource_group", "").strip()
        base_name = request.POST.get("base_name", "").strip()
        location = request.POST.get("location", "eastus")
        include_storage = request.POST.get("include_storage") == "on"
        include_sql = request.POST.get("include_sql") == "on"
        
        # Validate
        if not resource_group or not base_name:
            return render(request, "dashboard/partials/azure_result.html", {
                "success": False,
                "error": "Resource group and base name are required",
            })
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(execute_tool(
                "azure_flow_add_data_services",
                {
                    "resource_group": resource_group,
                    "base_name": base_name,
                    "location": location,
                    "include_storage": include_storage,
                    "include_sql": include_sql,
                },
            ))
            loop.close()
            
            return render(request, "dashboard/partials/azure_result.html", {
                "success": result.get("ok", False),
                "result": result,
                "error": result.get("error", ""),
                "flow": "add_data_services",
            })
        except Exception as e:
            return render(request, "dashboard/partials/azure_result.html", {
                "success": False,
                "error": str(e),
            })
    
    # GET - show form with resource groups
    resource_groups = []
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        rg_result = loop.run_until_complete(execute_tool(
            "azure_core_list_resource_groups",
            {},
        ))
        loop.close()
        if rg_result.get("success"):
            resource_groups = rg_result.get("resource_groups", [])
    except Exception:
        pass
    
    locations = [
        {"id": "eastus", "name": "East US"},
        {"id": "eastus2", "name": "East US 2"},
        {"id": "westus", "name": "West US"},
        {"id": "westus2", "name": "West US 2"},
        {"id": "centralus", "name": "Central US"},
        {"id": "northeurope", "name": "North Europe"},
        {"id": "westeurope", "name": "West Europe"},
    ]
    
    return render(request, "dashboard/azure_add_data.html", {
        "page_title": "Add Data Services",
        "resource_groups": resource_groups,
        "locations": locations,
    })


def azure_deploy(request):
    """Azure Deploy Template form and handler."""
    from mcp_tools_core.executor import execute_tool
    
    if request.method == "POST":
        resource_group = request.POST.get("resource_group", "").strip()
        deployment_name = request.POST.get("deployment_name", "").strip()
        template_source = request.POST.get("template_source", "").strip()
        
        # Parse parameters from form
        parameters = {}
        param_keys = request.POST.getlist("param_key")
        param_values = request.POST.getlist("param_value")
        for key, value in zip(param_keys, param_values):
            if key and value:
                parameters[key] = value
        
        # Validate
        if not resource_group or not deployment_name or not template_source:
            return render(request, "dashboard/partials/azure_result.html", {
                "success": False,
                "error": "Resource group, deployment name, and template are required",
            })
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(execute_tool(
                "azure_flow_deploy_standard_template",
                {
                    "resource_group": resource_group,
                    "deployment_name": deployment_name,
                    "template_source": template_source,
                    "parameters": parameters if parameters else None,
                },
            ))
            loop.close()
            
            return render(request, "dashboard/partials/azure_result.html", {
                "success": result.get("ok", False),
                "result": result,
                "error": result.get("error", ""),
                "flow": "deploy_standard_template",
            })
        except Exception as e:
            return render(request, "dashboard/partials/azure_result.html", {
                "success": False,
                "error": str(e),
            })
    
    # GET - show form with resource groups
    resource_groups = []
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        rg_result = loop.run_until_complete(execute_tool(
            "azure_core_list_resource_groups",
            {},
        ))
        loop.close()
        if rg_result.get("success"):
            resource_groups = rg_result.get("resource_groups", [])
    except Exception:
        pass
    
    return render(request, "dashboard/azure_deploy.html", {
        "page_title": "Deploy Template",
        "resource_groups": resource_groups,
    })


# =============================================================================
# Discord Views
# =============================================================================

def discord_dashboard(request):
    """Discord management dashboard.
    
    Shows:
    - Discord connection status
    - Server info (guild name, channels, roles)
    - Quick actions (test, bootstrap, send message)
    """
    from mcp_tools_core.executor import execute_tool
    from mcp_tools_core.models import Tool
    
    # Check Discord connection status
    discord_status = None
    guild_info = {}
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(execute_tool(
            "discord_get_guild_info",
            {},
        ))
        loop.close()
        
        if result.get("ok"):
            discord_status = {
                "connected": True,
                "guild_id": result.get("guild_id", ""),
                "guild_name": result.get("name", "Unknown"),
                "member_count": result.get("member_count", 0),
            }
            guild_info = result.get("raw", {})
        else:
            error = result.get("error", "Unknown error")
            discord_status = {
                "connected": False,
                "error": error,
                "is_config_error": "not configured" in error.lower() or "missing" in error.lower(),
            }
    except Exception as e:
        discord_status = {
            "connected": False,
            "error": str(e),
            "is_config_error": True,
        }
    
    # Get channel and role counts from guild info
    channels = guild_info.get("channels", []) if guild_info else []
    roles = guild_info.get("roles", []) if guild_info else []
    
    # Categorize channels
    categories = [ch for ch in channels if ch.get("type") == 4]
    text_channels = [ch for ch in channels if ch.get("type") == 0]
    voice_channels = [ch for ch in channels if ch.get("type") == 2]
    
    # Filter out @everyone from roles
    custom_roles = [r for r in roles if r.get("name") != "@everyone"]
    
    # Check if Discord tools are available
    discord_tools = Tool.objects.filter(
        name__startswith="discord_",
        is_active=True
    )
    
    return render(request, "dashboard/discord.html", {
        "page_title": "Discord",
        "discord_status": discord_status,
        "guild_info": guild_info,
        "categories": categories,
        "text_channels": text_channels,
        "voice_channels": voice_channels,
        "custom_roles": custom_roles,
        "discord_tools": discord_tools,
    })


def discord_test(request):
    """Test Discord connection via HTMX."""
    from mcp_tools_core.executor import execute_tool
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(execute_tool(
            "discord_get_guild_info",
            {},
        ))
        loop.close()
        
        return render(request, "dashboard/partials/discord_test_result.html", {
            "success": result.get("ok", False),
            "result": result,
            "error": result.get("error", ""),
        })
    except Exception as e:
        return render(request, "dashboard/partials/discord_test_result.html", {
            "success": False,
            "error": str(e),
        })


def discord_bootstrap(request):
    """Run Discord bootstrap via HTMX."""
    from mcp_tools_core.executor import execute_tool
    
    dry_run = request.GET.get("dry_run", "false").lower() == "true"
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(execute_tool(
            "discord_bootstrap_server",
            {"dry_run": dry_run},
        ))
        loop.close()
        
        return render(request, "dashboard/partials/discord_bootstrap_result.html", {
            "success": result.get("ok", False),
            "result": result,
            "dry_run": dry_run,
            "error": result.get("error", ""),
        })
    except Exception as e:
        return render(request, "dashboard/partials/discord_bootstrap_result.html", {
            "success": False,
            "error": str(e),
        })


def discord_send_message(request):
    """Send a message to Discord via HTMX."""
    from mcp_tools_core.executor import execute_tool
    
    if request.method != "POST":
        return render(request, "dashboard/partials/discord_message_result.html", {
            "success": False,
            "error": "POST required",
        })
    
    channel_id = request.POST.get("channel_id", "").strip()
    content = request.POST.get("content", "").strip()
    
    if not channel_id or not content:
        return render(request, "dashboard/partials/discord_message_result.html", {
            "success": False,
            "error": "Channel ID and message content are required",
        })
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(execute_tool(
            "discord_send_message",
            {"channel_id": channel_id, "content": content},
        ))
        loop.close()
        
        return render(request, "dashboard/partials/discord_message_result.html", {
            "success": result.get("ok", False),
            "result": result,
            "error": result.get("error", ""),
        })
    except Exception as e:
        return render(request, "dashboard/partials/discord_message_result.html", {
            "success": False,
            "error": str(e),
        })


# =============================================================================
# Patreon Views
# =============================================================================

def patreon_dashboard(request):
    """Patreon management dashboard.
    
    Shows:
    - Patreon connection status
    - Creator/campaign info
    - Tier list with patron counts
    - Patron list with filtering
    """
    from mcp_tools_core.executor import execute_tool
    from mcp_tools_core.models import Tool
    
    # Check Patreon connection and get creator info
    patreon_status = None
    creator_info = {}
    tiers = []
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(execute_tool(
            "patreon_get_creator",
            {},
        ))
        loop.close()
        
        if result.get("success"):
            patreon_status = {
                "connected": True,
                "creator_id": result.get("creator_id", ""),
                "creator_name": result.get("creator_name", "Unknown"),
                "creator_email": result.get("creator_email", ""),
            }
            creator_info = result
            
            # Get campaign info
            campaign = result.get("campaign")
            if campaign:
                patreon_status["campaign_id"] = campaign.get("id", "")
                patreon_status["campaign_name"] = campaign.get("name", "")
                patreon_status["patron_count"] = campaign.get("patron_count", 0)
        else:
            error = result.get("error", "Unknown error")
            patreon_status = {
                "connected": False,
                "error": error,
                "is_config_error": "not configured" in error.lower() or "missing" in error.lower() or "credentials" in error.lower(),
            }
    except Exception as e:
        patreon_status = {
            "connected": False,
            "error": str(e),
            "is_config_error": True,
        }
    
    # Get tiers if connected
    if patreon_status.get("connected"):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            tier_result = loop.run_until_complete(execute_tool(
                "patreon_get_tiers",
                {},
            ))
            loop.close()
            
            if tier_result.get("success"):
                tiers = tier_result.get("tiers", [])
        except Exception:
            pass
    
    # Check if Patreon tools are available
    patreon_tools = Tool.objects.filter(
        name__startswith="patreon_",
        is_active=True
    )
    
    return render(request, "dashboard/patreon.html", {
        "page_title": "Patreon",
        "patreon_status": patreon_status,
        "creator_info": creator_info,
        "tiers": tiers,
        "patreon_tools": patreon_tools,
    })


def patreon_get_patrons(request):
    """Get patrons via HTMX with filtering."""
    from mcp_tools_core.executor import execute_tool
    
    status_filter = request.GET.get("status_filter", "")
    tier_filter = request.GET.get("tier_filter", "")
    
    params = {}
    if status_filter:
        params["status_filter"] = status_filter
    if tier_filter:
        params["tier_filter"] = tier_filter
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(execute_tool(
            "patreon_get_patrons",
            params,
        ))
        loop.close()
        
        return render(request, "dashboard/partials/patreon_patrons.html", {
            "success": result.get("success", False),
            "patrons": result.get("patrons", []),
            "count": result.get("count", 0),
            "total_monthly_cents": result.get("total_monthly_cents", 0),
            "error": result.get("error", ""),
        })
    except Exception as e:
        return render(request, "dashboard/partials/patreon_patrons.html", {
            "success": False,
            "error": str(e),
        })


def patreon_export(request):
    """Export patrons via HTMX."""
    from mcp_tools_core.executor import execute_tool
    from django.http import HttpResponse
    
    export_format = request.GET.get("format", "csv")
    status_filter = request.GET.get("status_filter", "")
    
    params = {"format": export_format}
    if status_filter:
        params["status_filter"] = status_filter
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(execute_tool(
            "patreon_export_patrons",
            params,
        ))
        loop.close()
        
        if result.get("success"):
            if export_format == "csv":
                response = HttpResponse(result.get("data", ""), content_type="text/csv")
                response["Content-Disposition"] = 'attachment; filename="patrons.csv"'
                return response
            else:
                response = HttpResponse(result.get("data", "{}"), content_type="application/json")
                response["Content-Disposition"] = 'attachment; filename="patrons.json"'
                return response
        else:
            return render(request, "dashboard/partials/patreon_export_result.html", {
                "success": False,
                "error": result.get("error", "Export failed"),
            })
    except Exception as e:
        return render(request, "dashboard/partials/patreon_export_result.html", {
            "success": False,
            "error": str(e),
        })