"""Context builder for AI assistant system prompts.

Builds system prompts with domain knowledge, user context, permissions,
and current page context.
"""

import sys
import os
from typing import Any, Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from logging_config import get_logger

from .actions import get_action_registry

logger = get_logger(__name__)


# Base system prompt - customize for your application
BASE_SYSTEM_PROMPT = """You are an AI assistant for JexidaMCP, a network management and automation platform.

You help users manage:
- Azure cloud resources (subscriptions, cost management, CLI operations)
- UniFi network infrastructure (devices, security, hardening)
- Synology NAS systems (storage, backups, services)
- Secrets and credentials (secure storage, configuration)

## CRITICAL: Action-First Approach

**GET IT DONE FIRST, FOLLOW UP LATER.**

When the user asks you to do something:
1. Optional fields missing? Leave them blank. Mention briefly AFTER success.
2. Required fields missing but can infer? Use inferred value. Don't explain.
3. Required fields missing and CAN'T infer? Ask ONE brief question, then proceed.
4. NEVER ask for verbal confirmation - system shows popup automatically.
5. Keep responses SHORT. One sentence is often enough.

## Tool Usage Rules

**CRITICAL: USE DEFAULTS - DON'T ASK**

1. **All tools have pre-configured defaults**. Call tools without optional parameters.
2. **NEVER ask about site_id, subscription_id, or controller address** - these are pre-configured.
3. **For "how many" questions**: Call the appropriate list tool, count the results, respond with the number.
4. **For device queries**: `unifi_list_devices` gives all UniFi network infrastructure (switches, APs, gateways).
5. **For network security**: Use `unifi_get_security_settings` without parameters.
6. **For Azure costs**: Use `azure_cost_get_summary` with just the subscription_id from configured infrastructure.
7. **For Synology**: All synology_* tools work without parameters for basic queries.

**Examples of correct behavior:**
- User: "how many devices on my network?" → Call `unifi_list_devices()`, count, respond: "You have 12 devices."
- User: "show my azure costs" → Call `azure_cost_get_summary(subscription_id=<configured>)`
- User: "list files on nas" → Call `synology_list_files()` with defaults

## Available Actions

Use the available function calls to:
- `model_query`: Search records in any data model
- `model_create`: Create new records (popup confirms)
- `model_update`: Update existing records (popup confirms)
- `model_delete`: Delete records (popup confirms)

## Data Models

Available models and their purposes:
- `Secret`: Encrypted credentials and configuration values

## Response Style

- Be concise and direct
- Use technical terminology appropriate for system administrators
- When showing data, format it clearly
- If an action fails, explain what went wrong and suggest fixes
- Don't apologize excessively - just fix the issue
"""


def build_system_prompt(
    user_id: Optional[str] = None,
    user_roles: Optional[List[str]] = None,
    page_context: Optional[Dict[str, Any]] = None,
    conversation_mode: Optional[str] = None,
) -> str:
    """Build the complete system prompt with context.
    
    Args:
        user_id: ID of the current user
        user_roles: List of user's roles
        page_context: Context about what the user is viewing
        conversation_mode: Optional conversation mode (e.g., "technical", "casual")
        
    Returns:
        Complete system prompt string
    """
    parts = [BASE_SYSTEM_PROMPT]
    
    # Add infrastructure context (what systems are configured)
    # This is critical for the AI to know what tools it can use with defaults
    infra_context = build_infrastructure_context()
    if infra_context:
        parts.append(f"\n## Configured Infrastructure\n\n{infra_context}")
    
    # Add user context
    if user_id or user_roles:
        user_context = build_user_context(user_id, user_roles)
        if user_context:
            parts.append(f"\n## Current User\n\n{user_context}")
    
    # Add page context
    if page_context:
        page_section = build_page_context(page_context)
        if page_section:
            parts.append(f"\n## Current Context\n\n{page_section}")
    
    # Add conversation mode context
    if conversation_mode:
        mode_context = build_mode_context(conversation_mode)
        if mode_context:
            parts.append(f"\n## Mode\n\n{mode_context}")
    
    # Add available actions summary
    actions_summary = build_actions_summary(user_roles)
    if actions_summary:
        parts.append(f"\n## Available Tools\n\n{actions_summary}")
    
    return "\n".join(parts)


def build_user_context(
    user_id: Optional[str],
    user_roles: Optional[List[str]],
) -> str:
    """Build user context section.
    
    Args:
        user_id: User ID
        user_roles: User's roles
        
    Returns:
        User context string
    """
    lines = []
    
    if user_id:
        lines.append(f"User ID: {user_id}")
    
    if user_roles:
        lines.append(f"Roles: {', '.join(user_roles)}")
        
        # Add role-specific capabilities
        if "admin" in user_roles:
            lines.append("Capabilities: Full access to all models and operations")
        else:
            lines.append("Capabilities: Standard user access")
    
    return "\n".join(lines)


def build_page_context(page_context: Dict[str, Any]) -> str:
    """Build page context section.
    
    Args:
        page_context: Dictionary with page information
        
    Returns:
        Page context string
    """
    lines = []
    
    # Current page/view
    if "page" in page_context:
        lines.append(f"Current page: {page_context['page']}")
    
    if "path" in page_context:
        lines.append(f"URL path: {page_context['path']}")
    
    # Selected items
    if "selected_items" in page_context:
        items = page_context["selected_items"]
        if items:
            lines.append(f"Selected items: {len(items)} item(s)")
    
    # Current model/entity being viewed
    if "model" in page_context:
        lines.append(f"Viewing model: {page_context['model']}")
    
    if "record_id" in page_context:
        lines.append(f"Record ID: {page_context['record_id']}")
    
    # Filters or search context
    if "filters" in page_context:
        filters = page_context["filters"]
        if filters:
            filter_str = ", ".join(f"{k}={v}" for k, v in filters.items())
            lines.append(f"Active filters: {filter_str}")
    
    # Any additional context
    if "extra" in page_context:
        for key, value in page_context["extra"].items():
            lines.append(f"{key}: {value}")
    
    return "\n".join(lines)


