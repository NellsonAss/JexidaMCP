"""Main assistant service for processing user messages.

Handles:
- Message processing with LLM
- Function call execution
- Conversation management
- Multi-step agentic planning
"""

import json
import sys
import os
from typing import Any, Dict, List, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from logging_config import get_logger

from .providers import get_provider, ProviderResponse, ToolCall
from .context import (
    build_system_prompt,
    build_conversation_messages,
    get_function_definitions,
    truncate_context,
)
from .actions import get_action_registry, ActionResult
from .models import (
    Conversation,
    Message,
    MessageRole,
    ActionLog,
    ActionStatus,
    ConversationMode,
    get_conversation_messages,
    create_conversation,
    add_message,
    log_action,
    update_action_log,
)

logger = get_logger(__name__)

# Maximum iterations for agentic loops
MAX_ITERATIONS = 10


async def process_user_message(
    content: str,
    conversation_id: Optional[int] = None,
    user_id: Optional[str] = None,
    user_roles: Optional[List[str]] = None,
    page_context: Optional[Dict[str, Any]] = None,
    mode: Optional[ConversationMode] = None,
    temperature: Optional[float] = None,
    db_session=None,
) -> Dict[str, Any]:
    """Process a user message and generate an AI response.
    
    Args:
        content: User message content
        conversation_id: Existing conversation ID (creates new if None)
        user_id: ID of the user
        user_roles: User's roles for permission checking
        page_context: Context about current page/view
        mode: Conversation mode
        temperature: Sampling temperature (0.0-2.0), or None for model default
        db_session: SQLAlchemy session
        
    Returns:
        Dictionary with:
        - conversation_id: int
        - message_id: int (assistant's message)
        - content: str (assistant's response)
        - tool_calls: Optional list of tool calls
        - pending_confirmations: Optional list of pending confirmations
        - tokens_used: int
    """
    from database import get_db
    
    # Get database session
    if db_session is None:
        db_session = next(get_db())
        should_close = True
    else:
        should_close = False
    
    try:
        # Get or create conversation
        conversation = None
        if conversation_id:
            conversation = db_session.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
        
        if conversation is None:
            conversation = create_conversation(
                db_session,
                user_id=user_id,
                mode=mode or ConversationMode.DEFAULT,
                context=page_context or {},
            )
            logger.info(
                f"Created new conversation: {conversation.id}",
                extra={"conversation_id": conversation.id, "user_id": user_id}
            )
        
        # Save user message
        user_message = add_message(
            db_session,
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=content,
        )
        
        # Get conversation history
        messages = get_conversation_messages(db_session, conversation.id)
        message_list = [msg.to_openai_format() for msg in messages]
        
        # Build system prompt
        system_prompt = build_system_prompt(
            user_id=user_id,
            user_roles=user_roles,
            page_context=page_context or conversation.context,
            conversation_mode=conversation.mode.value if conversation.mode else None,
        )
        
        # Truncate context if needed
        message_list = truncate_context(message_list)
        
        # Build full message list
        full_messages = build_conversation_messages(message_list, system_prompt)
        
        # Get function definitions
        functions = get_function_definitions(user_roles)
        
        # Get provider
        provider = get_provider()
        
        if not provider.is_configured():
            logger.warning("LLM provider not configured")
            return {
                "conversation_id": conversation.id,
                "message_id": 0,
                "content": "I'm sorry, but the AI assistant is not currently configured. Please contact an administrator.",
                "tokens_used": 0,
            }
        
        # Process with potential agentic loop
        result = await _process_with_tools(
            provider=provider,
            messages=full_messages,
            functions=functions,
            conversation=conversation,
            user_id=user_id,
            user_roles=user_roles,
            temperature=temperature,
            db_session=db_session,
        )
        
        return result
    
    finally:
        if should_close:
            db_session.close()


