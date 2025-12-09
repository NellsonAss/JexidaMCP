"""Assistant message processing services.

Framework-agnostic services for AI assistant message processing.
These functions do NOT depend on any database or web framework.
"""

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..logging import get_logger
from ..actions import get_action_registry
from ..providers import get_provider, ProviderResponse, ToolCall

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


# Base system prompt
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

## Response Style

- Be concise and direct
- Use technical terminology appropriate for system administrators
- When showing data, format it clearly
- If an action fails, explain what went wrong and suggest fixes
"""


def build_system_prompt(
    user_id: Optional[str] = None,
    user_roles: Optional[List[str]] = None,
    page_context: Optional[Dict[str, Any]] = None,
    conversation_mode: Optional[str] = None,
    reference_snippets: Optional[List[Any]] = None,
) -> str:
    """Build the complete system prompt with context.
    
    Args:
        user_id: ID of the current user
        user_roles: List of user's roles
        page_context: Context about what the user is viewing
        conversation_mode: Optional conversation mode
        reference_snippets: Optional list of reference snippets
        
    Returns:
        Complete system prompt string
    """
    parts = [BASE_SYSTEM_PROMPT]
    
    # Add user context
    if user_id or user_roles:
        user_context = _build_user_context(user_id, user_roles)
        if user_context:
            parts.append(f"\n## Current User\n\n{user_context}")
    
    # Add page context
    if page_context:
        page_section = _build_page_context(page_context)
        if page_section:
            parts.append(f"\n## Current Context\n\n{page_section}")
    
    # Add conversation mode context
    if conversation_mode:
        mode_context = _build_mode_context(conversation_mode)
        if mode_context:
            parts.append(f"\n## Mode\n\n{mode_context}")
    
    # Add reference snippets
    if reference_snippets:
        ref_section = _build_reference_section(reference_snippets)
        if ref_section:
            parts.append(f"\n## Reference Material\n\n{ref_section}")
    
    # Add available actions summary
    actions_summary = _build_actions_summary(user_roles)
    if actions_summary:
        parts.append(f"\n## Available Tools\n\n{actions_summary}")
    
    return "\n".join(parts)


def _build_user_context(
    user_id: Optional[str],
    user_roles: Optional[List[str]],
) -> str:
    """Build user context section."""
    lines = []
    
    if user_id:
        lines.append(f"User ID: {user_id}")
    
    if user_roles:
        lines.append(f"Roles: {', '.join(user_roles)}")
        if "admin" in user_roles:
            lines.append("Capabilities: Full access to all models and operations")
        else:
            lines.append("Capabilities: Standard user access")
    
    return "\n".join(lines)


def _build_page_context(page_context: Dict[str, Any]) -> str:
    """Build page context section."""
    lines = []
    
    if "page" in page_context:
        lines.append(f"Current page: {page_context['page']}")
    
    if "path" in page_context:
        lines.append(f"URL path: {page_context['path']}")
    
    if "model" in page_context:
        lines.append(f"Viewing model: {page_context['model']}")
    
    if "record_id" in page_context:
        lines.append(f"Record ID: {page_context['record_id']}")
    
    return "\n".join(lines)


def _build_mode_context(conversation_mode: str) -> str:
    """Build conversation mode context."""
    modes = {
        "technical": "Respond with detailed technical information.",
        "casual": "Respond in a friendly, conversational manner.",
        "brief": "Keep responses extremely short and to the point.",
        "verbose": "Provide detailed explanations and background information.",
    }
    return modes.get(conversation_mode, "")


def _build_reference_section(reference_snippets: List[Any]) -> str:
    """Build the reference material section from snippets."""
    if not reference_snippets:
        return ""
    
    sections = []
    for snippet in reference_snippets:
        title = getattr(snippet, "title", "Reference")
        content = getattr(snippet, "content", str(snippet))
        section = f"### {title}\n\n{content}"
        sections.append(section)
    
    return "\n\n".join(sections)


def _build_actions_summary(user_roles: Optional[List[str]] = None) -> str:
    """Build a summary of available actions."""
    registry = get_action_registry()
    actions = registry.get_available_actions(user_roles)
    
    if not actions:
        return ""
    
    lines = ["You have access to the following tools:"]
    
    for action in actions:
        confirmation = " (requires confirmation)" if action.requires_confirmation else ""
        lines.append(f"- `{action.name}`: {action.description}{confirmation}")
    
    return "\n".join(lines)


def build_conversation_messages(
    messages: List[Dict[str, Any]],
    system_prompt: str,
) -> List[Dict[str, Any]]:
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
    """
    return len(text) // 4


