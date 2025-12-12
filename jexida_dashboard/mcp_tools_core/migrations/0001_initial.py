"""Initial migration for mcp_tools_core models."""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """Create Tool, ToolRequest, ExecutionLog, and Fact models."""

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Tool",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="Unique tool identifier (e.g., 'unifi_list_devices')",
                        max_length=100,
                        unique=True,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        help_text="Human-readable description of what the tool does"
                    ),
                ),
                (
                    "input_schema",
                    models.JSONField(
                        default=dict,
                        help_text="JSON Schema defining the tool's input parameters",
                    ),
                ),
                (
                    "tags",
                    models.CharField(
                        blank=True,
                        help_text="Comma-separated tags for categorization (e.g., 'unifi,network')",
                        max_length=255,
                    ),
                ),
                (
                    "handler_path",
                    models.CharField(
                        help_text="Python import path to the handler function",
                        max_length=255,
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Whether this tool is available for use",
                    ),
                ),
                (
                    "last_run",
                    models.DateTimeField(
                        blank=True,
                        help_text="When this tool was last executed",
                        null=True,
                    ),
                ),
                (
                    "run_count",
                    models.IntegerField(
                        default=0,
                        help_text="Total number of times this tool has been executed",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Tool",
                "verbose_name_plural": "Tools",
                "db_table": "mcp_tools",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Fact",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "key",
                    models.CharField(
                        help_text="Unique key identifying this fact",
                        max_length=255,
                        unique=True,
                    ),
                ),
                (
                    "value",
                    models.JSONField(
                        help_text="The fact value (can be any JSON-serializable data)"
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        blank=True,
                        help_text="Where this fact came from (e.g., 'unifi_scan', 'user_input')",
                        max_length=100,
                    ),
                ),
                (
                    "confidence",
                    models.FloatField(
                        default=1.0,
                        help_text="Confidence level (0.0 to 1.0) for this fact",
                    ),
                ),
                (
                    "learned_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        help_text="When this fact was first learned",
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True,
                        help_text="When this fact was last updated",
                    ),
                ),
                (
                    "expires_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="When this fact should be considered stale (optional)",
                        null=True,
                    ),
                ),
            ],
            options={
                "verbose_name": "Fact",
                "verbose_name_plural": "Facts",
                "db_table": "mcp_facts",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="ToolRequest",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "prompt",
                    models.TextField(
                        help_text="The original prompt or request that triggered this"
                    ),
                ),
                (
                    "suggested_name",
                    models.CharField(
                        help_text="Suggested name for the new tool",
                        max_length=100,
                    ),
                ),
                (
                    "suggested_description",
                    models.TextField(
                        help_text="Suggested description for what the tool should do"
                    ),
                ),
                (
                    "suggested_schema",
                    models.JSONField(
                        default=dict,
                        help_text="Suggested JSON Schema for the tool's parameters",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "resolved",
                    models.BooleanField(
                        default=False,
                        help_text="Whether this request has been fulfilled",
                    ),
                ),
                (
                    "resolved_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="When this request was resolved",
                        null=True,
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True,
                        help_text="Additional notes about this request",
                    ),
                ),
                (
                    "resolved_tool",
                    models.ForeignKey(
                        blank=True,
                        help_text="The tool that was created to fulfill this request",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="requests",
                        to="mcp_tools_core.tool",
                    ),
                ),
            ],
            options={
                "verbose_name": "Tool Request",
                "verbose_name_plural": "Tool Requests",
                "db_table": "mcp_tool_requests",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ExecutionLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "run_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        help_text="When the execution started",
                    ),
                ),
                (
                    "parameters",
                    models.JSONField(
                        default=dict,
                        help_text="Input parameters passed to the tool",
                    ),
                ),
                (
                    "result",
                    models.TextField(
                        help_text="Output/result from the tool execution"
                    ),
                ),
                (
                    "success",
                    models.BooleanField(
                        help_text="Whether the execution succeeded"
                    ),
                ),
                (
                    "duration_ms",
                    models.IntegerField(
                        blank=True,
                        help_text="Execution duration in milliseconds",
                        null=True,
                    ),
                ),
                (
                    "error_message",
                    models.TextField(
                        blank=True,
                        help_text="Error message if execution failed",
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True,
                        help_text="Additional notes about this execution",
                    ),
                ),
                (
                    "tool",
                    models.ForeignKey(
                        help_text="The tool that was executed",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="executions",
                        to="mcp_tools_core.tool",
                    ),
                ),
            ],
            options={
                "verbose_name": "Execution Log",
                "verbose_name_plural": "Execution Logs",
                "db_table": "mcp_execution_logs",
                "ordering": ["-run_at"],
            },
        ),
    ]

