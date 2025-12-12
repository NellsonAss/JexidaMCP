"""Admin configuration for jobs app."""

from django.contrib import admin
from mcp_tools_core.models import WorkerNode, Job


@admin.register(WorkerNode)
class WorkerNodeAdmin(admin.ModelAdmin):
    """Admin for WorkerNode model."""

    list_display = ["name", "host", "user", "ssh_port", "is_active", "last_seen", "created_at"]
    list_filter = ["is_active", "tags"]
    search_fields = ["name", "host", "tags"]
    readonly_fields = ["created_at", "updated_at", "last_seen"]


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    """Admin for Job model."""

    list_display = ["id", "target_node", "status", "exit_code", "duration_ms", "created_at"]
    list_filter = ["status", "target_node"]
    search_fields = ["command", "id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    raw_id_fields = ["target_node"]

