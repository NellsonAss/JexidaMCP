"""Views for MCP Tools Core app.

Provides both web UI views (HTMX-enabled) and REST API endpoints.
"""

import asyncio
import json
import logging

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from .models import Tool, ToolRequest, ExecutionLog, Fact
from .executor import execute_tool, ToolNotFoundError, ToolExecutionError

logger = logging.getLogger(__name__)


# =============================================================================
# Web UI Views (HTMX)
# =============================================================================

def tool_list(request):
    """List all registered tools with run buttons."""
    tools = Tool.objects.all().order_by("name")
    
    # Get filter parameters
    tag_filter = request.GET.get("tag", "")
    active_filter = request.GET.get("active", "")
    
    if tag_filter:
        tools = tools.filter(tags__icontains=tag_filter)
    if active_filter == "true":
        tools = tools.filter(is_active=True)
    elif active_filter == "false":
        tools = tools.filter(is_active=False)
    
    # Get unique tags for filter dropdown
    all_tags = set()
    for tool in Tool.objects.values_list("tags", flat=True):
        if tool:
            all_tags.update(t.strip() for t in tool.split(","))
    
    return render(request, "mcp_tools/list.html", {
        "page_title": "MCP Tools",
        "tools": tools,
        "tag_filter": tag_filter,
        "active_filter": active_filter,
        "all_tags": sorted(all_tags),
        "tool_count": tools.count(),
        "active_count": Tool.objects.filter(is_active=True).count(),
    })


def tool_detail(request, tool_id):
    """View tool details and recent executions."""
    tool = get_object_or_404(Tool, pk=tool_id)
    recent_logs = ExecutionLog.objects.filter(tool=tool).order_by("-run_at")[:10]
    
    return render(request, "mcp_tools/detail.html", {
        "page_title": f"Tool: {tool.name}",
        "tool": tool,
        "recent_logs": recent_logs,
    })


@require_POST
def tool_run(request, tool_id):
    """Execute a tool and return HTMX partial with result."""
    tool = get_object_or_404(Tool, pk=tool_id)
    
    # Get parameters from POST body
    try:
        if request.content_type == "application/json":
            params = json.loads(request.body)
        else:
            params = {}
            for key, value in request.POST.items():
                if key != "csrfmiddlewaretoken":
                    # Try to parse as JSON if possible
                    try:
                        params[key] = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        params[key] = value
    except Exception as e:
        return render(request, "mcp_tools/partials/tool_result.html", {
            "tool": tool,
            "success": False,
            "error": f"Invalid parameters: {e}",
        })
    
    # Execute the tool
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(execute_tool(tool.name, params))
        loop.close()
        
        # Refresh tool from DB to get updated stats
        tool.refresh_from_db()
        
        return render(request, "mcp_tools/partials/tool_result.html", {
            "tool": tool,
            "success": True,
            "result": json.dumps(result, indent=2, default=str),
        })
        
    except (ToolNotFoundError, ToolExecutionError) as e:
        return render(request, "mcp_tools/partials/tool_result.html", {
            "tool": tool,
            "success": False,
            "error": str(e),
        })
    except Exception as e:
        logger.exception(f"Tool execution failed: {e}")
        return render(request, "mcp_tools/partials/tool_result.html", {
            "tool": tool,
            "success": False,
            "error": f"Unexpected error: {e}",
        })


def tool_request_list(request):
    """List all tool requests."""
    requests = ToolRequest.objects.all().order_by("-created_at")
    
    # Filter by resolved status
    resolved_filter = request.GET.get("resolved", "")
    if resolved_filter == "true":
        requests = requests.filter(resolved=True)
    elif resolved_filter == "false":
        requests = requests.filter(resolved=False)
    
    return render(request, "mcp_tools/requests.html", {
        "page_title": "Tool Requests",
        "requests": requests,
        "resolved_filter": resolved_filter,
        "pending_count": ToolRequest.objects.filter(resolved=False).count(),
    })


@require_POST
def tool_request_create(request):
    """Create a new tool request."""
    try:
        if request.content_type == "application/json":
            data = json.loads(request.body)
        else:
            data = request.POST.dict()
        
        tool_request = ToolRequest.objects.create(
            prompt=data.get("prompt", ""),
            suggested_name=data.get("suggested_name", ""),
            suggested_description=data.get("suggested_description", ""),
            suggested_schema=data.get("suggested_schema", {}),
            notes=data.get("notes", ""),
        )
        
        if request.headers.get("HX-Request"):
            return render(request, "mcp_tools/partials/request_row.html", {
                "request": tool_request,
            })
        
        return redirect("mcp_tools:requests")
        
    except Exception as e:
        if request.headers.get("HX-Request"):
            return HttpResponse(f"Error: {e}", status=400)
        return redirect("mcp_tools:requests")


