"""FastAPI router for AI assistant endpoints.

Provides:
- Chat endpoint for sending messages
- Streaming chat endpoint with real-time progress (SSE)
- Conversation management endpoints
- Action confirmation endpoints
- Status endpoint
"""

import sys
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_db
from logging_config import get_logger

from .schemas import (
    ChatRequest,
    ChatResponse,
    ConfirmActionRequest,
    ConfirmActionResponse,
    ConversationListItem,
    ConversationDetail,
    MessageSchema,
    ActionLogSchema,
    CreateConversationRequest,
    UpdateConversationRequest,
    AssistantStatus,
    ConversationMode,
    StreamChatRequest,
)
from .services import (
    process_user_message,
    process_user_message_streaming,
    confirm_pending_action,
    cancel_pending_action,
    get_assistant_status,
)
from .progress import ProgressEmitter
from .models import (
    Conversation,
    Message,
    ActionLog,
    ConversationMode as DBConversationMode,
    create_conversation,
    get_conversation_messages,
)
from .actions import register_dynamic_actions
from .models_registry import (
    get_all_models,
    get_model,
    get_active_model,
    set_active_model,
    get_active_model_id,
    ModelCapability,
)
from .unified_registry import (
    get_registry,
    UnifiedModelRegistry,
    ModelSource,
    StrategyType,
    execute_with_strategy,
)

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/api/assistant", tags=["assistant"])


# Initialize dynamic actions on module load
try:
    register_dynamic_actions()
except Exception as e:
    logger.warning(f"Failed to register dynamic actions: {e}")


