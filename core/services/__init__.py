"""Core business logic services.

Framework-agnostic services for:
- Assistant message processing
- Secret encryption/decryption
- Monitoring data aggregation
"""

from .assistant import (
    process_message,
    build_system_prompt,
    build_conversation_messages,
    get_function_definitions,
    truncate_context,
)
from .secrets import (
    encrypt_value,
    decrypt_value,
    get_fernet,
)

__all__ = [
    # Assistant
    "process_message",
    "build_system_prompt",
    "build_conversation_messages",
    "get_function_definitions",
    "truncate_context",
    # Secrets
    "encrypt_value",
    "decrypt_value",
    "get_fernet",
]

