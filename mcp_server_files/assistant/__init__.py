"""AI Assistant module for natural language interaction with MCP tools.

This module provides:
- Provider abstraction for OpenAI and Azure OpenAI
- Model introspection for dynamic function calling
- Action registry with permission checking
- Context-aware system prompts
- Conversation management
"""

# Lazy imports to avoid circular dependencies
def get_assistant_router():
    """Get the assistant router (lazy import)."""
    from .router import router
    return router


def get_process_user_message():
    """Get the process_user_message function (lazy import)."""
    from .services import process_user_message
    return process_user_message


def get_handle_function_call():
    """Get the handle_function_call function (lazy import)."""
    from .services import handle_function_call
    return handle_function_call


# For backwards compatibility, also provide direct imports
# These will be loaded when the module is imported
try:
    from .router import router as assistant_router
    from .services import process_user_message, handle_function_call
except ImportError:
    # Handle case where dependencies aren't ready
    assistant_router = None
    process_user_message = None
    handle_function_call = None


__all__ = [
    "process_user_message",
    "handle_function_call",
    "assistant_router",
    "get_assistant_router",
    "get_process_user_message",
    "get_handle_function_call",
]

