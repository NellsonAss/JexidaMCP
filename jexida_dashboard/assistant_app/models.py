"""Assistant models for conversation management."""

from django.db import models
from django.contrib.auth.models import User


class ConversationMode(models.TextChoices):
    """Conversation modes that affect AI behavior."""
    DEFAULT = "default", "Default"
    TECHNICAL = "technical", "Technical"
    CASUAL = "casual", "Casual"
    BRIEF = "brief", "Brief"
    VERBOSE = "verbose", "Verbose"


class MessageRole(models.TextChoices):
    """Message roles in a conversation."""
    SYSTEM = "system", "System"
    USER = "user", "User"
    ASSISTANT = "assistant", "Assistant"
    TOOL = "tool", "Tool"


class ActionStatus(models.TextChoices):
    """Status of an action log entry."""
    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Confirmed"
    EXECUTED = "executed", "Executed"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class Conversation(models.Model):
    """A conversation session with the AI assistant."""
    
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversations"
    )
    title = models.CharField(max_length=500, blank=True)
    mode = models.CharField(
        max_length=20,
        choices=ConversationMode.choices,
        default=ConversationMode.DEFAULT
    )
    context = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "assistant_conversations"
        ordering = ["-updated_at"]
    
    def __str__(self):
        return f"Conversation {self.id} ({self.user or 'anonymous'})"
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "mode": self.mode,
            "context": self.context,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_count": self.messages.count(),
        }


class Message(models.Model):
    """A message in a conversation."""
    
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages"
    )
    role = models.CharField(
        max_length=20,
        choices=MessageRole.choices
    )
    content = models.TextField(blank=True)
    tool_calls = models.JSONField(null=True, blank=True)
    tool_call_id = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=255, blank=True)
    tokens_used = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "assistant_messages"
        ordering = ["created_at"]
    
    def __str__(self):
        return f"Message {self.id} ({self.role})"
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        result = {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        
        if self.name:
            result["name"] = self.name
        
        return result
    
    def to_openai_format(self):
        """Convert to OpenAI message format."""
        message = {
            "role": self.role,
        }
        
        if self.content:
            message["content"] = self.content
        
        if self.tool_calls:
            message["tool_calls"] = self.tool_calls
        
        if self.tool_call_id:
            message["tool_call_id"] = self.tool_call_id
        
        if self.name:
            message["name"] = self.name
        
        return message


class ActionLog(models.Model):
    """Audit log for AI actions."""
    
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="action_logs"
    )
    action_name = models.CharField(max_length=255, db_index=True)
    action_type = models.CharField(max_length=50)
    parameters = models.JSONField(default=dict)
    result = models.JSONField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ActionStatus.choices,
        default=ActionStatus.PENDING
    )
    confirmation_id = models.CharField(max_length=255, blank=True, db_index=True)
    user_id = models.CharField(max_length=255, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        db_table = "assistant_action_logs"
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"ActionLog {self.id} ({self.action_name})"
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "action_name": self.action_name,
            "action_type": self.action_type,
            "parameters": self.parameters,
            "result": self.result,
            "status": self.status,
            "confirmation_id": self.confirmation_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "error_message": self.error_message,
        }

