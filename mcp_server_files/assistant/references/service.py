"""Service functions for Reference Context Management.

Provides:
- Context-aware reference selection (get_references_for_context)
- CRUD operations for snippets and profiles
- Reference logging for audit trail
"""

import sys
import os
from typing import Any, Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from logging_config import get_logger

from .models import (
    ReferenceCategory,
    ReferenceSnippet,
    ReferenceProfile,
    ReferenceProfileSnippet,
    ReferenceLog,
)

logger = get_logger(__name__)


# Default profile key
DEFAULT_PROFILE_KEY = "profile.default_it_assistant"


# -----------------------------------------------------------------------------
# Context-Aware Reference Selection
# -----------------------------------------------------------------------------

def get_references_for_context(
    db_session,
    profile_key: Optional[str] = None,
    user_roles: Optional[List[str]] = None,
    page_context: Optional[Dict[str, Any]] = None,
    mode: Optional[str] = None,
    tools_hint: Optional[List[str]] = None,
) -> List[ReferenceSnippet]:
    """Get relevant reference snippets for the current context.
    
    Selection logic:
    1. Start with snippets from the selected profile (or default profile)
    2. Filter to is_active=True
    3. Apply soft filters for roles, modes, pages, and tools
    4. Sort by order_index from profile association
    
    Args:
        db_session: SQLAlchemy session
        profile_key: Profile key to use (falls back to default profile)
        user_roles: User's roles for filtering
        page_context: Dict with page info (path, model, etc.)
        mode: Conversation mode (e.g., "technical", "casual")
        tools_hint: List of tool names that might be used
        
    Returns:
        Ordered list of ReferenceSnippet objects to include in system prompt
    """
    # Get the profile
    profile = None
    if profile_key:
        profile = db_session.query(ReferenceProfile).filter(
            ReferenceProfile.key == profile_key
        ).first()
    
    # Fall back to default profile
    if profile is None:
        profile = db_session.query(ReferenceProfile).filter(
            ReferenceProfile.is_default == True
        ).first()
    
    if profile is None:
        logger.warning("No reference profile found, returning empty list")
        return []
    
    # Get all active snippets from the profile, ordered
    associations = (
        db_session.query(ReferenceProfileSnippet)
        .filter(ReferenceProfileSnippet.profile_id == profile.id)
        .join(ReferenceSnippet)
        .filter(ReferenceSnippet.is_active == True)
        .order_by(ReferenceProfileSnippet.order_index)
        .all()
    )
    
    # Extract snippets
    snippets = [assoc.snippet for assoc in associations]
    
    # Apply soft filters
    filtered = []
    page_path = page_context.get("path") if page_context else None
    
    for snippet in snippets:
        # Check role applicability
        if snippet.applicable_roles:
            if not user_roles or not _has_intersection(snippet.applicable_roles, user_roles):
                continue
        
        # Check mode applicability
        if snippet.applicable_modes:
            if not mode or mode not in snippet.applicable_modes:
                continue
        
        # Check page applicability
        if snippet.applicable_pages:
            if not page_path or not _matches_page(page_path, snippet.applicable_pages):
                continue
        
        # Check tool applicability
        if snippet.applicable_tools:
            if not tools_hint or not _has_intersection(snippet.applicable_tools, tools_hint):
                continue
        
        filtered.append(snippet)
    
    logger.debug(
        f"Selected {len(filtered)} references from profile '{profile.key}'",
        extra={
            "profile_key": profile.key,
            "total_snippets": len(snippets),
            "filtered_snippets": len(filtered),
        }
    )
    
    return filtered


def _has_intersection(list_a: List[str], list_b: List[str]) -> bool:
    """Check if two lists have any common elements."""
    return bool(set(list_a) & set(list_b))


def _matches_page(page_path: str, applicable_pages: List[str]) -> bool:
    """Check if page_path matches any of the applicable pages.
    
    Supports both exact matches and prefix matches (e.g., "/azure/*").
    """
    for pattern in applicable_pages:
        if pattern.endswith("*"):
            # Prefix match
            if page_path.startswith(pattern[:-1]):
                return True
        else:
            # Exact match
            if page_path == pattern:
                return True
    return False


# -----------------------------------------------------------------------------
# Snippet CRUD
# -----------------------------------------------------------------------------

def create_reference_snippet(
    db_session,
    key: str,
    title: str,
    content: str,
    category: ReferenceCategory = ReferenceCategory.OTHER,
    tags: Optional[List[str]] = None,
    applicable_tools: Optional[List[str]] = None,
    applicable_roles: Optional[List[str]] = None,
    applicable_modes: Optional[List[str]] = None,
    applicable_pages: Optional[List[str]] = None,
    is_active: bool = True,
) -> ReferenceSnippet:
    """Create a new reference snippet.
    
    Args:
        db_session: SQLAlchemy session
        key: Unique key for the snippet
        title: Human-readable title
        content: The prompt text
        category: Category classification
        tags: Optional list of tags
        applicable_tools: Optional list of tool names
        applicable_roles: Optional list of role names
        applicable_modes: Optional list of conversation modes
        applicable_pages: Optional list of page paths
        is_active: Whether the snippet is active
        
    Returns:
        Created ReferenceSnippet
    """
    snippet = ReferenceSnippet(
        key=key,
        title=title,
        content=content,
        category=category,
        tags=tags or [],
        applicable_tools=applicable_tools,
        applicable_roles=applicable_roles,
        applicable_modes=applicable_modes,
        applicable_pages=applicable_pages,
        is_active=is_active,
    )
    db_session.add(snippet)
    db_session.commit()
    db_session.refresh(snippet)
    
    logger.info(f"Created reference snippet: {key}")
    return snippet