async def _process_with_tools(
    provider,
    messages: List[Dict[str, Any]],
    functions: List[Dict[str, Any]],
    conversation: Conversation,
    user_id: Optional[str],
    user_roles: Optional[List[str]],
    temperature: Optional[float],
    db_session,
) -> Dict[str, Any]:
    """Process messages with tool calling support.
    
    Implements an agentic loop that continues until the model
    returns a response without tool calls.
    """
    all_tool_results = []
    pending_confirmations = []
    total_tokens = 0
    iteration = 0
    
    current_messages = messages.copy()
    
    while iteration < MAX_ITERATIONS:
        iteration += 1
        
        logger.debug(
            f"Processing iteration {iteration}",
            extra={"conversation_id": conversation.id, "iteration": iteration}
        )
        
        # Call the LLM
        # Use provided temperature or let provider use model default
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
            # No more tool calls, save and return the response
            assistant_message = add_message(
                db_session,
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content=response.content,
                tokens_used=response.total_tokens,
            )
            
            return {
                "conversation_id": conversation.id,
                "message_id": assistant_message.id,
                "content": response.content or "",
                "tool_calls": all_tool_results if all_tool_results else None,
                "pending_confirmations": pending_confirmations if pending_confirmations else None,
                "tokens_used": total_tokens,
            }
        
        # Process tool calls
        tool_results = await _execute_tool_calls(
            tool_calls=response.tool_calls,
            conversation=conversation,
            user_id=user_id,
            user_roles=user_roles,
            db_session=db_session,
        )
        
        all_tool_results.extend(tool_results)
        
        # Collect pending confirmations
        for result in tool_results:
            if result.get("requires_confirmation"):
                pending_confirmations.append({
                    "confirmation_id": result.get("confirmation_id"),
                    "action_name": result.get("action_name"),
                    "message": result.get("message"),
                })
        
        # Save assistant message with tool calls
        assistant_message = add_message(
            db_session,
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=response.content,
            tool_calls=[
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
            tokens_used=response.total_tokens,
        )
        
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
        
        # Add tool responses
        for result in tool_results:
            tool_message = add_message(
                db_session,
                conversation_id=conversation.id,
                role=MessageRole.TOOL,
                content=json.dumps(result.get("result", {})),
                tool_call_id=result.get("tool_call_id"),
                name=result.get("action_name"),
            )
            
            current_messages.append({
                "role": "tool",
                "tool_call_id": result.get("tool_call_id"),
                "content": json.dumps(result.get("result", {})),
            })
    
    # Max iterations reached
    logger.warning(
        f"Max iterations reached for conversation {conversation.id}",
        extra={"conversation_id": conversation.id, "iterations": MAX_ITERATIONS}
    )
    
    return {
        "conversation_id": conversation.id,
        "message_id": 0,
        "content": "I apologize, but I encountered too many steps while trying to help. Please try simplifying your request.",
        "tool_calls": all_tool_results,
        "pending_confirmations": pending_confirmations if pending_confirmations else None,
        "tokens_used": total_tokens,
    }


async def _execute_tool_calls(
    tool_calls: List[ToolCall],
    conversation: Conversation,
    user_id: Optional[str],
    user_roles: Optional[List[str]],
    db_session,
) -> List[Dict[str, Any]]:
    """Execute a list of tool calls.
    
    Returns:
        List of result dictionaries
    """
    registry = get_action_registry()
    results = []
    
    for tc in tool_calls:
        logger.info(
            f"Executing tool call: {tc.name}",
            extra={
                "conversation_id": conversation.id,
                "tool_call_id": tc.id,
                "tool_name": tc.name,
            }
        )
        
        # Execute the action
        action_result = await registry.execute(
            name=tc.name,
            parameters=tc.arguments,
            user_id=user_id,
            user_roles=user_roles,
        )
        
        # Log the action
        action = registry.get(tc.name)
        action_log = log_action(
            db_session,
            action_name=tc.name,
            action_type=action.action_type.value if action else "execute",
            parameters=tc.arguments,
            user_id=user_id,
            conversation_id=conversation.id,
            confirmation_id=action_result.confirmation_id if action_result.requires_confirmation else None,
        )
        
        if action_result.success and not action_result.requires_confirmation:
            update_action_log(
                db_session,
                log_id=action_log.id,
                status=ActionStatus.EXECUTED,
                result=action_result.to_dict(),
            )
        elif not action_result.success:
            update_action_log(
                db_session,
                log_id=action_log.id,
                status=ActionStatus.FAILED,
                error_message=action_result.error,
            )
        
        results.append({
            "tool_call_id": tc.id,
            "action_name": tc.name,
            "success": action_result.success,
            "message": action_result.message,
            "result": action_result.to_dict(),
            "requires_confirmation": action_result.requires_confirmation,
            "confirmation_id": action_result.confirmation_id,
        })
    
    return results


async def handle_function_call(
    conversation_id: int,
    user_id: Optional[str],
    user_roles: Optional[List[str]],
    function_name: str,
    arguments: Dict[str, Any],
    db_session=None,
) -> ActionResult:
    """Handle a direct function call (not from LLM).
    
    Args:
        conversation_id: Conversation ID
        user_id: User ID
        user_roles: User's roles
        function_name: Name of the function to call
        arguments: Function arguments
        db_session: SQLAlchemy session
        
    Returns:
        ActionResult from execution
    """
    from database import get_db
    
    if db_session is None:
        db_session = next(get_db())
        should_close = True
    else:
        should_close = False
    
    try:
        registry = get_action_registry()
        
        result = await registry.execute(
            name=function_name,
            parameters=arguments,
            user_id=user_id,
            user_roles=user_roles,
        )
        
        # Log the action
        action = registry.get(function_name)
        log_action(
            db_session,
            action_name=function_name,
            action_type=action.action_type.value if action else "execute",
            parameters=arguments,
            user_id=user_id,
            conversation_id=conversation_id,
            confirmation_id=result.confirmation_id if result.requires_confirmation else None,
        )
        
        return result
    
    finally:
        if should_close:
            db_session.close()


async def confirm_pending_action(
    confirmation_id: str,
    user_id: Optional[str] = None,
    db_session=None,
) -> ActionResult:
    """Confirm and execute a pending action.
    
    Args:
        confirmation_id: Confirmation ID
        user_id: User ID
        db_session: SQLAlchemy session
        
    Returns:
        ActionResult from execution
    """
    from database import get_db
    
    if db_session is None:
        db_session = next(get_db())
        should_close = True
    else:
        should_close = False
    
    try:
        registry = get_action_registry()
        
        result = await registry.confirm_action(confirmation_id, user_id)
        
        # Update action log
        action_log = db_session.query(ActionLog).filter(
            ActionLog.confirmation_id == confirmation_id
        ).first()
        
        if action_log:
            if result.success:
                update_action_log(
                    db_session,
                    log_id=action_log.id,
                    status=ActionStatus.EXECUTED,
                    result=result.to_dict(),
                )
            else:
                update_action_log(
                    db_session,
                    log_id=action_log.id,
                    status=ActionStatus.FAILED,
                    error_message=result.error,
                )
        
        return result
    
    finally:
        if should_close:
            db_session.close()


async def cancel_pending_action(
    confirmation_id: str,
    user_id: Optional[str] = None,
    db_session=None,
) -> bool:
    """Cancel a pending action.
    
    Args:
        confirmation_id: Confirmation ID
        user_id: User ID
        db_session: SQLAlchemy session
        
    Returns:
        True if cancelled, False if not found
    """
    from database import get_db
    
    if db_session is None:
        db_session = next(get_db())
        should_close = True
    else:
        should_close = False
    
    try:
        registry = get_action_registry()
        
        cancelled = registry.cancel_confirmation(confirmation_id)
        
        if cancelled:
            # Update action log
            action_log = db_session.query(ActionLog).filter(
                ActionLog.confirmation_id == confirmation_id
            ).first()
            
            if action_log:
                update_action_log(
                    db_session,
                    log_id=action_log.id,
                    status=ActionStatus.CANCELLED,
                )
        
        return cancelled
    
    finally:
        if should_close:
            db_session.close()


def get_assistant_status() -> Dict[str, Any]:
    """Get the status of the assistant service.
    
    Returns:
        Status dictionary
    """
    provider = get_provider()
    registry = get_action_registry()
    
    return {
        "provider": provider.provider_name,
        "is_configured": provider.is_configured(),
        "model": provider.default_model,
        "available_actions": len(registry.list_actions()),
    }

