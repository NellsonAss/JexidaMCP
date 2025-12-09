from django.contrib import admin
from .models import Conversation, Message, ActionLog


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "title", "mode", "is_active", "created_at", "updated_at"]
    list_filter = ["mode", "is_active"]
    search_fields = ["title"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["id", "conversation", "role", "tokens_used", "created_at"]
    list_filter = ["role"]
    readonly_fields = ["created_at"]


@admin.register(ActionLog)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = ["id", "action_name", "action_type", "status", "created_at", "executed_at"]
    list_filter = ["action_type", "status"]
    search_fields = ["action_name"]
    readonly_fields = ["created_at", "executed_at"]

