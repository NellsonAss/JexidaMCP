"""Backwards-compatible import for Config.

The Config class has been moved to jexida_cli.state.config.
This module provides backwards compatibility.
"""

from .state.config import Config, DEFAULT_CONTEXT_MAX_DEPTH, DEFAULT_CONTEXT_MAX_FILE_SIZE, DEFAULT_CONTEXT_EXCLUDE_PATTERNS

__all__ = [
    "Config",
    "DEFAULT_CONTEXT_MAX_DEPTH",
    "DEFAULT_CONTEXT_MAX_FILE_SIZE",
    "DEFAULT_CONTEXT_EXCLUDE_PATTERNS",
]
