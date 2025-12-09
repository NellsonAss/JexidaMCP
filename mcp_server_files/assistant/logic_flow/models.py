"""Database models for AI Logic Flow versioning and logging.

Provides SQLAlchemy models for:
- AILogicVersion: Tracks versions of AI logic/strategy
- AILogicFlowLog: Captures step-by-step flow details for analysis
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
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from database import Base


class LogicStepType(str, Enum):
    """Types of steps in the AI logic flow."""
    
    # Initialization steps
    FLOW_START = "flow_start"           # Processing begins
    CONVERSATION_LOAD = "conversation_load"  # Load/create conversation
    
    # Context building steps  
    CONTEXT_BUILD = "context_build"     # Building system prompt context
    REFERENCE_FETCH = "reference_fetch" # Fetching reference snippets
    HISTORY_LOAD = "history_load"       # Loading conversation history
    CONTEXT_TRUNCATE = "context_truncate"  # Truncating context for limits
    
    # LLM interaction steps
    LLM_CALL = "llm_call"              # Calling the LLM
    LLM_RESPONSE = "llm_response"      # Receiving LLM response
    
    # Tool execution steps
    TOOL_DECISION = "tool_decision"    # AI decides to use tools
    TOOL_EXECUTE = "tool_execute"      # Executing a tool call
    TOOL_RESULT = "tool_result"        # Tool execution result
    
    # Iteration steps
    ITERATION_START = "iteration_start"  # Starting agentic loop iteration
    ITERATION_END = "iteration_end"      # Ending iteration
    
    # Completion steps
    MESSAGE_SAVE = "message_save"      # Saving assistant message
    FLOW_END = "flow_end"              # Processing complete
    FLOW_ERROR = "flow_error"          # Error occurred


class AILogicVersion(Base):
    """Tracks versions of AI logic/strategy for analysis.
    
    Each version represents a distinct configuration of the AI behavior,
    allowing isolation of conversations for evaluation and A/B testing.
    
    Attributes:
        id: Unique version ID
        version_id: Semantic version string (e.g., "v1.2.0")
        name: Human-readable name for this version
        description: What changed or what this version represents
        configuration: JSON storing configuration parameters
        system_prompt_hash: Hash of base system prompt for drift detection
        max_iterations: Max agentic loop iterations in this version
        is_active: Whether this is the currently active version
        is_baseline: Whether this is a baseline for comparison
        created_at: When version was created
        deprecated_at: When version was deprecated (if applicable)
    """
    __tablename__ = "ai_logic_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Configuration snapshot
    configuration = Column(JSON, nullable=False, default=dict)
    """
    Configuration JSON structure:
    {
        "max_iterations": 10,
        "temperature": null,  # null = use model default
        "system_prompt_version": "v1.0",
        "tools_enabled": ["model_query", "model_create", ...],
        "reference_profile": "default",
        "changes_from_previous": "Added tool X, updated system prompt",
    }
    """
    
    # Hash for drift detection
    system_prompt_hash = Column(String(64), nullable=True)
    
    # Key parameters (denormalized for easy querying)
    max_iterations = Column(Integer, default=10, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=False, nullable=False, index=True)
    is_baseline = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    deprecated_at = Column(DateTime, nullable=True)
    
    # Relationships
    flow_logs = relationship(
        "AILogicFlowLog",
        back_populates="logic_version",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<AILogicVersion(version_id={self.version_id}, is_active={self.is_active})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "version_id": self.version_id,
            "name": self.name,
            "description": self.description,
            "configuration": self.configuration,
            "system_prompt_hash": self.system_prompt_hash,
            "max_iterations": self.max_iterations,
            "is_active": self.is_active,
            "is_baseline": self.is_baseline,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "deprecated_at": self.deprecated_at.isoformat() if self.deprecated_at else None,
        }
    
    def to_summary(self) -> Dict[str, Any]:
        """Convert to minimal summary for logging."""
        return {
            "id": self.id,
            "version_id": self.version_id,
            "name": self.name,
            "is_active": self.is_active,
        }


class AILogicFlowLog(Base):
    """Captures step-by-step flow details for analysis.
    
    Each row represents one step in the AI processing flow, allowing
    detailed analysis of how the AI arrives at responses.
    
    Attributes:
        id: Unique log ID
        logic_version_id: Which AI logic version was used
        conversation_id: Associated conversation
        message_id: Associated message (assistant response)
        turn_index: Which turn in the conversation (0-based)
        
        step_type: Type of step (from LogicStepType enum)
        step_name: Human-readable step description
        step_order: Order within this turn (0-based)
        
        input_data: What went into this step (JSON)
        output_data: What came out (JSON)
        
        duration_ms: How long the step took in milliseconds
        tokens_used: Tokens used in this step (for LLM calls)
        
        metadata: Additional metadata (JSON)
        error_message: Error message if step failed
        
        created_at: Timestamp of the step
    """
    __tablename__ = "ai_logic_flow_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Version tracking (critical for analysis)
    logic_version_id = Column(
        Integer,
        ForeignKey("ai_logic_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    # Conversation context
    conversation_id = Column(Integer, nullable=True, index=True)
    message_id = Column(Integer, nullable=True, index=True)
    turn_index = Column(Integer, nullable=True)
    
    # Step details
    step_type = Column(SQLEnum(LogicStepType), nullable=False, index=True)
    step_name = Column(String(255), nullable=False)
    step_order = Column(Integer, default=0, nullable=False)
    
    # Input/Output capture
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    
    # Performance metrics
    duration_ms = Column(Float, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    
    # Additional context
    metadata = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    logic_version = relationship("AILogicVersion", back_populates="flow_logs")
    
    def __repr__(self) -> str:
        return f"<AILogicFlowLog(id={self.id}, step_type={self.step_type}, conversation_id={self.conversation_id})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "logic_version_id": self.logic_version_id,
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "turn_index": self.turn_index,
            "step_type": self.step_type.value if self.step_type else None,
            "step_name": self.step_name,
            "step_order": self.step_order,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "duration_ms": self.duration_ms,
            "tokens_used": self.tokens_used,
            "metadata": self.metadata,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
    
    def to_summary(self) -> Dict[str, Any]:
        """Convert to minimal summary for quick views."""
        return {
            "id": self.id,
            "step_type": self.step_type.value if self.step_type else None,
            "step_name": self.step_name,
            "step_order": self.step_order,
            "duration_ms": self.duration_ms,
            "tokens_used": self.tokens_used,
            "has_error": self.error_message is not None,
        }

