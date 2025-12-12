"""API views for AI assistant with MCP tools integration.

This module provides the REST API for the AI assistant, including:
- Chat with MCP tool awareness and execution
- Tool confirmation for dangerous operations
- Conversation management
- Status endpoint
"""

import asyncio
import json
import logging
import uuid
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.cache import cache

from .models import Conversation, Message, MessageRole
from .mcp_tools_bridge import (
    get_mcp_tool_definitions,
    get_tool_by_name,
    is_dangerous_tool,
    get_tool_risk_level,
    execute_mcp_tool,
    build_tools_context_prompt,
)

logger = logging.getLogger(__name__)

# Cache key prefix for pending tool calls
PENDING_TOOL_CACHE_PREFIX = "pending_tool_call:"
PENDING_TOOL_TIMEOUT = 300  # 5 minutes


@csrf_exempt
@require_http_methods(["POST"])
def api_chat(request):
    """Process a user message and return AI response with MCP tool support.
    
    This endpoint:
    1. Loads MCP tool definitions from the database
    2. Sends user message to LLM with tool context
    3. If LLM requests a tool call:
       - Safe tools: Execute immediately and return result
       - Dangerous tools: Return pending_tool_call for UI confirmation
    4. Returns the assistant's response
    """
    try:
        data = json.loads(request.body)
        user_message = data.get("message", "")
        conversation_id = data.get("conversation_id")
        page_context = data.get("page_context")
        mode = data.get("mode")
        temperature = data.get("temperature")
        
        # Get or create conversation
        if conversation_id:
            try:
                conversation = Conversation.objects.get(id=conversation_id)
            except Conversation.DoesNotExist:
                conversation = Conversation.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    mode=mode or "default",
                    context=page_context or {},
                )
        else:
            conversation = Conversation.objects.create(
                user=request.user if request.user.is_authenticated else None,
                mode=mode or "default",
                context=page_context or {},
            )
        
        # Save user message
        Message.objects.create(
            conversation=conversation,
            role=MessageRole.USER,
            content=user_message,
        )
        
        # Get conversation history
        messages = list(conversation.messages.all())
        history = [msg.to_openai_format() for msg in messages[:-1]]
        
        # Get MCP tool definitions
        mcp_tools = get_mcp_tool_definitions()
        tools_context = build_tools_context_prompt()
        
        # Process with MCP-aware service
        user_id = str(request.user.id) if request.user.is_authenticated else None
        user_roles = ["admin"] if request.user.is_staff else []
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_process_message_with_mcp_tools(
                content=user_message,
                conversation_history=history,
                mcp_tools=mcp_tools,
                tools_context=tools_context,
                user_id=user_id,
                user_roles=user_roles,
                page_context=page_context,
                mode=mode,
                temperature=temperature,
            ))
        finally:
            loop.close()
        
        # Check if we have a pending tool call that needs confirmation
        if result.get("pending_tool_call"):
            pending = result["pending_tool_call"]
            
            # Store the pending tool call in cache for later confirmation
            cache_key = f"{PENDING_TOOL_CACHE_PREFIX}{pending['id']}"
            cache.set(cache_key, {
                "conversation_id": conversation.id,
                "tool_name": pending["tool_name"],
                "parameters": pending["parameters"],
                "context_messages": result.get("context_messages", []),
            }, PENDING_TOOL_TIMEOUT)
            
            # Save a placeholder assistant message
            assistant_message = Message.objects.create(
                conversation=conversation,
                role=MessageRole.ASSISTANT,
                content=result.get("content", ""),
                metadata={
                    "pending_tool_call": pending,
                    "awaiting_confirmation": True,
                },
            )
            
            return JsonResponse({
                "conversation_id": conversation.id,
                "message_id": assistant_message.id,
                "content": result.get("content", ""),
                "pending_tool_call": pending,
                "tokens_used": result.get("tokens_used", 0),
            })
        
        # Save assistant message
        assistant_message = Message.objects.create(
            conversation=conversation,
            role=MessageRole.ASSISTANT,
            content=result.get("content", ""),
            tokens_used=result.get("tokens_used", 0),
            metadata={
                "tool_calls": result.get("tool_calls"),
            } if result.get("tool_calls") else None,
        )
        
        return JsonResponse({
            "conversation_id": conversation.id,
            "message_id": assistant_message.id,
            "content": result.get("content", ""),
            "tool_calls": result.get("tool_calls"),
            "tool_results": result.get("tool_results"),
            "tokens_used": result.get("tokens_used", 0),
        })
    
    except Exception as e:
        logger.exception("Chat API error")
        return JsonResponse({
            "error": str(e),
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_confirm_tool(request):
    """Confirm or cancel a pending tool execution.
    
    This endpoint is called when the user confirms or cancels a dangerous
    tool that was pending confirmation.
    
    Request body:
        {
            "tool_call_id": "...",
            "confirmed": true/false
        }
    
    Returns:
        Tool execution result or cancellation acknowledgment
    """
    try:
        data = json.loads(request.body)
        tool_call_id = data.get("tool_call_id")
        confirmed = data.get("confirmed", False)
        
        if not tool_call_id:
            return JsonResponse({"error": "tool_call_id is required"}, status=400)
        
        # Get pending tool call from cache
        cache_key = f"{PENDING_TOOL_CACHE_PREFIX}{tool_call_id}"
        pending = cache.get(cache_key)
        
        if not pending:
            return JsonResponse({
                "error": "Tool call not found or expired",
                "expired": True,
            }, status=404)
        
        # Clear the cache entry
        cache.delete(cache_key)
        
        # Get conversation
        try:
            conversation = Conversation.objects.get(id=pending["conversation_id"])
        except Conversation.DoesNotExist:
            return JsonResponse({"error": "Conversation not found"}, status=404)
        
        if not confirmed:
            # User cancelled the tool execution
            Message.objects.create(
                conversation=conversation,
                role=MessageRole.ASSISTANT,
                content=f"Tool execution cancelled: {pending['tool_name']}",
                metadata={"cancelled_tool": pending["tool_name"]},
            )
            
            return JsonResponse({
                "conversation_id": conversation.id,
                "cancelled": True,
                "tool_name": pending["tool_name"],
                "message": "Tool execution was cancelled.",
            })
        
        # Execute the confirmed tool
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            tool_result = loop.run_until_complete(
                execute_mcp_tool(pending["tool_name"], pending["parameters"])
            )
        finally:
            loop.close()
        
        # Save tool result message
        if tool_result.get("success"):
            result_content = _format_tool_result(pending["tool_name"], tool_result["result"])
        else:
            result_content = f"Tool execution failed: {tool_result.get('error', 'Unknown error')}"
        
        Message.objects.create(
            conversation=conversation,
            role=MessageRole.ASSISTANT,
            content=result_content,
            metadata={
                "tool_execution": {
                    "tool_name": pending["tool_name"],
                    "success": tool_result.get("success", False),
                    "confirmed": True,
                },
            },
        )
        
        return JsonResponse({
            "conversation_id": conversation.id,
            "tool_name": pending["tool_name"],
            "success": tool_result.get("success", False),
            "result": tool_result.get("result"),
            "error": tool_result.get("error"),
            "content": result_content,
        })
    
    except Exception as e:
        logger.exception("Confirm tool API error")
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_chat_stream(request):
    """Process a user message with streaming response."""
    # For now, return a simple non-streaming response
    # Full SSE streaming would require async view support
    return api_chat(request)


@require_http_methods(["GET"])
def api_conversations(request):
    """List conversations."""
    conversations = Conversation.objects.filter(
        is_active=True
    ).order_by("-updated_at")[:20]
    
    return JsonResponse({
        "conversations": [c.to_dict() for c in conversations],
    })


@require_http_methods(["GET"])
def api_conversation_detail(request, conversation_id):
    """Get conversation details."""
    try:
        conversation = Conversation.objects.get(id=conversation_id)
        messages = list(conversation.messages.all())
        
        return JsonResponse({
            "conversation": conversation.to_dict(),
            "messages": [m.to_dict() for m in messages],
        })
    except Conversation.DoesNotExist:
        return JsonResponse({"error": "Conversation not found"}, status=404)


@require_http_methods(["GET"])
def api_status(request):
    """Get assistant status including MCP tools info."""
    from core.providers import get_provider
    from .mcp_tools_bridge import get_tools_summary
    
    provider = get_provider()
    tools_summary = get_tools_summary()
    
    return JsonResponse({
        "provider": provider.provider_name,
        "is_configured": provider.is_configured(),
        "model": provider.default_model,
        "mcp_tools": tools_summary,
    })


# =============================================================================
# Helper Functions
# =============================================================================

async def _process_message_with_mcp_tools(
    content: str,
    conversation_history: list,
    mcp_tools: list,
    tools_context: str,
    user_id: str = None,
    user_roles: list = None,
    page_context: dict = None,
    mode: str = None,
    temperature: float = None,
) -> dict:
    """Process a message with MCP tool awareness.
    
    This is the core processing function that:
    1. Builds the system prompt with tools context
    2. Calls the LLM with tool definitions
    3. Handles tool calls (auto-execute safe, defer dangerous)
    """
    from core.providers import get_provider
    from core.services.assistant import (
        build_system_prompt,
        build_conversation_messages,
        truncate_context,
    )
    
    # Build system prompt with MCP tools context
    base_prompt = build_system_prompt(
        user_id=user_id,
        user_roles=user_roles,
        page_context=page_context,
        conversation_mode=mode,
    )
    
    # Append MCP tools context
    system_prompt = f"{base_prompt}\n\n## MCP Tools\n\n{tools_context}"
    
    # Add user message to history
    messages = conversation_history + [{"role": "user", "content": content}]
    messages = truncate_context(messages)
    full_messages = build_conversation_messages(messages, system_prompt)
    
    # Get provider
    provider = get_provider()
    
    if not provider.is_configured():
        return {
            "content": "I'm sorry, but the AI assistant is not currently configured.",
            "tokens_used": 0,
        }
    
    # Call LLM with tools
    total_tokens = 0
    all_tool_results = []
    current_messages = full_messages.copy()
    max_iterations = 5
    
    for iteration in range(max_iterations):
        call_params = {
            "messages": current_messages,
            "functions": mcp_tools if mcp_tools else None,
        }
        if temperature is not None:
            call_params["temperature"] = temperature
        
        response = await provider.chat_completion(**call_params)
        total_tokens += response.total_tokens
        
        # No tool calls - return response
        if not response.has_tool_calls:
            return {
                "content": response.content or "",
                "tool_calls": all_tool_results if all_tool_results else None,
                "tool_results": all_tool_results if all_tool_results else None,
                "tokens_used": total_tokens,
            }
        
        # Process tool calls
        for tc in response.tool_calls:
            tool = get_tool_by_name(tc.name)
            
            if not tool:
                # Tool not found
                all_tool_results.append({
                    "tool_call_id": tc.id,
                    "tool_name": tc.name,
                    "success": False,
                    "error": f"Tool '{tc.name}' not found",
                })
                continue
            
            # Check if tool is dangerous
            if is_dangerous_tool(tool):
                # Return pending confirmation
                return {
                    "content": response.content or f"I'll execute {tool.name} for you.",
                    "pending_tool_call": {
                        "id": str(uuid.uuid4()),
                        "tool_call_id": tc.id,
                        "tool_name": tc.name,
                        "tool_description": tool.description,
                        "parameters": tc.arguments,
                        "requires_confirmation": True,
                        "risk_level": get_tool_risk_level(tool),
                        "reason": _get_confirmation_reason(tool),
                    },
                    "context_messages": current_messages,
                    "tokens_used": total_tokens,
                }
            
            # Safe tool - execute immediately
            try:
                result = await execute_mcp_tool(tc.name, tc.arguments)
                all_tool_results.append({
                    "tool_call_id": tc.id,
                    "tool_name": tc.name,
                    "success": result.get("success", False),
                    "result": result.get("result"),
                    "error": result.get("error"),
                })
            except Exception as e:
                all_tool_results.append({
                    "tool_call_id": tc.id,
                    "tool_name": tc.name,
                    "success": False,
                    "error": str(e),
                })
        
        # Add tool results to context for next iteration
        current_messages.append({
            "role": "assistant",
            "content": response.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in response.tool_calls
            ],
        })
        
        for result in all_tool_results[-len(response.tool_calls):]:
            current_messages.append({
                "role": "tool",
                "tool_call_id": result["tool_call_id"],
                "content": json.dumps(result.get("result", result.get("error", {}))),
            })
    
    return {
        "content": "I've processed your request.",
        "tool_calls": all_tool_results,
        "tool_results": all_tool_results,
        "tokens_used": total_tokens,
    }


def _get_confirmation_reason(tool) -> str:
    """Get a human-readable reason why confirmation is needed."""
    tags = set(t.lower() for t in tool.get_tags_list())
    tool_name = tool.name.lower()
    
    if "delete" in tags or "delete" in tool_name:
        return "This tool may delete data or resources."
    elif "harden" in tags or "harden" in tool_name:
        return "This tool modifies security settings."
    elif "apply" in tags or "apply" in tool_name:
        return "This tool applies configuration changes."
    elif "restart" in tags or "restart" in tool_name or "reboot" in tags:
        return "This tool restarts services or systems."
    elif "create" in tags or "create" in tool_name:
        return "This tool creates new resources."
    elif "modify" in tags or "update" in tags:
        return "This tool modifies existing resources."
    else:
        return "This tool may modify your infrastructure."


def _format_tool_result(tool_name: str, result: any) -> str:
    """Format a tool result for display in chat."""
    if isinstance(result, dict):
        # Check for common result patterns
        if result.get("success") is not None:
            status = "succeeded" if result["success"] else "failed"
            message = result.get("message", result.get("error", ""))
            
            formatted = f"**{tool_name}** {status}"
            if message:
                formatted += f": {message}"
            
            # Include relevant data
            if "result" in result:
                data = result["result"]
                if isinstance(data, (dict, list)):
                    formatted += f"\n\n```json\n{json.dumps(data, indent=2, default=str)[:1000]}\n```"
                else:
                    formatted += f"\n\n{str(data)[:500]}"
            
            return formatted
        else:
            # Generic dict result
            return f"**{tool_name}** result:\n\n```json\n{json.dumps(result, indent=2, default=str)[:1500]}\n```"
    
    elif isinstance(result, list):
        return f"**{tool_name}** returned {len(result)} items:\n\n```json\n{json.dumps(result[:10], indent=2, default=str)}\n```"
    
    else:
        return f"**{tool_name}** result: {str(result)[:500]}"
