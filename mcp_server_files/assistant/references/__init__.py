"""Reference Context Management for AI Assistant.

This module provides:
- ReferenceSnippet: Reusable prompt fragments with targeting
- ReferenceProfile: Collections of snippets for different environments
- ReferenceLog: Audit trail of which references influenced each response
- Service functions for CRUD and context-aware selection
"""

from .models import (
    ReferenceCategory,
    ReferenceSnippet,
    ReferenceProfile,
    ReferenceProfileSnippet,
    ReferenceLog,
)
from .service import (
    get_references_for_context,
    create_reference_snippet,
    update_reference_snippet,
    list_reference_snippets,
    get_reference_snippet_by_key,
    create_reference_profile,
    add_snippet_to_profile,
    remove_snippet_from_profile,
    list_reference_profiles,
    get_reference_profile_by_key,
    create_reference_log,
    get_reference_logs_for_conversation,
)

__all__ = [
    # Models
    "ReferenceCategory",
    "ReferenceSnippet",
    "ReferenceProfile",
    "ReferenceProfileSnippet",
    "ReferenceLog",
    # Service functions
    "get_references_for_context",
    "create_reference_snippet",
    "update_reference_snippet",
    "list_reference_snippets",
    "get_reference_snippet_by_key",
    "create_reference_profile",
    "add_snippet_to_profile",
    "remove_snippet_from_profile",
    "list_reference_profiles",
    "get_reference_profile_by_key",
    "create_reference_log",
    "get_reference_logs_for_conversation",
]