def truncate_context(
    messages: List[Dict[str, Any]],
    max_tokens: int = 8000,
    preserve_last: int = 4,
) -> List[Dict[str, Any]]:
    """Truncate conversation history to fit within token limits.
    
    Args:
        messages: Conversation messages
        max_tokens: Maximum tokens to allow
        preserve_last: Number of recent messages to always keep
        
    Returns:
        Truncated message list
    """
    if not messages:
        return []
    
    preserved = messages[-preserve_last:] if len(messages) > preserve_last else messages
    earlier = messages[:-preserve_last] if len(messages) > preserve_last else []
    
    preserved_tokens = sum(
        estimate_token_count(str(m.get("content", "")))
        for m in preserved
    )
    
    remaining_budget = max_tokens - preserved_tokens
    
    included = []
    for msg in reversed(earlier):
        msg_tokens = estimate_token_count(str(msg.get("content", "")))
        if msg_tokens <= remaining_budget:
            included.insert(0, msg)
            remaining_budget -= msg_tokens
        else:
            break
    
    return included + preserved


async def process_message(
    content: str,
    conversation_history: List[Dict[str, Any]],
    user_id: Optional[str] = None,
    user_roles: Optional[List[str]] = None,
    page_context: Optional[Dict[str, Any]] = None,
    mode: Optional[str] = None,
    temperature: Optional[float] = None,
    max_iterations: int = 10,
) -> Dict[str, Any]:
    """Process a user message and generate an AI response.
    
    This is a framework-agnostic processing function. The caller is responsible
    for managing conversation persistence.
    
    Args:
        content: User message content
        conversation_history: Previous messages in OpenAI format
        user_id: ID of the user
        user_roles: User's roles for permission checking
        page_context: Context about current page/view
        mode: Conversation mode
        temperature: Sampling temperature
        max_iterations: Maximum agentic loop iterations
        
    Returns:
        Dictionary with:
        - content: str (assistant's response)
        - tool_calls: Optional list of tool call results
        - tokens_used: int
    """
    # Build system prompt
    system_prompt = build_system_prompt(
        user_id=user_id,
        user_roles=user_roles,
        page_context=page_context,
        conversation_mode=mode,
    )
    
    # Add user message to history
    messages = conversation_history + [{"role": "user", "content": content}]
    
    # Truncate if needed
    messages = truncate_context(messages)
    
    # Build full message list
    full_messages = build_conversation_messages(messages, system_prompt)
    
    # Get function definitions
    functions = get_function_definitions(user_roles)
    
    # Get provider
    provider = get_provider()
    
    if not provider.is_configured():
        return {
            "content": "I'm sorry, but the AI assistant is not currently configured.",
            "tool_calls": None,
            "tokens_used": 0,
        }
    
    # Process with potential tool calling loop
    return await _process_with_tools(
        provider=provider,
        messages=full_messages,
        functions=functions,
        user_id=user_id,
        user_roles=user_roles,
        temperature=temperature,
        max_iterations=max_iterations,
    )


async def _process_with_tools(
    provider,
    messages: List[Dict[str, Any]],
    functions: List[Dict[str, Any]],
    user_id: Optional[str],
    user_roles: Optional[List[str]],
    temperature: Optional[float],
    max_iterations: int,
) -> Dict[str, Any]:
    """Process messages with tool calling support."""
    import json
    
    all_tool_results = []
    total_tokens = 0
    iteration = 0
    
    current_messages = messages.copy()
    registry = get_action_registry()
    
    while iteration < max_iterations:
        iteration += 1
        
        # Call the LLM
        call_params = {
            "messages": current_messages,
            "functions": functions if functions else None,
        }
        if temperature is not None:
            call_params["temperature"] = temperature
        
        response = await provider.chat_completion(**call_params)
        total_tokens += response.total_tokens
        
        # Check if we have tool calls
        if not response.has_tool_calls:
            return {
                "content": response.content or "",
                "tool_calls": all_tool_results if all_tool_results else None,
                "tokens_used": total_tokens,
            }
        
        # Process tool calls
        tool_results = []
        for tc in response.tool_calls:
            try:
                action_result = await registry.execute(
                    name=tc.name,
                    parameters=tc.arguments,
                    user_id=user_id,
                    user_roles=user_roles,
                )
                tool_results.append({
                    "tool_call_id": tc.id,
                    "action_name": tc.name,
                    "success": action_result.success,
                    "message": action_result.message,
                    "result": action_result.to_dict(),
                })
            except Exception as e:
                tool_results.append({
                    "tool_call_id": tc.id,
                    "action_name": tc.name,
                    "success": False,
                    "message": str(e),
                    "result": {"error": str(e)},
                })
        
        all_tool_results.extend(tool_results)
        
        # Add assistant message and tool results to context
        current_messages.append({
            "role": "assistant",
            "content": response.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in response.tool_calls
            ],
        })
        
        for result in tool_results:
            current_messages.append({
                "role": "tool",
                "tool_call_id": result["tool_call_id"],
                "content": json.dumps(result.get("result", {})),
            })
    
    # Max iterations reached
    return {
        "content": "I apologize, but I encountered too many steps. Please simplify your request.",
        "tool_calls": all_tool_results,
        "tokens_used": total_tokens,
    }

