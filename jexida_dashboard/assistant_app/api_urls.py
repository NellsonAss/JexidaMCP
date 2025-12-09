"""API URL patterns for assistant app."""

from django.urls import path
from . import api_views

urlpatterns = [
    path("chat/", api_views.api_chat, name="api_chat"),
    path("chat/stream/", api_views.api_chat_stream, name="api_chat_stream"),
    path("conversations/", api_views.api_conversations, name="api_conversations"),
    path("conversations/<int:conversation_id>/", api_views.api_conversation_detail, name="api_conversation_detail"),
    path("status/", api_views.api_status, name="api_status"),
]

