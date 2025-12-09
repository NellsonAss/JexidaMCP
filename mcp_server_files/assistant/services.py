"""Main assistant service for processing user messages.

Handles:
- Message processing with LLM
- Function call execution
- Conversation management
- Multi-step agentic planning
- Reference context management and logging
- Real-time progress streaming via SSE
- Versioned AI logic flow logging for analysis
"""

import json
import sys
import os
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

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
from .progress import ProgressEmitter, TaskStatus, EventType
from .logic_flow import FlowLogger, LogicStepType, ensure_logic_version_exists

logger = get_logger(__name__)


def _get_reference_service():
    """Lazy import of reference service to avoid circular imports."""
    try:
        from .references.service import (
            get_references_for_context,
            create_reference_log,
        )
        return get_references_for_context, create_reference_log
    except ImportError as e:
        logger.debug(f"Reference service not available: {e}")
        return None, None

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
    reference_profile_key: Optional[str] = None,
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
        reference_profile_key: Optional key of reference profile to use
        
    Returns:
        Dictionary with:
        - conversation_id: int
        - message_id: int (assistant's message)
        - content: str (assistant's response)
        - tool_calls: Optional list of tool calls
        - pending_confirmations: Optional list of pending confirmations
        - tokens_used: int
        - reference_log_id: int (ID of the reference log entry)
        - logic_version_id: str (version of AI logic used)
        - flow_summary: dict (summary of processing flow)
    """
    from database import get_db
    
    # Get database session
    if db_session is None:
        db_session = next(get_db())
        should_close = True
    else:
        should_close = False
    
    # Initialize flow logger
    flow_logger = FlowLogger(
        db_session=db_session,
        conversation_id=conversation_id,
    )
    
    try:
        # Log flow start
        flow_logger.log_step(
            step_type=LogicStepType.FLOW_START,
            step_name="Processing user message",
            input_data={
                "content_length": len(content),
                "has_conversation_id": conversation_id is not None,
                "mode": mode.value if mode else None,
                "has_page_context": page_context is not None,
            },
        )
        
        # Get or create conversation
        with flow_logger.timed_step(
            step_type=LogicStepType.CONVERSATION_LOAD,
            step_name="Load/create conversation",
            input_data={"conversation_id": conversation_id},
        ) as step:
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
            
            step.output_data = {
                "conversation_id": conversation.id,
                "is_new": conversation_id is None,
            }
            
            # Update flow logger with conversation ID
            flow_logger.set_conversation_id(conversation.id)
        
        # Save user message
        user_message = add_message(
            db_session,
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=content,
        )
        
        # Get conversation history
        with flow_logger.timed_step(
            step_type=LogicStepType.HISTORY_LOAD,
            step_name="Load conversation history",
        ) as step:
            messages = get_conversation_messages(db_session, conversation.id)
            message_list = [msg.to_openai_format() for msg in messages]
            
            # Calculate turn index for this response
            turn_index = len([m for m in messages if m.role == MessageRole.ASSISTANT])
            flow_logger.turn_index = turn_index
            
            step.output_data = {
                "message_count": len(messages),
                "turn_index": turn_index,
            }
        
        # Get reference snippets for context
        with flow_logger.timed_step(
            step_type=LogicStepType.REFERENCE_FETCH,
            step_name="Fetch reference snippets",
        ) as step:
            get_references_for_context, create_reference_log = _get_reference_service()
            reference_snippets = []
            
            # Determine profile key (from parameter, page_context, or default)
            effective_profile_key = reference_profile_key
            if effective_profile_key is None and page_context:
                effective_profile_key = page_context.get("reference_profile_key")
            
            # Get list of available tools for reference filtering
            registry = get_action_registry()
            tools_hint = [action.name for action in registry.list_actions()]
            
            if get_references_for_context is not None:
                try:
                    reference_snippets = get_references_for_context(
                        db_session=db_session,
                        profile_key=effective_profile_key,
                        user_roles=user_roles,
                        page_context=page_context or conversation.context,
                        mode=conversation.mode.value if conversation.mode else None,
                        tools_hint=tools_hint,
                    )
                    logger.debug(
                        f"Selected {len(reference_snippets)} reference snippets",
                        extra={
                            "conversation_id": conversation.id,
                            "profile_key": effective_profile_key,
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to get reference snippets: {e}")
                    reference_snippets = []
            
            step.output_data = {
                "snippet_count": len(reference_snippets),
                "profile_key": effective_profile_key,
            }
        
        # Build system prompt with references
        with flow_logger.timed_step(
            step_type=LogicStepType.CONTEXT_BUILD,
            step_name="Build system prompt and context",
        ) as step:
            system_prompt = build_system_prompt(
                user_id=user_id,
                user_roles=user_roles,
                page_context=page_context or conversation.context,
                conversation_mode=conversation.mode.value if conversation.mode else None,
                reference_profile_key=effective_profile_key,
                reference_snippets=reference_snippets,
            )
            
            # Truncate context if needed
            original_count = len(message_list)
            message_list = truncate_context(message_list)
            
            # Build full message list
            full_messages = build_conversation_messages(message_list, system_prompt)
            
            # Get function definitions
            functions = get_function_definitions(user_roles)
            
            step.output_data = {
                "system_prompt_length": len(system_prompt),
                "messages_before_truncate": original_count,
                "messages_after_truncate": len(message_list),
                "function_count": len(functions),
            }
        
        # Get provider
        provider = get_provider()
        
        if not provider.is_configured():
            logger.warning("LLM provider not configured")
            flow_logger.log_step(
                step_type=LogicStepType.FLOW_ERROR,
                step_name="Provider not configured",
                error_message="LLM provider not configured",
            )
            flow_logger.commit()
            return {
                "conversation_id": conversation.id,
                "message_id": 0,
                "content": "I'm sorry, but the AI assistant is not currently configured. Please contact an administrator.",
                "tokens_used": 0,
                "logic_version_id": flow_logger.logic_version_string,
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
            flow_logger=flow_logger,
        )
        
        # Update flow logger with message ID
        if result.get("message_id"):
            flow_logger.set_message_id(result["message_id"])
        
        # Create reference log entry
        reference_log_id = None
        if create_reference_log is not None and reference_snippets:
            try:
                ref_log = create_reference_log(
                    db_session=db_session,
                    assembled_system_prompt=system_prompt,
                    referenced_snippets=reference_snippets,
                    conversation_id=conversation.id,
                    message_id=result.get("message_id"),
                    turn_index=turn_index,
                    model_id=provider.default_model,
                    strategy_id=None,  # Can be extended for strategy support
                    profile_key=effective_profile_key,
                )
                reference_log_id = ref_log.id
                logger.debug(
                    f"Created reference log: {ref_log.id}",
                    extra={
                        "conversation_id": conversation.id,
                        "message_id": result.get("message_id"),
                        "snippet_count": len(reference_snippets),
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to create reference log: {e}")
        
        # Log flow completion
        flow_logger.log_step(
            step_type=LogicStepType.FLOW_END,
            step_name="Processing complete",
            output_data={
                "tokens_used": result.get("tokens_used", 0),
                "tool_calls_count": len(result.get("tool_calls") or []),
                "pending_confirmations": len(result.get("pending_confirmations") or []),
            },
        )
        
        # Commit flow logs
        flow_logger.commit()
        
        # Add flow metadata to result
        result["reference_log_id"] = reference_log_id
        result["logic_version_id"] = flow_logger.logic_version_string
        result["flow_summary"] = flow_logger.get_flow_summary()
        
        return result
    
    except Exception as e:
        # Log the error
        flow_logger.log_step(
            step_type=LogicStepType.FLOW_ERROR,
            step_name="Processing failed",
            error_message=str(e),
        )
        flow_logger.commit()
        raise
    
    finally:
        if should_close:
            db_session.close()


async def process_user_message_streaming(
    content: str,
    conversation_id: Optional[int] = None,
    user_id: Optional[str] = None,
    user_roles: Optional[List[str]] = None,
    page_context: Optional[Dict[str, Any]] = None,
    mode: Optional[ConversationMode] = None,
    temperature: Optional[float] = None,
    db_session=None,
    reference_profile_key: Optional[str] = None,
    progress_emitter: Optional[ProgressEmitter] = None,
) -> AsyncGenerator[str, None]:
    """Process a user message with streaming progress updates.
    
    Similar to process_user_message but yields SSE events for real-time progress.
    Uses a concurrent approach: processing runs while events are yielded immediately.
    
    Args:
        content: User message content
        conversation_id: Existing conversation ID (creates new if None)
        user_id: ID of the user
        user_roles: User's roles for permission checking
        page_context: Context about current page/view
        mode: Conversation mode
        temperature: Sampling temperature (0.0-2.0)
        db_session: SQLAlchemy session
        reference_profile_key: Optional key of reference profile to use
        progress_emitter: Progress emitter for SSE events
        
    Yields:
        SSE-formatted event strings
    """
    import asyncio
    from database import get_db
    
    # Create emitter if not provided
    if progress_emitter is None:
        progress_emitter = ProgressEmitter(conversation_id=conversation_id)
    
    # Get database session
    if db_session is None:
        db_session = next(get_db())
        should_close = True
    else:
        should_close = False
    
    # Create the processing coroutine
    async def do_processing():
        """Run the actual processing, emitting events along the way."""
        main_task_id = progress_emitter.generate_task_id("request")
        
        # Initialize flow logger for streaming
        flow_logger = FlowLogger(
            db_session=db_session,
            conversation_id=conversation_id,
        )
        
        try:
            # Log flow start
            flow_logger.log_step(
                step_type=LogicStepType.FLOW_START,
                step_name="Processing user message (streaming)",
                input_data={
                    "content_length": len(content),
                    "has_conversation_id": conversation_id is not None,
                    "mode": mode.value if mode else None,
                },
            )
            
            # Start main processing task
            await progress_emitter.emit_start(main_task_id, "Processing your request")
            
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
                progress_emitter.conversation_id = conversation.id
                logger.info(
                    f"Created new conversation: {conversation.id}",
                    extra={"conversation_id": conversation.id, "user_id": user_id}
                )
            
            # Update flow logger with conversation ID
            flow_logger.set_conversation_id(conversation.id)
            
            # Save user message
            user_message = add_message(
                db_session,
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content=content,
            )
            
            # Emit progress update
            await progress_emitter.emit_update(main_task_id, "Preparing context...")
            
            # Get conversation history
            messages = get_conversation_messages(db_session, conversation.id)
            message_list = [msg.to_openai_format() for msg in messages]
            
            # Calculate turn index for this response
            turn_index = len([m for m in messages if m.role == MessageRole.ASSISTANT])
            flow_logger.turn_index = turn_index
            
            # Get reference snippets for context
            get_references_for_context, create_reference_log = _get_reference_service()
            reference_snippets = []
            
            effective_profile_key = reference_profile_key
            if effective_profile_key is None and page_context:
                effective_profile_key = page_context.get("reference_profile_key")
            
            registry = get_action_registry()
            tools_hint = [action.name for action in registry.list_actions()]
            
            if get_references_for_context is not None:
                try:
                    reference_snippets = get_references_for_context(
                        db_session=db_session,
                        profile_key=effective_profile_key,
                        user_roles=user_roles,
                        page_context=page_context or conversation.context,
                        mode=conversation.mode.value if conversation.mode else None,
                        tools_hint=tools_hint,
                    )
                except Exception as e:
                    logger.warning(f"Failed to get reference snippets: {e}")
            
            # Log context build
            flow_logger.log_step(
                step_type=LogicStepType.CONTEXT_BUILD,
                step_name="Build context for streaming",
                output_data={
                    "message_count": len(messages),
                    "reference_count": len(reference_snippets),
                    "turn_index": turn_index,
                },
            )
            
            # Build system prompt
            system_prompt = build_system_prompt(
                user_id=user_id,
                user_roles=user_roles,
                page_context=page_context or conversation.context,
                conversation_mode=conversation.mode.value if conversation.mode else None,
                reference_profile_key=effective_profile_key,
                reference_snippets=reference_snippets,
            )
            
            message_list = truncate_context(message_list)
            full_messages = build_conversation_messages(message_list, system_prompt)
            functions = get_function_definitions(user_roles)
            
            provider = get_provider()
            
            if not provider.is_configured():
                flow_logger.log_step(
                    step_type=LogicStepType.FLOW_ERROR,
                    step_name="Provider not configured",
                    error_message="LLM provider not configured",
                )
                flow_logger.commit()
                await progress_emitter.emit_error(
                    main_task_id,
                    "AI assistant is not configured"
                )
                await progress_emitter.emit_done_signal(
                    "I'm sorry, but the AI assistant is not currently configured."
                )
                return
            
            # Update progress - starting LLM call
            await progress_emitter.emit_update(main_task_id, "Thinking...")
            
            # Process with tools (streaming version)
            result = await _process_with_tools_streaming(
                provider=provider,
                messages=full_messages,
                functions=functions,
                conversation=conversation,
                user_id=user_id,
                user_roles=user_roles,
                temperature=temperature,
                db_session=db_session,
                progress_emitter=progress_emitter,
                parent_task_id=main_task_id,
                flow_logger=flow_logger,
            )
            
            # Update flow logger with message ID
            if result.get("message_id"):
                flow_logger.set_message_id(result["message_id"])
            
            # Create reference log entry
            reference_log_id = None
            if create_reference_log is not None and reference_snippets:
                try:
                    ref_log = create_reference_log(
                        db_session=db_session,
                        assembled_system_prompt=system_prompt,
                        referenced_snippets=reference_snippets,
                        conversation_id=conversation.id,
                        message_id=result.get("message_id"),
                        turn_index=turn_index,
                        model_id=provider.default_model,
                        strategy_id=None,
                        profile_key=effective_profile_key,
                    )
                    reference_log_id = ref_log.id
                except Exception as e:
                    logger.warning(f"Failed to create reference log: {e}")
            
            # Log flow completion
            flow_logger.log_step(
                step_type=LogicStepType.FLOW_END,
                step_name="Streaming processing complete",
                output_data={
                    "tokens_used": result.get("tokens_used", 0),
                    "tool_calls_count": len(result.get("tool_calls") or []),
                },
            )
            flow_logger.commit()
            
            # Complete main task
            await progress_emitter.emit_done(
                main_task_id,
                f"Completed ({result.get('tokens_used', 0)} tokens)",
                metadata={"tokens_used": result.get("tokens_used", 0)}
            )
            
            # Send final done signal with flow info
            await progress_emitter.emit_done_signal(
                final_content=result.get("content", ""),
                metadata={
                    "conversation_id": conversation.id,
                    "message_id": result.get("message_id"),
                    "tokens_used": result.get("tokens_used", 0),
                    "tool_calls": result.get("tool_calls"),
                    "pending_confirmations": result.get("pending_confirmations"),
                    "reference_log_id": reference_log_id,
                    "logic_version_id": flow_logger.logic_version_string,
                }
            )
        
        except Exception as e:
            logger.error(f"Streaming processing failed: {e}", exc_info=True)
            flow_logger.log_step(
                step_type=LogicStepType.FLOW_ERROR,
                step_name="Streaming processing failed",
                error_message=str(e),
            )
            flow_logger.commit()
            await progress_emitter.emit_error(main_task_id, str(e))
            await progress_emitter.emit_done_signal(
                f"Error: {str(e)}",
                metadata={"error": str(e)}
            )
    
    try:
        # Start processing as a background task
        processing_task = asyncio.create_task(do_processing())
        
        # Yield events from the queue as they arrive
        while not progress_emitter._closed or not progress_emitter._queue.empty():
            try:
                # Check if processing task failed
                if processing_task.done():
                    try:
                        # Check for exceptions in the task
                        await processing_task
                    except Exception as e:
                        logger.error(f"Processing task failed: {e}", exc_info=True)
                        # Emit error event
                        error_event = f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                        yield error_event
                        # Drain any remaining events
                        while not progress_emitter._queue.empty():
                            event = await progress_emitter._queue.get()
                            yield event.to_sse()
                        break
                    
                    # Drain any remaining events
                    while not progress_emitter._queue.empty():
                        event = await progress_emitter._queue.get()
                        yield event.to_sse()
                    break
                
                # Wait for event with short timeout
                try:
                    event = await asyncio.wait_for(
                        progress_emitter._queue.get(),
                        timeout=0.1
                    )
                    yield event.to_sse()
                    
                    # Check if this was the done event
                    if event.event_type == EventType.DONE:
                        break
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ": keepalive\n\n"
                    
            except Exception as e:
                logger.error(f"Error yielding event: {e}", exc_info=True)
                # Emit error event
                error_event = f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                yield error_event
                break
        
        # Ensure processing task completes
        if not processing_task.done():
            try:
                await processing_task
            except Exception as e:
                logger.error(f"Processing task exception: {e}", exc_info=True)
        
    except Exception as e:
        logger.error(f"Stream generator error: {e}", exc_info=True)
        # Emit final error event
        error_event = f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        yield error_event
        
    finally:
        if should_close:
            db_session.close()


async def _process_with_tools_streaming(
    provider,
    messages: List[Dict[str, Any]],
    functions: List[Dict[str, Any]],
    conversation: Conversation,
    user_id: Optional[str],
    user_roles: Optional[List[str]],
    temperature: Optional[float],
    db_session,
    progress_emitter: ProgressEmitter,
    parent_task_id: str,
    flow_logger: Optional[FlowLogger] = None,
) -> Dict[str, Any]:
    """Process messages with tool calling and streaming progress.
    
    Similar to _process_with_tools but emits progress events.
    """
    all_tool_results = []
    pending_confirmations = []
    total_tokens = 0
    iteration = 0
    
    current_messages = messages.copy()
    
    while iteration < MAX_ITERATIONS:
        iteration += 1
        
        # Log iteration start
        if flow_logger:
            flow_logger.log_step(
                step_type=LogicStepType.ITERATION_START,
                step_name=f"Streaming iteration {iteration}",
                input_data={"iteration": iteration, "max_iterations": MAX_ITERATIONS},
            )
        
        # Create task for this iteration
        iter_task_id = progress_emitter.generate_task_id(f"iter-{iteration}")
        await progress_emitter.emit_start(
            iter_task_id,
            f"Processing (step {iteration})",
            parent_id=parent_task_id
        )
        
        logger.debug(
            f"Processing iteration {iteration}",
            extra={"conversation_id": conversation.id, "iteration": iteration}
        )
        
        # Call the LLM
        await progress_emitter.emit_update(iter_task_id, "Calling AI model...")
        
        call_params = {
            "messages": current_messages,
            "functions": functions if functions else None,
        }
        if temperature is not None:
            call_params["temperature"] = temperature
        
        # Log LLM call with timing
        if flow_logger:
            with flow_logger.timed_step(
                step_type=LogicStepType.LLM_CALL,
                step_name=f"Streaming LLM call (iteration {iteration})",
                input_data={"model": provider.default_model, "temperature": temperature},
            ) as step:
                response = await provider.chat_completion(**call_params)
                step.output_data = {
                    "has_tool_calls": response.has_tool_calls,
                    "tool_call_count": len(response.tool_calls) if response.tool_calls else 0,
                }
                step.tokens_used = response.total_tokens
        else:
            response = await provider.chat_completion(**call_params)
        
        total_tokens += response.total_tokens
        
        # Check if we have tool calls
        if not response.has_tool_calls:
            # Log decision
            if flow_logger:
                flow_logger.log_step(
                    step_type=LogicStepType.TOOL_DECISION,
                    step_name="No tools - final response",
                    output_data={"decision": "no_tools"},
                )
            
            # No more tool calls, save and return the response
            assistant_message = add_message(
                db_session,
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content=response.content,
                tokens_used=response.total_tokens,
            )
            
            await progress_emitter.emit_done(
                iter_task_id,
                "Generated response",
                metadata={"tokens": response.total_tokens}
            )
            
            return {
                "conversation_id": conversation.id,
                "message_id": assistant_message.id,
                "content": response.content or "",
                "tool_calls": all_tool_results if all_tool_results else None,
                "pending_confirmations": pending_confirmations if pending_confirmations else None,
                "tokens_used": total_tokens,
            }
        
        # Log tool decision
        if flow_logger:
            flow_logger.log_step(
                step_type=LogicStepType.TOOL_DECISION,
                step_name=f"Using {len(response.tool_calls)} tool(s)",
                output_data={"tool_names": [tc.name for tc in response.tool_calls]},
            )
        
        # Process tool calls with progress tracking
        await progress_emitter.emit_update(
            iter_task_id,
            f"Executing {len(response.tool_calls)} tool(s)..."
        )
        
        tool_results = await _execute_tool_calls_streaming(
            tool_calls=response.tool_calls,
            conversation=conversation,
            user_id=user_id,
            user_roles=user_roles,
            db_session=db_session,
            progress_emitter=progress_emitter,
            parent_task_id=iter_task_id,
            flow_logger=flow_logger,
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
        
        # Add to context for next iteration
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
        
        # Complete this iteration
        await progress_emitter.emit_done(
            iter_task_id,
            f"Executed {len(response.tool_calls)} tool(s)",
            metadata={"tool_count": len(response.tool_calls)}
        )
    
    # Max iterations reached
    logger.warning(
        f"Max iterations reached for conversation {conversation.id}",
        extra={"conversation_id": conversation.id, "iterations": MAX_ITERATIONS}
    )
    
    return {
        "conversation_id": conversation.id,
        "message_id": 0,
        "content": "I apologize, but I encountered too many steps. Please simplify your request.",
        "tool_calls": all_tool_results,
        "pending_confirmations": pending_confirmations if pending_confirmations else None,
        "tokens_used": total_tokens,
    }


async def _execute_tool_calls_streaming(
    tool_calls: List[ToolCall],
    conversation: Conversation,
    user_id: Optional[str],
    user_roles: Optional[List[str]],
    db_session,
    progress_emitter: ProgressEmitter,
    parent_task_id: str,
    flow_logger: Optional[FlowLogger] = None,
) -> List[Dict[str, Any]]:
    """Execute tool calls with streaming progress updates.
    
    Similar to _execute_tool_calls but emits progress events for each tool.
    """
    registry = get_action_registry()
    results = []
    
    for tc in tool_calls:
        # Create task for this tool call
        tool_task_id = f"tool-{tc.id}"
        await progress_emitter.emit_start(
            tool_task_id,
            f"Running: {tc.name}",
            parent_id=parent_task_id,
            metadata={"tool_name": tc.name, "arguments": tc.arguments}
        )
        
        logger.info(
            f"Executing tool call: {tc.name}",
            extra={
                "conversation_id": conversation.id,
                "tool_call_id": tc.id,
                "tool_name": tc.name,
            }
        )
        
        try:
            # Execute the action with flow logging
            if flow_logger:
                with flow_logger.timed_step(
                    step_type=LogicStepType.TOOL_EXECUTE,
                    step_name=f"Streaming execute: {tc.name}",
                    input_data={"tool_name": tc.name, "arguments": tc.arguments},
                ) as step:
                    action_result = await registry.execute(
                        name=tc.name,
                        parameters=tc.arguments,
                        user_id=user_id,
                        user_roles=user_roles,
                    )
                    step.output_data = {
                        "success": action_result.success,
                        "requires_confirmation": action_result.requires_confirmation,
                    }
            else:
                action_result = await registry.execute(
                    name=tc.name,
                    parameters=tc.arguments,
                    user_id=user_id,
                    user_roles=user_roles,
                )
            
            # Log tool result to flow log
            if flow_logger:
                flow_logger.log_step(
                    step_type=LogicStepType.TOOL_RESULT,
                    step_name=f"Streaming result: {tc.name}",
                    output_data={"success": action_result.success},
                    error_message=action_result.error if not action_result.success else None,
                )
            
            # Log the action to action_logs table
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
                await progress_emitter.emit_done(
                    tool_task_id,
                    action_result.message or "Success",
                    metadata={"success": True}
                )
            elif action_result.requires_confirmation:
                await progress_emitter.emit_done(
                    tool_task_id,
                    "Awaiting confirmation",
                    metadata={"requires_confirmation": True}
                )
            else:
                update_action_log(
                    db_session,
                    log_id=action_log.id,
                    status=ActionStatus.FAILED,
                    error_message=action_result.error,
                )
                await progress_emitter.emit_error(
                    tool_task_id,
                    action_result.error or "Failed"
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
            
        except Exception as e:
            logger.error(f"Tool execution failed: {tc.name}", exc_info=True)
            await progress_emitter.emit_error(tool_task_id, str(e))
            results.append({
                "tool_call_id": tc.id,
                "action_name": tc.name,
                "success": False,
                "message": str(e),
                "result": {"error": str(e)},
                "requires_confirmation": False,
                "confirmation_id": None,
            })
    
    return results


async def _process_with_tools(
    provider,
    messages: List[Dict[str, Any]],
    functions: List[Dict[str, Any]],
    conversation: Conversation,
    user_id: Optional[str],
    user_roles: Optional[List[str]],
    temperature: Optional[float],
    db_session,
    flow_logger: Optional[FlowLogger] = None,
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
        
        # Log iteration start
        if flow_logger:
            flow_logger.log_step(
                step_type=LogicStepType.ITERATION_START,
                step_name=f"Agentic loop iteration {iteration}",
                input_data={
                    "iteration": iteration,
                    "max_iterations": MAX_ITERATIONS,
                    "message_count": len(current_messages),
                },
            )
        
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
        
        # Log LLM call
        if flow_logger:
            with flow_logger.timed_step(
                step_type=LogicStepType.LLM_CALL,
                step_name=f"LLM call (iteration {iteration})",
                input_data={
                    "model": provider.default_model,
                    "temperature": temperature,
                    "function_count": len(functions) if functions else 0,
                },
            ) as step:
                response = await provider.chat_completion(**call_params)
                step.output_data = {
                    "has_tool_calls": response.has_tool_calls,
                    "tool_call_count": len(response.tool_calls) if response.tool_calls else 0,
                    "content_length": len(response.content) if response.content else 0,
                }
                step.tokens_used = response.total_tokens
        else:
            response = await provider.chat_completion(**call_params)
        
        total_tokens += response.total_tokens
        
        # Check if we have tool calls
        if not response.has_tool_calls:
            # Log decision not to use tools
            if flow_logger:
                flow_logger.log_step(
                    step_type=LogicStepType.TOOL_DECISION,
                    step_name="No tool calls - generating final response",
                    output_data={"decision": "no_tools", "iteration": iteration},
                )
            
            # No more tool calls, save and return the response
            assistant_message = add_message(
                db_session,
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content=response.content,
                tokens_used=response.total_tokens,
            )
            
            # Log message save
            if flow_logger:
                flow_logger.log_step(
                    step_type=LogicStepType.MESSAGE_SAVE,
                    step_name="Save assistant response",
                    output_data={
                        "message_id": assistant_message.id,
                        "content_length": len(response.content) if response.content else 0,
                    },
                )
            
            return {
                "conversation_id": conversation.id,
                "message_id": assistant_message.id,
                "content": response.content or "",
                "tool_calls": all_tool_results if all_tool_results else None,
                "pending_confirmations": pending_confirmations if pending_confirmations else None,
                "tokens_used": total_tokens,
            }
        
        # Log tool decision
        if flow_logger:
            flow_logger.log_step(
                step_type=LogicStepType.TOOL_DECISION,
                step_name=f"Decided to call {len(response.tool_calls)} tool(s)",
                output_data={
                    "decision": "use_tools",
                    "tool_names": [tc.name for tc in response.tool_calls],
                    "iteration": iteration,
                },
            )
        
        # Process tool calls
        tool_results = await _execute_tool_calls(
            tool_calls=response.tool_calls,
            conversation=conversation,
            user_id=user_id,
            user_roles=user_roles,
            db_session=db_session,
            flow_logger=flow_logger,
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
        
        # Log iteration end
        if flow_logger:
            flow_logger.log_step(
                step_type=LogicStepType.ITERATION_END,
                step_name=f"Completed iteration {iteration}",
                output_data={
                    "iteration": iteration,
                    "tools_executed": len(tool_results),
                    "pending_confirmations": len(pending_confirmations),
                },
            )
    
    # Max iterations reached
    logger.warning(
        f"Max iterations reached for conversation {conversation.id}",
        extra={"conversation_id": conversation.id, "iterations": MAX_ITERATIONS}
    )
    
    if flow_logger:
        flow_logger.log_step(
            step_type=LogicStepType.FLOW_ERROR,
            step_name="Max iterations reached",
            error_message=f"Reached maximum of {MAX_ITERATIONS} iterations",
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
    flow_logger: Optional[FlowLogger] = None,
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
        
        # Log tool execution
        if flow_logger:
            with flow_logger.timed_step(
                step_type=LogicStepType.TOOL_EXECUTE,
                step_name=f"Execute tool: {tc.name}",
                input_data={
                    "tool_name": tc.name,
                    "tool_call_id": tc.id,
                    "arguments": tc.arguments,
                },
            ) as step:
                # Execute the action
                action_result = await registry.execute(
                    name=tc.name,
                    parameters=tc.arguments,
                    user_id=user_id,
                    user_roles=user_roles,
                )
                step.output_data = {
                    "success": action_result.success,
                    "requires_confirmation": action_result.requires_confirmation,
                    "message": action_result.message,
                }
        else:
            action_result = await registry.execute(
                name=tc.name,
                parameters=tc.arguments,
                user_id=user_id,
                user_roles=user_roles,
            )
        
        # Log tool result
        if flow_logger:
            flow_logger.log_step(
                step_type=LogicStepType.TOOL_RESULT,
                step_name=f"Tool result: {tc.name}",
                output_data={
                    "success": action_result.success,
                    "data_keys": list(action_result.data.keys()) if action_result.data else [],
                },
                error_message=action_result.error if not action_result.success else None,
            )
        
        # Log the action to action_logs table
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

