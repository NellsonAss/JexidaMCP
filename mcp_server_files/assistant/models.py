"""Database models for conversation management.

Provides SQLAlchemy models for storing:
- Conversations with users
- Messages (user, assistant, tool calls)
- Action logs for audit trail
"""

import sys
import os
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import Base


class ConversationMode(str, Enum):
    """Conversation modes that affect AI behavior."""
    DEFAULT = "default"
    TECHNICAL = "technical"
    CASUAL = "casual"
    BRIEF = "brief"
    VERBOSE = "verbose"


class MessageRole(str, Enum):
    """Message roles in a conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ActionStatus(str, Enum):
    """Status of an action log entry."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    EXECUTED = "executed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Conversation(Base):
    """A conversation session with the AI assistant.
    
    Attributes:
        id: Unique conversation ID
        user_id: ID of the user who owns this conversation
        title: Optional title for the conversation
        mode: Conversation mode (affects AI behavior)
        context: JSON context data (page context, etc.)
        is_active: Whether the conversation is currently active
        created_at: When the conversation was started
        updated_at: When the conversation was last updated
    """
    __tablename__ = "assistant_conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), index=True, nullable=True)
    title = Column(String(500), nullable=True)
    mode = Column(
        SQLEnum(ConversationMode),
        default=ConversationMode.DEFAULT,
        nullable=False
    )
    context = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    messages = relationship(
        "Message",
        back_populates="conversation",
        order_by="Message.created_at",
        cascade="all, delete-orphan",
    )
    action_logs = relationship(
        "ActionLog",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, user_id={self.user_id})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "mode": self.mode.value if self.mode else "default",
            "context": self.context,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_count": len(self.messages) if self.messages else 0,
        }


class Message(Base):
    """A message in a conversation.
    
    Attributes:
        id: Unique message ID
        conversation_id: ID of the parent conversation
        role: Message role (system, user, assistant, tool)
        content: Message content
        tool_calls: JSON array of tool calls (for assistant messages)
        tool_call_id: ID of the tool call this message responds to
        name: Function name (for tool messages)
        tokens_used: Number of tokens in this message
        created_at: When the message was created
    """
    __tablename__ = "assistant_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        Integer,
        ForeignKey("assistant_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(SQLEnum(MessageRole), nullable=False)
    content = Column(Text, nullable=True)
    tool_calls = Column(JSON, nullable=True)  # For assistant messages with tool calls
    tool_call_id = Column(String(255), nullable=True)  # For tool response messages
    name = Column(String(255), nullable=True)  # Function name for tool messages
    tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    
    def __repr__(self) -> str:
        return f"<Message(id={self.id}, role={self.role}, conversation_id={self.conversation_id})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role.value if self.role else "user",
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
    
    def to_openai_format(self) -> Dict[str, Any]:
        """Convert to OpenAI message format."""
        message: Dict[str, Any] = {
            "role": self.role.value if self.role else "user",
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


class ActionLog(Base):
    """Audit log for AI actions.
    
    Records all actions taken by the AI assistant for auditing,
    debugging, and rollback purposes.
    
    Attributes:
        id: Unique log ID
        conversation_id: ID of the conversation
        action_name: Name of the action performed
        action_type: Type of action (query, create, update, delete, execute)
        parameters: JSON parameters passed to the action
        result: JSON result from the action
        status: Current status of the action
        confirmation_id: ID for pending confirmations
        user_id: ID of the user who triggered the action
        created_at: When the action was initiated
        executed_at: When the action was executed
        error_message: Error message if failed
    """
    __tablename__ = "assistant_action_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        Integer,
        ForeignKey("assistant_conversations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    action_name = Column(String(255), nullable=False, index=True)
    action_type = Column(String(50), nullable=False)
    parameters = Column(JSON, default=dict)
    result = Column(JSON, nullable=True)
    status = Column(
        SQLEnum(ActionStatus),
        default=ActionStatus.PENDING,
        nullable=False
    )
    confirmation_id = Column(String(255), nullable=True, index=True)
    user_id = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    executed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="action_logs")
    
    def __repr__(self) -> str:
        return f"<ActionLog(id={self.id}, action={self.action_name}, status={self.status})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "action_name": self.action_name,
            "action_type": self.action_type,
            "parameters": self.parameters,
            "result": self.result,
            "status": self.status.value if self.status else "pending",
            "confirmation_id": self.confirmation_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "error_message": self.error_message,
        }


def get_conversation_messages(
    db_session,
    conversation_id: int,
    limit: Optional[int] = None,
) -> List[Message]:
    """Get messages for a conversation.
    
    Args:
        db_session: SQLAlchemy session
        conversation_id: ID of the conversation
        limit: Optional limit on number of messages
        
    Returns:
        List of Message objects
    """
    query = db_session.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at)
    
    if limit:
        query = query.limit(limit)
    
    return query.all()