@require_POST
def tool_request_resolve(request, request_id):
    """Mark a tool request as resolved."""
    tool_request = get_object_or_404(ToolRequest, pk=request_id)
    
    tool_request.resolved = True
    tool_request.resolved_at = timezone.now()
    
    # If a tool_id was provided, link it
    tool_id = request.POST.get("tool_id")
    if tool_id:
        try:
            tool_request.resolved_tool = Tool.objects.get(pk=tool_id)
        except Tool.DoesNotExist:
            pass
    
    tool_request.save()
    
    if request.headers.get("HX-Request"):
        return render(request, "mcp_tools/partials/request_row.html", {
            "request": tool_request,
        })
    
    return redirect("mcp_tools:requests")


def fact_list(request):
    """List all facts in the knowledge store."""
    facts = Fact.objects.all().order_by("-updated_at")
    
    # Filter by source
    source_filter = request.GET.get("source", "")
    if source_filter:
        facts = facts.filter(source=source_filter)
    
    # Get unique sources for filter dropdown
    sources = Fact.objects.values_list("source", flat=True).distinct()
    
    return render(request, "mcp_tools/facts.html", {
        "page_title": "Knowledge Store",
        "facts": facts,
        "source_filter": source_filter,
        "sources": [s for s in sources if s],
    })


@require_POST
def fact_create(request):
    """Create or update a fact."""
    try:
        if request.content_type == "application/json":
            data = json.loads(request.body)
        else:
            data = request.POST.dict()
            # Try to parse value as JSON
            if "value" in data:
                try:
                    data["value"] = json.loads(data["value"])
                except (json.JSONDecodeError, TypeError):
                    pass
        
        key = data.get("key", "")
        value = data.get("value", {})
        source = data.get("source", "user_input")
        
        fact, created = Fact.objects.update_or_create(
            key=key,
            defaults={
                "value": value,
                "source": source,
            }
        )
        
        if request.headers.get("HX-Request"):
            return render(request, "mcp_tools/partials/fact_row.html", {
                "fact": fact,
            })
        
        return redirect("mcp_tools:facts")
        
    except Exception as e:
        if request.headers.get("HX-Request"):
            return HttpResponse(f"Error: {e}", status=400)
        return redirect("mcp_tools:facts")


def execution_log_list(request):
    """List execution logs."""
    logs = ExecutionLog.objects.select_related("tool").order_by("-run_at")[:100]
    
    # Filter by tool
    tool_filter = request.GET.get("tool", "")
    if tool_filter:
        logs = logs.filter(tool__name=tool_filter)
    
    # Filter by success
    success_filter = request.GET.get("success", "")
    if success_filter == "true":
        logs = logs.filter(success=True)
    elif success_filter == "false":
        logs = logs.filter(success=False)
    
    return render(request, "mcp_tools/logs.html", {
        "page_title": "Execution Logs",
        "logs": logs,
        "tool_filter": tool_filter,
        "success_filter": success_filter,
        "tools": Tool.objects.values_list("name", flat=True).distinct(),
    })


# =============================================================================
# REST API Views
# =============================================================================

@require_GET
def api_root(request):
    """API: Root endpoint with usage documentation.
    
    This endpoint provides a self-describing API guide for LLMs and agents.
    """
    base_url = request.build_absolute_uri('/tools/api/')
    
    return JsonResponse({
        "name": "JexidaMCP Tools API",
        "version": "1.0",
        "description": "REST API for executing MCP tools programmatically. Supports UniFi network management, Synology NAS operations, Azure cloud management, and more.",
        "endpoints": {
            "list_tools": {
                "method": "GET",
                "url": f"{base_url}tools/",
                "description": "List all available tools with their schemas",
            },
            "get_tool": {
                "method": "GET", 
                "url": f"{base_url}tools/{{tool_name}}/",
                "description": "Get details for a specific tool",
            },
            "run_tool": {
                "method": "POST",
                "url": f"{base_url}tools/{{tool_name}}/run/",
                "description": "Execute a tool with parameters",
                "content_type": "application/json",
                "body": "JSON object matching the tool's input_schema",
            },
            "list_facts": {
                "method": "GET",
                "url": f"{base_url}facts/",
                "description": "List all facts in the knowledge store",
            },
        },
        "usage": {
            "step_1": "GET /tools/api/tools/ to discover available tools",
            "step_2": "Check the input_schema for required/optional parameters",
            "step_3": "POST to /tools/api/tools/{tool_name}/run/ with JSON body",
            "step_4": "Response contains {success: bool, result: object}",
        },
        "examples": {
            "list_unifi_devices": {
                "request": "POST /tools/api/tools/unifi_list_devices/run/",
                "body": "{}",
                "note": "Empty body uses defaults; pass {\"site_id\": \"abc\"} to override",
            },
            "list_synology_files": {
                "request": "POST /tools/api/tools/synology_list_files/run/",
                "body": "{\"folder_path\": \"/shared\"}",
            },
        },
        "tool_categories": {
            "unifi": "Network management - devices, security, firewall, clients",
            "synology": "NAS operations - files, docker, backups, users",
            "azure": "Cloud management - CLI commands, resource queries",
            "network": "Security scanning and auditing",
        },
    })