# -------------------------------------------------------------------------
# Chat Endpoints
# -------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    """Process a user message and return AI response.
    
    Args:
        request: Chat request with message and optional context
        db: Database session
        
    Returns:
        ChatResponse with assistant's response
    """
    try:
        # Convert mode to DB enum if provided
        mode = None
        if request.mode:
            mode = DBConversationMode(request.mode.value)
        
        result = await process_user_message(
            content=request.message,
            conversation_id=request.conversation_id,
            user_id=None,  # TODO: Get from authentication
            user_roles=None,  # TODO: Get from authentication
            page_context=request.page_context,
            mode=mode,
            temperature=request.temperature,
            db_session=db,
        )
        
        return ChatResponse(
            conversation_id=result["conversation_id"],
            message_id=result["message_id"],
            content=result["content"],
            tool_calls=result.get("tool_calls"),
            pending_confirmations=result.get("pending_confirmations"),
            tokens_used=result.get("tokens_used"),
        )
    
    except Exception as e:
        logger.error(f"Chat processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process message: {str(e)}"
        )


@router.post("/chat/stream")
async def send_message_stream(
    request: StreamChatRequest,
    db: Session = Depends(get_db),
):
    """Process a user message with streaming progress updates via SSE.
    
    Returns Server-Sent Events with real-time task progress.
    
    Event types:
    - task.start: New task begins (UI auto-expands)
    - task.update: Progress update (e.g., "thinking...")
    - task.done: Task completed (UI auto-collapses to summary)
    - task.error: Task failed
    - message.chunk: Streaming text content
    - done: Full response complete
    
    Args:
        request: Stream chat request with message and optional context
        db: Database session
        
    Returns:
        StreamingResponse with text/event-stream content type
    """
    try:
        # Convert mode to DB enum if provided
        mode = None
        if request.mode:
            mode = DBConversationMode(request.mode.value)
        
        # Create progress emitter
        emitter = ProgressEmitter()
        
        async def generate():
            """Generate SSE events from the progress emitter."""
            try:
                async for event in process_user_message_streaming(
                    content=request.message,
                    conversation_id=request.conversation_id,
                    user_id=None,  # TODO: Get from authentication
                    user_roles=None,  # TODO: Get from authentication
                    page_context=request.page_context,
                    mode=mode,
                    temperature=request.temperature,
                    db_session=db,
                    progress_emitter=emitter,
                ):
                    yield event
            except Exception as e:
                logger.error(f"Streaming error: {e}", exc_info=True)
                # Emit error event
                import json
                error_event = f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                yield error_event
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            }
        )
    
    except Exception as e:
        logger.error(f"Stream setup failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to setup stream: {str(e)}"
        )


# -------------------------------------------------------------------------
# Action Confirmation Endpoints
# -------------------------------------------------------------------------

@router.post("/actions/confirm", response_model=ConfirmActionResponse)
async def confirm_action(
    request: ConfirmActionRequest,
    db: Session = Depends(get_db),
):
    """Confirm and execute a pending action.
    
    Args:
        request: Confirmation request with confirmation_id
        db: Database session
        
    Returns:
        ConfirmActionResponse with result
    """
    try:
        result = await confirm_pending_action(
            confirmation_id=request.confirmation_id,
            user_id=None,  # TODO: Get from authentication
            db_session=db,
        )
        
        return ConfirmActionResponse(
            success=result.success,
            message=result.message,
            data=result.data,
            error=result.error,
        )
    
    except Exception as e:
        logger.error(f"Action confirmation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to confirm action: {str(e)}"
        )


@router.post("/actions/{confirmation_id}/cancel")
async def cancel_action(
    confirmation_id: str,
    db: Session = Depends(get_db),
):
    """Cancel a pending action.
    
    Args:
        confirmation_id: ID of the confirmation to cancel
        db: Database session
        
    Returns:
        Success indicator
    """
    try:
        cancelled = await cancel_pending_action(
            confirmation_id=confirmation_id,
            user_id=None,  # TODO: Get from authentication
            db_session=db,
        )
        
        if not cancelled:
            raise HTTPException(
                status_code=404,
                detail="Confirmation not found or already processed"
            )
        
        return {"success": True, "message": "Action cancelled"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Action cancellation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel action: {str(e)}"
        )


# -------------------------------------------------------------------------
# Conversation Management Endpoints
# -------------------------------------------------------------------------

@router.get("/conversations", response_model=List[ConversationListItem])
async def list_conversations(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List conversations for the current user.
    
    Args:
        limit: Maximum number of conversations to return
        offset: Number of conversations to skip
        db: Database session
        
    Returns:
        List of conversation summaries
    """
    try:
        # TODO: Filter by user_id from authentication
        conversations = db.query(Conversation).filter(
            Conversation.is_active == True
        ).order_by(
            Conversation.updated_at.desc()
        ).offset(offset).limit(limit).all()
        
        return [
            ConversationListItem(
                id=conv.id,
                title=conv.title,
                mode=conv.mode.value if conv.mode else "default",
                message_count=len(conv.messages) if conv.messages else 0,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
            )
            for conv in conversations
        ]
    
    except Exception as e:
        logger.error(f"Failed to list conversations: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list conversations: {str(e)}"
        )


@router.post("/conversations", response_model=ConversationDetail)
async def create_new_conversation(
    request: CreateConversationRequest,
    db: Session = Depends(get_db),
):
    """Create a new conversation.
    
    Args:
        request: Creation request
        db: Database session
        
    Returns:
        Created conversation
    """
    try:
        mode = DBConversationMode(request.mode.value) if request.mode else DBConversationMode.DEFAULT
        
        conversation = create_conversation(
            db,
            user_id=None,  # TODO: Get from authentication
            title=request.title,
            mode=mode,
            context=request.context,
        )
        
        return ConversationDetail(
            id=conversation.id,
            user_id=conversation.user_id,
            title=conversation.title,
            mode=conversation.mode.value if conversation.mode else "default",
            context=conversation.context or {},
            is_active=conversation.is_active,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            messages=[],
        )
    
    except Exception as e:
        logger.error(f"Failed to create conversation: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create conversation: {str(e)}"
        )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    """Get a conversation with its messages.
    
    Args:
        conversation_id: ID of the conversation
        db: Database session
        
    Returns:
        Conversation with messages
    """
    try:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found"
            )
        
        messages = get_conversation_messages(db, conversation_id)
        
        return ConversationDetail(
            id=conversation.id,
            user_id=conversation.user_id,
            title=conversation.title,
            mode=conversation.mode.value if conversation.mode else "default",
            context=conversation.context or {},
            is_active=conversation.is_active,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            messages=[msg.to_dict() for msg in messages],
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get conversation: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get conversation: {str(e)}"
        )