def update_reference_snippet(
    db_session,
    snippet_id: int,
    **kwargs,
) -> Optional[ReferenceSnippet]:
    """Update an existing reference snippet.
    
    Args:
        db_session: SQLAlchemy session
        snippet_id: ID of the snippet to update
        **kwargs: Fields to update
        
    Returns:
        Updated ReferenceSnippet or None if not found
    """
    snippet = db_session.query(ReferenceSnippet).filter(
        ReferenceSnippet.id == snippet_id
    ).first()
    
    if snippet is None:
        return None
    
    # Increment version if content changes
    if "content" in kwargs and kwargs["content"] != snippet.content:
        snippet.version += 1
    
    # Update fields
    updatable_fields = [
        "title", "content", "category", "tags",
        "applicable_tools", "applicable_roles", "applicable_modes", "applicable_pages",
        "is_active",
    ]
    
    for field in updatable_fields:
        if field in kwargs:
            setattr(snippet, field, kwargs[field])
    
    db_session.commit()
    db_session.refresh(snippet)
    
    logger.info(f"Updated reference snippet: {snippet.key} (id={snippet_id})")
    return snippet


def list_reference_snippets(
    db_session,
    filters: Optional[Dict[str, Any]] = None,
) -> List[ReferenceSnippet]:
    """List reference snippets with optional filtering.
    
    Args:
        db_session: SQLAlchemy session
        filters: Optional dict with filter criteria:
            - category: ReferenceCategory or string
            - is_active: bool
            - tag: str (matches if in tags list)
            
    Returns:
        List of ReferenceSnippet objects
    """
    query = db_session.query(ReferenceSnippet)
    
    if filters:
        if "category" in filters:
            category = filters["category"]
            if isinstance(category, str):
                category = ReferenceCategory(category)
            query = query.filter(ReferenceSnippet.category == category)
        
        if "is_active" in filters:
            query = query.filter(ReferenceSnippet.is_active == filters["is_active"])
    
    return query.order_by(ReferenceSnippet.key).all()


def get_reference_snippet_by_key(
    db_session,
    key: str,
) -> Optional[ReferenceSnippet]:
    """Get a reference snippet by its key.
    
    Args:
        db_session: SQLAlchemy session
        key: Unique key of the snippet
        
    Returns:
        ReferenceSnippet or None if not found
    """
    return db_session.query(ReferenceSnippet).filter(
        ReferenceSnippet.key == key
    ).first()


def deactivate_reference_snippet(
    db_session,
    snippet_id: int,
) -> bool:
    """Deactivate a reference snippet (soft delete).
    
    Args:
        db_session: SQLAlchemy session
        snippet_id: ID of the snippet to deactivate
        
    Returns:
        True if deactivated, False if not found
    """
    snippet = db_session.query(ReferenceSnippet).filter(
        ReferenceSnippet.id == snippet_id
    ).first()
    
    if snippet is None:
        return False
    
    snippet.is_active = False
    db_session.commit()
    
    logger.info(f"Deactivated reference snippet: {snippet.key}")
    return True


# -----------------------------------------------------------------------------
# Profile CRUD
# -----------------------------------------------------------------------------

