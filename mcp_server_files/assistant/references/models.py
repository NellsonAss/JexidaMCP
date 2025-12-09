"""Database models for Reference Context Management.

Provides SQLAlchemy models for storing:
- ReferenceSnippet: Reusable prompt fragments with metadata and targeting
- ReferenceProfile: Named collections of snippets
- ReferenceProfileSnippet: Join table for profile-snippet relationships
- ReferenceLog: Audit log of references used per assistant response
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
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from database import Base


class ReferenceCategory(str, Enum):
    """Categories for reference snippets."""
    SYSTEM_BEHAVIOR = "system_behavior"      # Core rules, philosophy
    TOOL_USAGE = "tool_usage"                # Examples for tools (few-shot)
    DOMAIN_KNOWLEDGE = "domain_knowledge"    # Domain snippets (Azure, UniFi, etc.)
    STYLE_GUIDE = "style_guide"              # Tone, conversation modes
    PAGE_CONTEXT = "page_context"            # Page/screen-specific context
    ROLE_CONTEXT = "role_context"            # Role-specific snippets
    OTHER = "other"


class ReferenceSnippet(Base):
    """A reusable prompt snippet with targeting metadata.
    
    Reference snippets are the building blocks of dynamic system prompts.
    Each snippet can be targeted to specific:
    - Tools (e.g., only include when unifi_list_devices is available)
    - Roles (e.g., only for admin users)
    - Modes (e.g., only in technical mode)
    - Pages (e.g., only on /devices page)
    
    Attributes:
        id: Unique snippet ID
        key: Unique identifier key (e.g., "core.it_assistant.behavior.v1")
        title: Human-readable label
        category: Category for organization
        content: The actual prompt text
        tags: JSON list of tags for filtering
        applicable_tools: JSON list of tool names this applies to
        applicable_roles: JSON list of role names this applies to
        applicable_modes: JSON list of conversation modes
        applicable_pages: JSON list of page paths
        is_active: Whether this snippet is currently active
        version: Version number for tracking changes
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    __tablename__ = "reference_snippets"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    category = Column(
        SQLEnum(ReferenceCategory),
        nullable=False,
        default=ReferenceCategory.OTHER
    )
    
    content = Column(Text, nullable=False)
    
    # Tagging / targeting (stored as JSON arrays)
    tags = Column(JSON, default=list)
    applicable_tools = Column(JSON, default=None)    # e.g., ["unifi_list_devices"]
    applicable_roles = Column(JSON, default=None)    # e.g., ["admin", "network_admin"]
    applicable_modes = Column(JSON, default=None)    # e.g., ["technical", "verbose"]
    applicable_pages = Column(JSON, default=None)    # e.g., ["/devices", "/azure/vms"]
    
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Versioning / audit
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    profile_associations = relationship(
        "ReferenceProfileSnippet",
        back_populates="snippet",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<ReferenceSnippet(key={self.key}, category={self.category})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "key": self.key,
            "title": self.title,
            "category": self.category.value if self.category else "other",
            "content": self.content,
            "tags": self.tags or [],
            "applicable_tools": self.applicable_tools,
            "applicable_roles": self.applicable_roles,
            "applicable_modes": self.applicable_modes,
            "applicable_pages": self.applicable_pages,
            "is_active": self.is_active,
            "version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def to_log_entry(self) -> Dict[str, Any]:
        """Convert to minimal dict for reference log entries."""
        return {
            "id": self.id,
            "key": self.key,
            "title": self.title,
            "category": self.category.value if self.category else "other",
            "version": self.version,
            "tags": self.tags or [],
        }


class ReferenceProfile(Base):
    """A named collection of reference snippets.
    
    Profiles allow grouping snippets into presets that can be applied
    to different environments or use cases, e.g.:
    - "Default IT Assistant"
    - "Azure Power User"
    - "Network Hardening Mode"
    
    Attributes:
        id: Unique profile ID
        key: Unique identifier key (e.g., "profile.default_it_assistant")
        name: Human-readable name
        description: Optional description
        is_default: Whether this is the default profile
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    __tablename__ = "reference_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_default = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    snippet_associations = relationship(
        "ReferenceProfileSnippet",
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="ReferenceProfileSnippet.order_index",
    )
    
    def __repr__(self) -> str:
        return f"<ReferenceProfile(key={self.key}, name={self.name})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "is_default": self.is_default,
            "snippet_count": len(self.snippet_associations) if self.snippet_associations else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ReferenceProfileSnippet(Base):
    """Join table linking profiles to snippets with ordering.
    
    Allows the same snippet to be in multiple profiles with
    different ordering positions.
    
    Attributes:
        id: Unique association ID
        profile_id: Foreign key to profile
        snippet_id: Foreign key to snippet
        order_index: Position in the profile (lower = earlier in prompt)
    """
    __tablename__ = "reference_profile_snippets"
    
    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(
        Integer,
        ForeignKey("reference_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    snippet_id = Column(
        Integer,
        ForeignKey("reference_snippets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_index = Column(Integer, default=0, nullable=False)
    
    # Relationships
    profile = relationship("ReferenceProfile", back_populates="snippet_associations")
    snippet = relationship("ReferenceSnippet", back_populates="profile_associations")
    
    # Ensure unique profile-snippet pairs
    __table_args__ = (
        UniqueConstraint("profile_id", "snippet_id", name="uq_profile_snippet"),
    )
    
    def __repr__(self) -> str:
        return f"<ReferenceProfileSnippet(profile_id={self.profile_id}, snippet_id={self.snippet_id})>"


class ReferenceLog(Base):
    """Audit log of which references were used for each assistant response.
    
    This log enables debugging and tuning of the reference system by
    showing exactly which snippets influenced each AI response.
    
    Attributes:
        id: Unique log ID
        conversation_id: FK to conversation (if available)
        message_id: FK to assistant message (if available)
        turn_index: Alternative to message_id for tracking position
        assembled_system_prompt: The exact system prompt sent to the model
        referenced_snippets: JSON array of snippet metadata used
        model_id: Which model handled this turn
        strategy_id: Which strategy was used (if any)
        profile_key: Which profile was active
        created_at: Log timestamp
    """
    __tablename__ = "reference_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    conversation_id = Column(Integer, nullable=True, index=True)
    message_id = Column(Integer, nullable=True, index=True)
    turn_index = Column(Integer, nullable=True)
    
    # The actual assembled prompt
    assembled_system_prompt = Column(Text, nullable=False)
    
    # Metadata about references used (JSON array)
    # Format: [{"id": 1, "key": "...", "title": "...", "category": "...", "version": 1, "tags": [...]}]
    referenced_snippets = Column(JSON, nullable=False, default=list)
    
    # Model/strategy metadata
    model_id = Column(String(255), nullable=True)
    strategy_id = Column(String(255), nullable=True)
    profile_key = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self) -> str:
        return f"<ReferenceLog(id={self.id}, conversation_id={self.conversation_id})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "turn_index": self.turn_index,
            "assembled_system_prompt": self.assembled_system_prompt,
            "referenced_snippets": self.referenced_snippets,
            "model_id": self.model_id,
            "strategy_id": self.strategy_id,
            "profile_key": self.profile_key,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


