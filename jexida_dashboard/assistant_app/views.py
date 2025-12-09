"""Views for AI assistant chat functionality."""

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse

from .models import Conversation, Message


def chat_page(request):
    """AI Assistant chat interface."""
    return render(request, "assistant/chat.html", {
        "page_title": "AI Assistant",
    })


def conversation_list(request):
    """List conversations for the current user."""
    user = request.user if request.user.is_authenticated else None
    
    conversations = Conversation.objects.filter(
        is_active=True
    ).order_by("-updated_at")[:20]
    
    return render(request, "assistant/conversations.html", {
        "page_title": "Conversations",
        "conversations": conversations,
    })


def conversation_detail(request, conversation_id):
    """View a specific conversation."""
    conversation = get_object_or_404(Conversation, id=conversation_id)
    messages = conversation.messages.all()
    
    return render(request, "assistant/conversation_detail.html", {
        "page_title": f"Conversation {conversation_id}",
        "conversation": conversation,
        "messages": messages,
    })

