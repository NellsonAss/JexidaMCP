"""AI Assistant module for natural language interaction with MCP tools.

This module provides:
- Provider abstraction for OpenAI and Azure OpenAI
- Model introspection for dynamic function calling
- Action registry with permission checking
- Context-aware system prompts
- Conversation management
- Reference context management for dynamic behavior rules
- Real-time progress streaming via SSE
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


def get_process_user_message_streaming():
    """Get the streaming process_user_message function (lazy import)."""
    from .services import process_user_message_streaming
    return process_user_message_streaming


def get_handle_function_call():
    """Get the handle_function_call function (lazy import)."""
    from .services import handle_function_call
    return handle_function_call


def get_progress_emitter():
    """Get the ProgressEmitter class (lazy import)."""
    from .progress import ProgressEmitter
    return ProgressEmitter


def get_reference_service():
    """Get reference service functions (lazy import)."""
    from .references.service import (
        get_references_for_context,
        create_reference_snippet,
        list_reference_snippets,
    )
    return {
        "get_references_for_context": get_references_for_context,
        "create_reference_snippet": create_reference_snippet,
        "list_reference_snippets": list_reference_snippets,
    }


# For backwards compatibility, also provide direct imports
# These will be loaded when the module is imported
try:
    from .router import router as assistant_router
    from .services import process_user_message, handle_function_call, process_user_message_streaming
    from .progress import ProgressEmitter, TaskProgress, TaskStatus, EventType
except ImportError:
    # Handle case where dependencies aren't ready
    assistant_router = None
    process_user_message = None
    process_user_message_streaming = None
    handle_function_call = None
    ProgressEmitter = None
    TaskProgress = None
    TaskStatus = None
    EventType = None


__all__ = [
    "process_user_message",
    "process_user_message_streaming",
    "handle_function_call",
    "assistant_router",
    "get_assistant_router",
    "get_process_user_message",
    "get_process_user_message_streaming",
    "get_handle_function_call",
    "get_progress_emitter",
    "get_reference_service",
    "ProgressEmitter",
    "TaskProgress",
    "TaskStatus",
    "EventType",
]

