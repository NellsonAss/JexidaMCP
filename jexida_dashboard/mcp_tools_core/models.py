"""Models for the self-extending MCP platform.

This module defines the core models for:
- Tool: Dynamic tool registry
- ToolRequest: Missing tool tracking
- ExecutionLog: Tool run history
- Fact: Persistent memory/knowledge store
- WorkerNode: Remote worker nodes for job execution
- Job: Jobs dispatched to worker nodes
"""

import uuid

from django.db import models


class Tool(models.Model):
    """Represents a registered MCP tool/function.

    Tools are the core building blocks of the MCP platform. Each tool
    has a unique name, description, input schema, and handler path that
    points to the actual implementation.
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique tool identifier (e.g., 'unifi_list_devices')",
    )
    description = models.TextField(
        help_text="Human-readable description of what the tool does"
    )
    input_schema = models.JSONField(
        default=dict,
        help_text="JSON Schema defining the tool's input parameters",
    )
    tags = models.CharField(
        max_length=255,
        blank=True,
        help_text="Comma-separated tags for categorization (e.g., 'unifi,network')",
    )
    handler_path = models.CharField(
        max_length=255,
        help_text="Python import path to the handler function (e.g., 'mcp_tools_core.tools.unifi.devices.unifi_list_devices')",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this tool is available for use",
    )
    last_run = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this tool was last executed",
    )
    run_count = models.IntegerField(
        default=0,
        help_text="Total number of times this tool has been executed",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "mcp_tools"
        ordering = ["name"]
        verbose_name = "Tool"
        verbose_name_plural = "Tools"

    def __str__(self):
        status = "active" if self.is_active else "inactive"
        return f"{self.name} ({status})"

    def get_tags_list(self):
        """Return tags as a list."""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(",")]


class ToolRequest(models.Model):
    """Tracks requests for tools that don't exist yet.

    When an LLM or user needs functionality that no existing tool provides,
    a ToolRequest is created to track what was needed. This enables the
    self-extending nature of the MCP platform.
    """

    prompt = models.TextField(
        help_text="The original prompt or request that triggered this"
    )
    suggested_name = models.CharField(
        max_length=100,
        help_text="Suggested name for the new tool",
    )
    suggested_description = models.TextField(
        help_text="Suggested description for what the tool should do",
    )
    suggested_schema = models.JSONField(
        default=dict,
        help_text="Suggested JSON Schema for the tool's parameters",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(
        default=False,
        help_text="Whether this request has been fulfilled",
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this request was resolved",
    )
    resolved_tool = models.ForeignKey(
        Tool,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="requests",
        help_text="The tool that was created to fulfill this request",
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this request",
    )

    class Meta:
        db_table = "mcp_tool_requests"
        ordering = ["-created_at"]
        verbose_name = "Tool Request"
        verbose_name_plural = "Tool Requests"

    def __str__(self):
        status = "resolved" if self.resolved else "pending"
        return f"{self.suggested_name} ({status})"


class ExecutionLog(models.Model):
    """Logs each execution of a tool.

    Provides an audit trail of tool usage including parameters,
    results, success/failure, and timing information.
    """

    tool = models.ForeignKey(
        Tool,
        on_delete=models.CASCADE,
        related_name="executions",
        help_text="The tool that was executed",
    )
    run_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the execution started",
    )
    parameters = models.JSONField(
        default=dict,
        help_text="Input parameters passed to the tool",
    )
    result = models.TextField(
        help_text="Output/result from the tool execution",
    )
    success = models.BooleanField(
        help_text="Whether the execution succeeded",
    )
    duration_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Execution duration in milliseconds",
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error message if execution failed",
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this execution",
    )

    class Meta:
        db_table = "mcp_execution_logs"
        ordering = ["-run_at"]
        verbose_name = "Execution Log"
        verbose_name_plural = "Execution Logs"

    def __str__(self):
        status = "success" if self.success else "failed"
        return f"{self.tool.name} @ {self.run_at.strftime('%Y-%m-%d %H:%M')} ({status})"


class Fact(models.Model):
    """Persistent memory/knowledge store.

    Facts represent learned information that the MCP platform accumulates
    over time. This enables the LLM to remember things like device inventories,
    previous scan results, user preferences, etc.
    """

    key = models.CharField(
        max_length=255,
        unique=True,
        help_text="Unique key identifying this fact (e.g., 'network.devices.last_scan')",
    )
    value = models.JSONField(
        help_text="The fact value (can be any JSON-serializable data)",
    )
    source = models.CharField(
        max_length=100,
        blank=True,
        help_text="Where this fact came from (e.g., 'unifi_scan', 'user_input')",
    )
    confidence = models.FloatField(
        default=1.0,
        help_text="Confidence level (0.0 to 1.0) for this fact",
    )
    learned_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this fact was first learned",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When this fact was last updated",
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this fact should be considered stale (optional)",
    )

    class Meta:
        db_table = "mcp_facts"
        ordering = ["-updated_at"]
        verbose_name = "Fact"
        verbose_name_plural = "Facts"

    def __str__(self):
        return f"{self.key} (from {self.source or 'unknown'})"

    @property
    def is_expired(self):
        """Check if this fact has expired."""
        if self.expires_at is None:
            return False
        from django.utils import timezone

        return timezone.now() > self.expires_at


class WorkerNode(models.Model):
    """Represents a remote worker node that can execute jobs.

    Worker nodes are remote servers that the MCP platform can SSH into
    to execute commands and jobs. Each node has connection details and
    can be tagged for job routing.
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique node identifier (e.g., 'node-ubuntu-0')",
    )
    host = models.CharField(
        max_length=255,
        help_text="Hostname or IP address of the worker node",
    )
    user = models.CharField(
        max_length=100,
        help_text="SSH username for connecting to the node",
    )
    ssh_port = models.IntegerField(
        default=22,
        help_text="SSH port number",
    )
    tags = models.CharField(
        max_length=255,
        blank=True,
        help_text="Comma-separated tags for categorization (e.g., 'ubuntu,gpu,worker')",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this node is available for jobs",
    )
    last_seen = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this node was last successfully contacted",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "mcp_worker_nodes"
        ordering = ["name"]
        verbose_name = "Worker Node"
        verbose_name_plural = "Worker Nodes"

    def __str__(self):
        status = "active" if self.is_active else "inactive"
        return f"{self.name} ({self.host}) - {status}"

    def get_tags_list(self):
        """Return tags as a list."""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(",")]

    def get_connection_string(self):
        """Return the SSH connection string."""
        return f"{self.user}@{self.host}"