@router.patch("/conversations/{conversation_id}", response_model=ConversationDetail)
async def update_conversation(
    conversation_id: int,
    request: UpdateConversationRequest,
    db: Session = Depends(get_db),
):
    """Update a conversation.
    
    Args:
        conversation_id: ID of the conversation
        request: Update request
        db: Database session
        
    Returns:
        Updated conversation
    """
    try:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found"
            )
        
        if request.title is not None:
            conversation.title = request.title
        
        if request.mode is not None:
            conversation.mode = DBConversationMode(request.mode.value)
        
        if request.context is not None:
            conversation.context = request.context
        
        if request.is_active is not None:
            conversation.is_active = request.is_active
        
        db.commit()
        db.refresh(conversation)
        
        messages = get_conversation_messages(db, conversation_id)
        
        return ConversationDetail(
            id=conversation.id,
            user_id=conversation.user_id,
            title=conversation.title,
            mode=conversation.mode.value if conversation.mode else "default",
            context=conversation.context or {},
            is_active=conversation.is_active,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            messages=[msg.to_dict() for msg in messages],
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update conversation: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update conversation: {str(e)}"
        )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    """Delete a conversation.
    
    Args:
        conversation_id: ID of the conversation
        db: Database session
        
    Returns:
        Success indicator
    """
    try:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found"
            )
        
        db.delete(conversation)
        db.commit()
        
        return {"success": True, "message": "Conversation deleted"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete conversation: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete conversation: {str(e)}"
        )


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageSchema])
async def get_messages(
    conversation_id: int,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Get messages for a conversation.
    
    Args:
        conversation_id: ID of the conversation
        limit: Maximum number of messages
        db: Database session
        
    Returns:
        List of messages
    """
    try:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found"
            )
        
        messages = get_conversation_messages(db, conversation_id, limit=limit)
        
        return [
            MessageSchema(
                id=msg.id,
                conversation_id=msg.conversation_id,
                role=msg.role.value if msg.role else "user",
                content=msg.content,
                tool_calls=msg.tool_calls,
                tool_call_id=msg.tool_call_id,
                name=msg.name,
                created_at=msg.created_at,
            )
            for msg in messages
        ]
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get messages: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get messages: {str(e)}"
        )


# -------------------------------------------------------------------------
# Action Log Endpoints
# -------------------------------------------------------------------------

@router.get("/action-logs", response_model=List[ActionLogSchema])
async def list_action_logs(
    conversation_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List action logs.
    
    Args:
        conversation_id: Optional filter by conversation
        limit: Maximum number of logs
        offset: Number of logs to skip
        db: Database session
        
    Returns:
        List of action logs
    """
    try:
        query = db.query(ActionLog)
        
        if conversation_id:
            query = query.filter(ActionLog.conversation_id == conversation_id)
        
        logs = query.order_by(
            ActionLog.created_at.desc()
        ).offset(offset).limit(limit).all()
        
        return [
            ActionLogSchema(
                id=log.id,
                conversation_id=log.conversation_id,
                action_name=log.action_name,
                action_type=log.action_type,
                parameters=log.parameters or {},
                result=log.result,
                status=log.status.value if log.status else "pending",
                confirmation_id=log.confirmation_id,
                user_id=log.user_id,
                created_at=log.created_at,
                executed_at=log.executed_at,
                error_message=log.error_message,
            )
            for log in logs
        ]
    
    except Exception as e:
        logger.error(f"Failed to list action logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list action logs: {str(e)}"
        )


# -------------------------------------------------------------------------
# Model Management Endpoints
# -------------------------------------------------------------------------

@router.get("/models")
async def list_models(
    tier: Optional[str] = None,
    capability: Optional[str] = None,
):
    """List available AI models.
    
    Args:
        tier: Optional filter by tier (budget, standard, premium, flagship)
        capability: Optional filter by capability (chat, function_calling, vision, reasoning, code)
        
    Returns:
        List of model configurations
    """
    try:
        models = get_all_models()
        
        # Filter by tier if specified
        if tier:
            models = [m for m in models if m.tier == tier]
        
        # Filter by capability if specified
        if capability:
            try:
                cap = ModelCapability(capability)
                models = [m for m in models if cap in m.capabilities]
            except ValueError:
                pass  # Invalid capability, ignore filter
        
        # Sort by tier priority
        tier_order = {"flagship": 0, "premium": 1, "standard": 2, "budget": 3}
        models.sort(key=lambda m: (tier_order.get(m.tier, 99), m.name))
        
        return {
            "models": [m.to_dict() for m in models],
            "active_model_id": get_active_model_id(),
        }
    
    except Exception as e:
        logger.error(f"Failed to list models: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list models: {str(e)}"
        )


@router.get("/models/active")
async def get_active_model_endpoint():
    """Get the currently active model.
    
    Returns:
        Active model configuration
    """
    try:
        model = get_active_model()
        if model is None:
            raise HTTPException(
                status_code=404,
                detail="No models available"
            )
        
        return {
            "model": model.to_dict(),
            "model_id": get_active_model_id(),
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get active model: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get active model: {str(e)}"
        )


@router.post("/models/active")
async def set_active_model_endpoint(
    model_id: str = Query(..., description="Model ID to activate"),
):
    """Set the active model.
    
    Args:
        model_id: ID of the model to activate
        
    Returns:
        Updated active model configuration
    """
    try:
        model = set_active_model(model_id)
        
        logger.info(
            f"Active model changed to {model_id}",
            extra={"model_id": model_id, "model_name": model.name}
        )
        
        return {
            "success": True,
            "model": model.to_dict(),
            "message": f"Model changed to {model.name}",
        }
    
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to set active model: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to set active model: {str(e)}"
        )


