"""Django admin configuration for MCP Tools Core models."""

from django.contrib import admin
from django.utils.html import format_html

from .models import Tool, ToolRequest, ExecutionLog, Fact


@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    """Admin interface for Tool model."""

    list_display = [
        "name",
        "is_active",
        "tags",
        "run_count",
        "last_run",
        "created_at",
    ]
    list_filter = ["is_active", "tags"]
    search_fields = ["name", "description", "tags"]
    readonly_fields = ["created_at", "updated_at", "run_count", "last_run"]
    ordering = ["name"]

    fieldsets = (
        (None, {"fields": ("name", "description", "is_active")}),
        ("Configuration", {"fields": ("input_schema", "handler_path", "tags")}),
        (
            "Statistics",
            {
                "fields": ("run_count", "last_run"),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(ToolRequest)
class ToolRequestAdmin(admin.ModelAdmin):
    """Admin interface for ToolRequest model."""

    list_display = [
        "suggested_name",
        "resolved_status",
        "resolved_tool",
        "created_at",
    ]
    list_filter = ["resolved", "created_at"]
    search_fields = ["suggested_name", "suggested_description", "prompt"]
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]

    fieldsets = (
        (None, {"fields": ("prompt", "suggested_name", "suggested_description")}),
        ("Schema", {"fields": ("suggested_schema",)}),
        (
            "Resolution",
            {"fields": ("resolved", "resolved_at", "resolved_tool", "notes")},
        ),
        ("Timestamps", {"fields": ("created_at",), "classes": ("collapse",)}),
    )

    @admin.display(description="Status")
    def resolved_status(self, obj):
        if obj.resolved:
            return format_html(
                '<span style="color: #3fb950;">✓ Resolved</span>'
            )
        return format_html(
            '<span style="color: #d29922;">○ Pending</span>'
        )


@admin.register(ExecutionLog)
class ExecutionLogAdmin(admin.ModelAdmin):
    """Admin interface for ExecutionLog model."""

    list_display = [
        "tool",
        "success_status",
        "duration_display",
        "run_at",
    ]
    list_filter = ["success", "tool", "run_at"]
    search_fields = ["tool__name", "result", "error_message"]
    readonly_fields = ["run_at"]
    ordering = ["-run_at"]

    fieldsets = (
        (None, {"fields": ("tool", "parameters")}),
        ("Result", {"fields": ("success", "result", "error_message")}),
        ("Timing", {"fields": ("run_at", "duration_ms")}),
        ("Notes", {"fields": ("notes",), "classes": ("collapse",)}),
    )

    @admin.display(description="Status")
    def success_status(self, obj):
        if obj.success:
            return format_html(
                '<span style="color: #3fb950;">✓ Success</span>'
            )
        return format_html(
            '<span style="color: #f85149;">✗ Failed</span>'
        )

    @admin.display(description="Duration")
    def duration_display(self, obj):
        if obj.duration_ms is None:
            return "-"
        if obj.duration_ms < 1000:
            return f"{obj.duration_ms}ms"
        return f"{obj.duration_ms / 1000:.2f}s"


@admin.register(Fact)
class FactAdmin(admin.ModelAdmin):
    """Admin interface for Fact model."""

    list_display = [
        "key",
        "source",
        "confidence",
        "expiry_status",
        "updated_at",
    ]
    list_filter = ["source", "confidence"]
    search_fields = ["key", "source"]
    readonly_fields = ["learned_at", "updated_at"]
    ordering = ["-updated_at"]

    fieldsets = (
        (None, {"fields": ("key", "value")}),
        ("Metadata", {"fields": ("source", "confidence", "expires_at")}),
        (
            "Timestamps",
            {
                "fields": ("learned_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Expiry")
    def expiry_status(self, obj):
        if obj.expires_at is None:
            return "Never"
        if obj.is_expired:
            return format_html(
                '<span style="color: #f85149;">Expired</span>'
            )
        return format_html(
            '<span style="color: #3fb950;">Valid</span>'
        )