def create_reference_profile(
    db_session,
    key: str,
    name: str,
    description: Optional[str] = None,
    is_default: bool = False,
) -> ReferenceProfile:
    """Create a new reference profile.
    
    Args:
        db_session: SQLAlchemy session
        key: Unique key for the profile
        name: Human-readable name
        description: Optional description
        is_default: Whether this is the default profile
        
    Returns:
        Created ReferenceProfile
    """
    # If setting as default, clear other defaults
    if is_default:
        db_session.query(ReferenceProfile).filter(
            ReferenceProfile.is_default == True
        ).update({"is_default": False})
    
    profile = ReferenceProfile(
        key=key,
        name=name,
        description=description,
        is_default=is_default,
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    
    logger.info(f"Created reference profile: {key}")
    return profile


def list_reference_profiles(
    db_session,
) -> List[ReferenceProfile]:
    """List all reference profiles.
    
    Args:
        db_session: SQLAlchemy session
        
    Returns:
        List of ReferenceProfile objects
    """
    return db_session.query(ReferenceProfile).order_by(ReferenceProfile.name).all()


def get_reference_profile_by_key(
    db_session,
    key: str,
) -> Optional[ReferenceProfile]:
    """Get a reference profile by its key.
    
    Args:
        db_session: SQLAlchemy session
        key: Unique key of the profile
        
    Returns:
        ReferenceProfile or None if not found
    """
    return db_session.query(ReferenceProfile).filter(
        ReferenceProfile.key == key
    ).first()


def add_snippet_to_profile(
    db_session,
    profile_id: int,
    snippet_id: int,
    order_index: int = 0,
) -> Optional[ReferenceProfileSnippet]:
    """Add a snippet to a profile.
    
    Args:
        db_session: SQLAlchemy session
        profile_id: ID of the profile
        snippet_id: ID of the snippet to add
        order_index: Position in the profile
        
    Returns:
        Created ReferenceProfileSnippet or None if profile/snippet not found
    """
    # Verify profile and snippet exist
    profile = db_session.query(ReferenceProfile).filter(
        ReferenceProfile.id == profile_id
    ).first()
    snippet = db_session.query(ReferenceSnippet).filter(
        ReferenceSnippet.id == snippet_id
    ).first()
    
    if profile is None or snippet is None:
        return None
    
    # Check if already associated
    existing = db_session.query(ReferenceProfileSnippet).filter(
        ReferenceProfileSnippet.profile_id == profile_id,
        ReferenceProfileSnippet.snippet_id == snippet_id,
    ).first()
    
    if existing:
        # Update order if already exists
        existing.order_index = order_index
        db_session.commit()
        db_session.refresh(existing)
        return existing
    
    # Create new association
    association = ReferenceProfileSnippet(
        profile_id=profile_id,
        snippet_id=snippet_id,
        order_index=order_index,
    )
    db_session.add(association)
    db_session.commit()
    db_session.refresh(association)
    
    logger.info(f"Added snippet {snippet.key} to profile {profile.key}")
    return association


def remove_snippet_from_profile(
    db_session,
    profile_id: int,
    snippet_id: int,
) -> bool:
    """Remove a snippet from a profile.
    
    Args:
        db_session: SQLAlchemy session
        profile_id: ID of the profile
        snippet_id: ID of the snippet to remove
        
    Returns:
        True if removed, False if association not found
    """
    association = db_session.query(ReferenceProfileSnippet).filter(
        ReferenceProfileSnippet.profile_id == profile_id,
        ReferenceProfileSnippet.snippet_id == snippet_id,
    ).first()
    
    if association is None:
        return False
    
    db_session.delete(association)
    db_session.commit()
    
    logger.info(f"Removed snippet from profile (profile_id={profile_id}, snippet_id={snippet_id})")
    return True


# -----------------------------------------------------------------------------
# Reference Logging
# -----------------------------------------------------------------------------

def create_reference_log(
    db_session,
    assembled_system_prompt: str,
    referenced_snippets: List[ReferenceSnippet],
    conversation_id: Optional[int] = None,
    message_id: Optional[int] = None,
    turn_index: Optional[int] = None,
    model_id: Optional[str] = None,
    strategy_id: Optional[str] = None,
    profile_key: Optional[str] = None,
) -> ReferenceLog:
    """Create a reference log entry.
    
    Args:
        db_session: SQLAlchemy session
        assembled_system_prompt: The full system prompt sent to model
        referenced_snippets: List of ReferenceSnippet objects used
        conversation_id: ID of the conversation
        message_id: ID of the assistant message
        turn_index: Turn index if message_id not available
        model_id: ID/name of the model used
        strategy_id: ID of the strategy used
        profile_key: Key of the profile used
        
    Returns:
        Created ReferenceLog
    """
    # Build snippet metadata for logging
    snippets_payload = [snippet.to_log_entry() for snippet in referenced_snippets]
    
    log_entry = ReferenceLog(
        conversation_id=conversation_id,
        message_id=message_id,
        turn_index=turn_index,
        assembled_system_prompt=assembled_system_prompt,
        referenced_snippets=snippets_payload,
        model_id=model_id,
        strategy_id=strategy_id,
        profile_key=profile_key,
    )
    db_session.add(log_entry)
    db_session.commit()
    db_session.refresh(log_entry)
    
    logger.debug(
        f"Created reference log: {log_entry.id}",
        extra={
            "conversation_id": conversation_id,
            "message_id": message_id,
            "snippet_count": len(snippets_payload),
        }
    )
    
    return log_entry


def get_reference_logs_for_conversation(
    db_session,
    conversation_id: int,
) -> List[ReferenceLog]:
    """Get all reference logs for a conversation.
    
    Args:
        db_session: SQLAlchemy session
        conversation_id: ID of the conversation
        
    Returns:
        List of ReferenceLog objects
    """
    return (
        db_session.query(ReferenceLog)
        .filter(ReferenceLog.conversation_id == conversation_id)
        .order_by(ReferenceLog.created_at)
        .all()
    )


def get_reference_log_by_message(
    db_session,
    message_id: int,
) -> Optional[ReferenceLog]:
    """Get the reference log for a specific message.
    
    Args:
        db_session: SQLAlchemy session
        message_id: ID of the assistant message
        
    Returns:
        ReferenceLog or None if not found
    """
    return db_session.query(ReferenceLog).filter(
        ReferenceLog.message_id == message_id
    ).first()