def create_conversation(
    db_session,
    user_id: Optional[str] = None,
    title: Optional[str] = None,
    mode: ConversationMode = ConversationMode.DEFAULT,
    context: Optional[Dict[str, Any]] = None,
) -> Conversation:
    """Create a new conversation.
    
    Args:
        db_session: SQLAlchemy session
        user_id: User ID
        title: Optional title
        mode: Conversation mode
        context: Initial context
        
    Returns:
        Created Conversation object
    """
    conversation = Conversation(
        user_id=user_id,
        title=title,
        mode=mode,
        context=context or {},
    )
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)
    return conversation


def add_message(
    db_session,
    conversation_id: int,
    role: MessageRole,
    content: Optional[str] = None,
    tool_calls: Optional[List[Dict]] = None,
    tool_call_id: Optional[str] = None,
    name: Optional[str] = None,
    tokens_used: int = 0,
) -> Message:
    """Add a message to a conversation.
    
    Args:
        db_session: SQLAlchemy session
        conversation_id: ID of the conversation
        role: Message role
        content: Message content
        tool_calls: Tool calls (for assistant messages)
        tool_call_id: Tool call ID (for tool messages)
        name: Function name (for tool messages)
        tokens_used: Number of tokens used
        
    Returns:
        Created Message object
    """
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        tool_calls=tool_calls,
        tool_call_id=tool_call_id,
        name=name,
        tokens_used=tokens_used,
    )
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)
    
    # Update conversation's updated_at
    conversation = db_session.query(Conversation).filter(
        Conversation.id == conversation_id
    ).first()
    if conversation:
        conversation.updated_at = datetime.utcnow()
        db_session.commit()
    
    return message


def log_action(
    db_session,
    action_name: str,
    action_type: str,
    parameters: Dict[str, Any],
    user_id: Optional[str] = None,
    conversation_id: Optional[int] = None,
    confirmation_id: Optional[str] = None,
) -> ActionLog:
    """Create an action log entry.
    
    Args:
        db_session: SQLAlchemy session
        action_name: Name of the action
        action_type: Type of action
        parameters: Action parameters
        user_id: User ID
        conversation_id: Conversation ID
        confirmation_id: Confirmation ID if pending
        
    Returns:
        Created ActionLog object
    """
    status = ActionStatus.PENDING if confirmation_id else ActionStatus.EXECUTED
    
    log = ActionLog(
        conversation_id=conversation_id,
        action_name=action_name,
        action_type=action_type,
        parameters=parameters,
        status=status,
        confirmation_id=confirmation_id,
        user_id=user_id,
    )
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)
    return log


def update_action_log(
    db_session,
    log_id: int,
    status: ActionStatus,
    result: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
) -> Optional[ActionLog]:
    """Update an action log entry.
    
    Args:
        db_session: SQLAlchemy session
        log_id: ID of the log entry
        status: New status
        result: Action result
        error_message: Error message if failed
        
    Returns:
        Updated ActionLog or None if not found
    """
    log = db_session.query(ActionLog).filter(ActionLog.id == log_id).first()
    
    if log:
        log.status = status
        log.result = result
        log.error_message = error_message
        
        if status in (ActionStatus.EXECUTED, ActionStatus.FAILED):
            log.executed_at = datetime.utcnow()
        
        db_session.commit()
        db_session.refresh(log)
    
    return log

