"""URL patterns for assistant app pages."""

from django.urls import path
from . import views

app_name = "assistant"

urlpatterns = [
    path("", views.chat_page, name="chat"),
    path("conversations/", views.conversation_list, name="conversations"),
    path("conversations/<int:conversation_id>/", views.conversation_detail, name="conversation_detail"),
]