@router.get("/models/{model_id}")
async def get_model_details(model_id: str):
    """Get details for a specific model.
    
    Args:
        model_id: Model identifier
        
    Returns:
        Model configuration
    """
    try:
        model = get_model(model_id)
        if model is None:
            raise HTTPException(
                status_code=404,
                detail=f"Model not found: {model_id}"
            )
        
        return {"model": model.to_dict()}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get model: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get model: {str(e)}"
        )


# -------------------------------------------------------------------------
# Status Endpoint
# -------------------------------------------------------------------------

@router.get("/status", response_model=AssistantStatus)
async def get_status():
    """Get the status of the assistant service.
    
    Returns:
        AssistantStatus with provider info and action count
    """
    try:
        status = get_assistant_status()
        return AssistantStatus(**status)
    
    except Exception as e:
        logger.error(f"Failed to get status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get status: {str(e)}"
        )


# -------------------------------------------------------------------------
# Unified Strategy Endpoints (New Orchestration System)
# -------------------------------------------------------------------------

@router.get("/strategies")
async def list_strategies(
    include_single: bool = Query(True, description="Include single-model strategies"),
    include_cascade: bool = Query(True, description="Include cascade strategies"),
):
    """List available orchestration strategies.
    
    Returns strategies grouped for UI display, including:
    - Single model strategies (wrappers around individual models)
    - Cascade strategies (ordered lists of models)
    
    Args:
        include_single: Include single-model strategies
        include_cascade: Include cascade/orchestration strategies
        
    Returns:
        List of strategies with grouping information
    """
    try:
        registry = get_registry()
        
        # Get combined options for UI
        options = registry.get_combined_options_for_ui()
        
        # Filter based on params
        filtered = []
        for opt in options:
            if opt.get("strategy_type") == "single" and include_single:
                filtered.append(opt)
            elif opt.get("strategy_type") == "cascade" and include_cascade:
                filtered.append(opt)
            elif opt.get("strategy_type") not in ["single", "cascade"]:
                filtered.append(opt)
        
        return {
            "strategies": filtered,
            "active_strategy_id": registry.get_active_strategy_id(),
            "groups": [
                "🔀 Auto / Orchestration",
                "🚀 GPT-5 Series (Latest)",
                "🧠 O-Series (Reasoning)",
                "⭐ GPT-4 Series",
                "🖥️ Local Models",
            ],
        }
    
    except Exception as e:
        logger.error(f"Failed to list strategies: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list strategies: {str(e)}"
        )


