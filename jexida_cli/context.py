"""Backwards-compatible import for ContextManager.

The context management has been moved to jexida_cli.state.session.
This module provides backwards compatibility by aliasing Session as ContextManager.
"""

from .state.session import Session, DEFAULT_EXCLUDE_PATTERNS, TEXT_FILE_EXTENSIONS, MAX_FILE_SIZE_BYTES

# Alias for backwards compatibility
ContextManager = Session

__all__ = [
    "ContextManager",
    "Session",
    "DEFAULT_EXCLUDE_PATTERNS",
    "TEXT_FILE_EXTENSIONS",
    "MAX_FILE_SIZE_BYTES",
]