class Job(models.Model):
    """Represents a job dispatched to a worker node.

    Jobs are commands or tasks that are executed on remote worker nodes.
    Each job tracks its status, output, and execution results.
    """

    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"
    STATUS_LOST = "lost"

    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED, "Failed"),
        (STATUS_LOST, "Lost"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique job identifier",
    )
    target_node = models.ForeignKey(
        WorkerNode,
        on_delete=models.CASCADE,
        related_name="jobs",
        help_text="The worker node this job runs on",
    )
    command = models.TextField(
        help_text="Shell command to execute on the worker node",
    )
    description = models.TextField(
        blank=True,
        help_text="Human-readable description of what this job does",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_QUEUED,
        help_text="Current job status",
    )
    stdout = models.TextField(
        blank=True,
        help_text="Standard output from the command",
    )
    stderr = models.TextField(
        blank=True,
        help_text="Standard error from the command",
    )
    exit_code = models.IntegerField(
        null=True,
        blank=True,
        help_text="Exit code from the command (0 = success)",
    )
    duration_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Execution duration in milliseconds",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "mcp_jobs"
        ordering = ["-created_at"]
        verbose_name = "Job"
        verbose_name_plural = "Jobs"

    def __str__(self):
        cmd_preview = self.command[:50] + "..." if len(self.command) > 50 else self.command
        return f"Job {self.id} ({self.status}): {cmd_preview}"

    @property
    def is_complete(self):
        """Check if the job has finished (succeeded, failed, or lost)."""
        return self.status in (self.STATUS_SUCCEEDED, self.STATUS_FAILED, self.STATUS_LOST)