@router.get("/strategies/active")
async def get_active_strategy():
    """Get the currently active strategy.
    
    Returns:
        Active strategy details
    """
    try:
        registry = get_registry()
        strategy = registry.get_active_strategy()
        
        if strategy is None:
            raise HTTPException(
                status_code=404,
                detail="No active strategy set"
            )
        
        # Get model details if single strategy
        model_details = None
        if strategy.strategy_type == StrategyType.SINGLE and strategy.models:
            model = registry.get_model(strategy.models[0])
            if model:
                model_details = model.to_dict()
        
        return {
            "strategy": strategy.to_dict(),
            "strategy_id": registry.get_active_strategy_id(),
            "model": model_details,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get active strategy: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get active strategy: {str(e)}"
        )


@router.post("/strategies/active")
async def set_active_strategy_endpoint(
    strategy_id: str = Query(..., description="Strategy ID to activate"),
):
    """Set the active strategy.
    
    Args:
        strategy_id: ID of the strategy to activate (e.g., "single:gpt-5-nano", "cascade:cloud-cheapest-first")
        
    Returns:
        Updated active strategy
    """
    try:
        registry = get_registry()
        strategy = registry.set_active_strategy(strategy_id)
        
        logger.info(
            f"Active strategy changed to {strategy_id}",
            extra={"strategy_id": strategy_id, "strategy_name": strategy.display_name}
        )
        
        # Get model details if single strategy
        model_details = None
        if strategy.strategy_type == StrategyType.SINGLE and strategy.models:
            model = registry.get_model(strategy.models[0])
            if model:
                model_details = model.to_dict()
        
        return {
            "success": True,
            "strategy": strategy.to_dict(),
            "model": model_details,
            "message": f"Strategy changed to {strategy.display_name}",
        }
    
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to set active strategy: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to set active strategy: {str(e)}"
        )


@router.get("/strategies/{strategy_id}")
async def get_strategy_details(strategy_id: str):
    """Get details for a specific strategy.
    
    Args:
        strategy_id: Strategy identifier
        
    Returns:
        Strategy details including model information
    """
    try:
        registry = get_registry()
        strategy = registry.get_strategy(strategy_id)
        
        if strategy is None:
            raise HTTPException(
                status_code=404,
                detail=f"Strategy not found: {strategy_id}"
            )
        
        # Get details for all models in the strategy
        model_details = []
        for model_id in strategy.models:
            model = registry.get_model(model_id)
            if model:
                model_details.append(model.to_dict())
        
        return {
            "strategy": strategy.to_dict(),
            "models": model_details,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get strategy: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get strategy: {str(e)}"
        )


@router.post("/strategies/discover-local")
async def discover_local_models(
    ollama_host: str = Query("http://localhost:11434", description="Ollama host URL"),
):
    """Discover and register local models from Ollama.
    
    Args:
        ollama_host: URL of the Ollama server
        
    Returns:
        List of discovered models
    """
    try:
        registry = get_registry()
        registry.set_ollama_host(ollama_host)
        
        discovered = await registry.discover_local_models()
        
        # Update local-first cascade with discovered models
        local_model_ids = [m.id for m in discovered]
        local_first_strategy = registry.get_strategy("cascade:local-first")
        if local_first_strategy and local_model_ids:
            # Add local models first, then cloud fallbacks
            local_first_strategy.models = local_model_ids + ["gpt-5-nano", "gpt-5-mini"]
            logger.info(f"Updated local-first cascade with {len(local_model_ids)} local models")
        
        return {
            "success": True,
            "discovered_count": len(discovered),
            "models": [m.to_dict() for m in discovered],
            "message": f"Discovered {len(discovered)} local models from Ollama",
        }
    
    except Exception as e:
        logger.error(f"Failed to discover local models: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to discover local models: {str(e)}"
        )