def build_mode_context(conversation_mode: str) -> str:
    """Build conversation mode context.
    
    Args:
        conversation_mode: Mode identifier
        
    Returns:
        Mode context string
    """
    modes = {
        "technical": (
            "Respond with detailed technical information. "
            "Include command examples and configuration details."
        ),
        "casual": (
            "Respond in a friendly, conversational manner. "
            "Simplify technical details where appropriate."
        ),
        "brief": (
            "Keep responses extremely short and to the point. "
            "No explanations unless explicitly requested."
        ),
        "verbose": (
            "Provide detailed explanations and background information. "
            "Include related information that might be helpful."
        ),
    }
    
    return modes.get(conversation_mode, "")


def build_actions_summary(user_roles: Optional[List[str]] = None) -> str:
    """Build a summary of available actions.
    
    Args:
        user_roles: User's roles for filtering
        
    Returns:
        Actions summary string
    """
    registry = get_action_registry()
    actions = registry.get_available_actions(user_roles)
    
    if not actions:
        return ""
    
    lines = ["You have access to the following tools:"]
    
    for action in actions:
        confirmation = " (requires confirmation)" if action.requires_confirmation else ""
        lines.append(f"- `{action.name}`: {action.description}{confirmation}")
    
    return "\n".join(lines)


def build_infrastructure_context() -> str:
    """Build context about configured infrastructure.
    
    Reads from settings to inform the AI what systems are available
    and pre-configured, so it can use tools without asking for
    parameters that already have defaults.
    
    Returns:
        Infrastructure context string describing available systems
    """
    try:
        from config import get_settings
        settings = get_settings()
    except Exception as e:
        logger.warning(f"Could not load settings for infrastructure context: {e}")
        return ""
    
    lines = []
    
    # UniFi Controller
    if settings.unifi_controller_url:
        lines.append(f"- **UniFi Network**: Controller at `{settings.unifi_controller_url}` (site: `{settings.unifi_site}`)")
        lines.append("  - Use `unifi_list_devices` for device counts - no parameters needed")
        lines.append("  - Use `unifi_get_security_settings` for security config - no parameters needed")
        lines.append("  - The site_id is pre-configured, never ask the user for it")
    
    # Azure
    if settings.azure_default_subscription:
        lines.append(f"- **Azure**: Subscription `{settings.azure_default_subscription}` is configured")
        lines.append("  - Use this subscription_id for all Azure tools")
        lines.append("  - Never ask the user which subscription to use")
    
    # Synology NAS
    if settings.synology_url:
        lines.append(f"- **Synology NAS**: `{settings.synology_url}` is configured")
        lines.append("  - All synology_* tools work without parameters for basic operations")
        lines.append("  - Never ask for NAS address or credentials")
    
    return "\n".join(lines) if lines else ""


def build_conversation_messages(
    messages: List[Dict[str, Any]],
    system_prompt: str,
) -> List[Dict[str, str]]:
    """Build the message list for the LLM request.
    
    Args:
        messages: Conversation history
        system_prompt: System prompt to use
        
    Returns:
        List of messages in OpenAI format
    """
    result = [{"role": "system", "content": system_prompt}]
    
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        
        message: Dict[str, Any] = {"role": role, "content": content}
        
        # Include tool call information if present
        if "tool_calls" in msg:
            message["tool_calls"] = msg["tool_calls"]
        
        if "tool_call_id" in msg:
            message["tool_call_id"] = msg["tool_call_id"]
        
        if "name" in msg:
            message["name"] = msg["name"]
        
        result.append(message)
    
    return result


def get_function_definitions(
    user_roles: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Get function definitions for available actions.
    
    Args:
        user_roles: User's roles for permission filtering
        
    Returns:
        List of function definitions in OpenAI format
    """
    registry = get_action_registry()
    return registry.get_function_definitions(user_roles)


def estimate_token_count(text: str) -> int:
    """Estimate the token count for a text string.
    
    Uses a simple heuristic: ~4 characters per token.
    
    Args:
        text: Text to estimate
        
    Returns:
        Estimated token count
    """
    return len(text) // 4


def truncate_context(
    messages: List[Dict[str, Any]],
    max_tokens: int = 8000,
    preserve_last: int = 4,
) -> List[Dict[str, Any]]:
    """Truncate conversation history to fit within token limits.
    
    Preserves the most recent messages while removing older ones.
    
    Args:
        messages: Conversation messages
        max_tokens: Maximum tokens to allow
        preserve_last: Number of recent messages to always keep
        
    Returns:
        Truncated message list
    """
    if not messages:
        return []
    
    # Always keep the last N messages
    preserved = messages[-preserve_last:] if len(messages) > preserve_last else messages
    earlier = messages[:-preserve_last] if len(messages) > preserve_last else []
    
    # Calculate tokens for preserved messages
    preserved_tokens = sum(
        estimate_token_count(str(m.get("content", "")))
        for m in preserved
    )
    
    # Calculate remaining budget
    remaining_budget = max_tokens - preserved_tokens
    
    # Add earlier messages from most recent to oldest
    included = []
    for msg in reversed(earlier):
        msg_tokens = estimate_token_count(str(msg.get("content", "")))
        if msg_tokens <= remaining_budget:
            included.insert(0, msg)
            remaining_budget -= msg_tokens
        else:
            break
    
    return included + preserved

