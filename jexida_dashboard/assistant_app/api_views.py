"""API views for AI assistant."""

import asyncio
import json
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

import sys
sys.path.insert(0, str(__file__).replace('/jexida_dashboard/assistant_app/api_views.py', ''))
from core.services.assistant import process_message

from .models import Conversation, Message, MessageRole


@csrf_exempt
@require_http_methods(["POST"])
def api_chat(request):
    """Process a user message and return AI response."""
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
        history = [msg.to_openai_format() for msg in messages[:-1]]  # Exclude current message
        
        # Process with core service
        user_id = str(request.user.id) if request.user.is_authenticated else None
        user_roles = ["admin"] if request.user.is_staff else []
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(process_message(
                content=user_message,
                conversation_history=history,
                user_id=user_id,
                user_roles=user_roles,
                page_context=page_context,
                mode=mode,
                temperature=temperature,
            ))
        finally:
            loop.close()
        
        # Save assistant message
        assistant_message = Message.objects.create(
            conversation=conversation,
            role=MessageRole.ASSISTANT,
            content=result.get("content", ""),
            tokens_used=result.get("tokens_used", 0),
        )
        
        return JsonResponse({
            "conversation_id": conversation.id,
            "message_id": assistant_message.id,
            "content": result.get("content", ""),
            "tool_calls": result.get("tool_calls"),
            "tokens_used": result.get("tokens_used", 0),
        })
    
    except Exception as e:
        return JsonResponse({
            "error": str(e),
        }, status=500)


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
    """Get assistant status."""
    from core.providers import get_provider
    from core.actions import get_action_registry
    
    provider = get_provider()
    registry = get_action_registry()
    
    return JsonResponse({
        "provider": provider.provider_name,
        "is_configured": provider.is_configured(),
        "model": provider.default_model,
        "available_actions": len(registry.list_actions()),
    })

