"""Pydantic schemas for assistant API requests and responses."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, Field


class ConversationMode(str, Enum):
    """Conversation modes."""
    DEFAULT = "default"
    TECHNICAL = "technical"
    CASUAL = "casual"
    BRIEF = "brief"
    VERBOSE = "verbose"


class ChatRequest(BaseModel):
    """Request to send a message to the assistant."""
    message: str = Field(..., description="User message content")
    conversation_id: Optional[int] = Field(
        None,
        description="Existing conversation ID (creates new if not provided)"
    )
    page_context: Optional[Dict[str, Any]] = Field(
        None,
        description="Context about current page/view"
    )
    mode: Optional[ConversationMode] = Field(
        None,
        description="Conversation mode"
    )
    temperature: Optional[float] = Field(
        None,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0.0-2.0). Only used if model supports it."
    )


class ChatResponse(BaseModel):
    """Response from the assistant."""
    conversation_id: int = Field(..., description="Conversation ID")
    message_id: int = Field(..., description="Assistant message ID")
    content: str = Field(..., description="Assistant response content")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Tool calls made by the assistant"
    )
    pending_confirmations: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Actions requiring user confirmation"
    )
    tokens_used: Optional[int] = Field(
        None,
        description="Total tokens used in this request"
    )
    
    class Config:
        from_attributes = True


class ConfirmActionRequest(BaseModel):
    """Request to confirm a pending action."""
    confirmation_id: str = Field(..., description="Confirmation ID")


class ConfirmActionResponse(BaseModel):
    """Response from confirming an action."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ConversationListItem(BaseModel):
    """Summary of a conversation for listing."""
    id: int
    title: Optional[str]
    mode: str
    message_count: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ConversationDetail(BaseModel):
    """Full conversation with messages."""
    id: int
    user_id: Optional[str]
    title: Optional[str]
    mode: str
    context: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    messages: List[Dict[str, Any]]
    
    class Config:
        from_attributes = True


class MessageSchema(BaseModel):
    """A message in a conversation."""
    id: int
    conversation_id: int
    role: str
    content: Optional[str]
    tool_calls: Optional[List[Dict[str, Any]]]
    tool_call_id: Optional[str]
    name: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ActionLogSchema(BaseModel):
    """Action log entry."""
    id: int
    conversation_id: Optional[int]
    action_name: str
    action_type: str
    parameters: Dict[str, Any]
    result: Optional[Dict[str, Any]]
    status: str
    confirmation_id: Optional[str]
    user_id: Optional[str]
    created_at: datetime
    executed_at: Optional[datetime]
    error_message: Optional[str]
    
    class Config:
        from_attributes = True


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    title: Optional[str] = Field(None, description="Optional conversation title")
    mode: ConversationMode = Field(
        ConversationMode.DEFAULT,
        description="Conversation mode"
    )
    context: Optional[Dict[str, Any]] = Field(
        None,
        description="Initial context"
    )


class UpdateConversationRequest(BaseModel):
    """Request to update a conversation."""
    title: Optional[str] = None
    mode: Optional[ConversationMode] = None
    context: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class AssistantStatus(BaseModel):
    """Status of the assistant service."""
    provider: str = Field(..., description="Active LLM provider name")
    is_configured: bool = Field(..., description="Whether provider is configured")
    model: str = Field(..., description="Default model being used")
    available_actions: int = Field(..., description="Number of available actions")