@require_GET
def api_tool_list(request):
    """API: List all active tools."""
    tools = Tool.objects.filter(is_active=True).order_by("name")
    
    return JsonResponse({
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "tags": t.get_tags_list(),
                "input_schema": t.input_schema,
                "last_run": t.last_run.isoformat() if t.last_run else None,
                "run_count": t.run_count,
            }
            for t in tools
        ]
    })


@require_GET
def api_tool_detail(request, name):
    """API: Get tool details."""
    try:
        tool = Tool.objects.get(name=name)
        return JsonResponse({
            "name": tool.name,
            "description": tool.description,
            "tags": tool.get_tags_list(),
            "input_schema": tool.input_schema,
            "is_active": tool.is_active,
            "last_run": tool.last_run.isoformat() if tool.last_run else None,
            "run_count": tool.run_count,
        })
    except Tool.DoesNotExist:
        return JsonResponse({"error": f"Tool '{name}' not found"}, status=404)


@csrf_exempt
@require_POST
def api_tool_run(request, name):
    """API: Execute a tool."""
    try:
        params = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(execute_tool(name, params))
        loop.close()
        
        return JsonResponse({
            "success": True,
            "result": result,
        })
        
    except ToolNotFoundError as e:
        return JsonResponse({
            "success": False,
            "error": str(e),
        }, status=404)
    except ToolExecutionError as e:
        return JsonResponse({
            "success": False,
            "error": str(e),
        }, status=500)
    except Exception as e:
        logger.exception(f"API tool execution failed: {e}")
        return JsonResponse({
            "success": False,
            "error": f"Unexpected error: {e}",
        }, status=500)


@csrf_exempt
@require_POST
def api_tool_request(request):
    """API: Create a tool request (for LLM integration)."""
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    
    tool_request = ToolRequest.objects.create(
        prompt=data.get("prompt", ""),
        suggested_name=data.get("suggested_name", ""),
        suggested_description=data.get("suggested_description", ""),
        suggested_schema=data.get("suggested_schema", {}),
        notes=data.get("notes", ""),
    )
    
    return JsonResponse({
        "id": tool_request.id,
        "suggested_name": tool_request.suggested_name,
        "created_at": tool_request.created_at.isoformat(),
        "message": "Tool request created successfully",
    }, status=201)


@require_GET
def api_fact_list(request):
    """API: List all facts."""
    facts = Fact.objects.all().order_by("-updated_at")
    
    # Optional source filter
    source = request.GET.get("source")
    if source:
        facts = facts.filter(source=source)
    
    return JsonResponse({
        "facts": [
            {
                "key": f.key,
                "value": f.value,
                "source": f.source,
                "learned_at": f.learned_at.isoformat(),
                "updated_at": f.updated_at.isoformat(),
            }
            for f in facts
        ]
    })


@csrf_exempt
def api_fact_detail(request, key):
    """API: Get, create, or update a fact."""
    if request.method == "GET":
        try:
            fact = Fact.objects.get(key=key)
            return JsonResponse({
                "key": fact.key,
                "value": fact.value,
                "source": fact.source,
                "learned_at": fact.learned_at.isoformat(),
                "updated_at": fact.updated_at.isoformat(),
            })
        except Fact.DoesNotExist:
            return JsonResponse({"error": f"Fact '{key}' not found"}, status=404)
    
    elif request.method in ("POST", "PUT"):
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)
        
        fact, created = Fact.objects.update_or_create(
            key=key,
            defaults={
                "value": data.get("value", {}),
                "source": data.get("source", "api"),
            }
        )
        
        return JsonResponse({
            "key": fact.key,
            "value": fact.value,
            "source": fact.source,
            "created": created,
        }, status=201 if created else 200)
    
    elif request.method == "DELETE":
        try:
            fact = Fact.objects.get(key=key)
            fact.delete()
            return JsonResponse({"message": f"Fact '{key}' deleted"})
        except Fact.DoesNotExist:
            return JsonResponse({"error": f"Fact '{key}' not found"}, status=404)
    
    return JsonResponse({"error": "Method not allowed"}, status=405)

