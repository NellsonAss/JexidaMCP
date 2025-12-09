"""Flow logging utilities for AI logic tracking.

Provides:
- FlowLogger: Context-aware logger for step-by-step flow logging
- Version management: Get/create/ensure logic versions
"""

import hashlib
import sys
import os
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from logging_config import get_logger

from .models import AILogicVersion, AILogicFlowLog, LogicStepType

logger = get_logger(__name__)

# Current logic version - updated when logic changes
CURRENT_LOGIC_VERSION_ID = "v1.0.0"
CURRENT_LOGIC_VERSION_NAME = "Initial AI Logic"
CURRENT_LOGIC_VERSION_DESCRIPTION = """
Initial versioned AI logic with:
- Agentic loop processing (max 10 iterations)
- Tool calling support with confirmation flow
- Reference snippet context injection
- Streaming progress updates
"""

# Configuration for the current logic version
CURRENT_LOGIC_CONFIG = {
    "max_iterations": 10,
    "temperature": None,  # Uses model default
    "system_prompt_version": "v1.0",
    "features": [
        "agentic_loop",
        "tool_calling",
        "reference_snippets",
        "streaming_progress",
    ],
    "changes_from_previous": "Initial version",
}


def compute_prompt_hash(prompt_text: str) -> str:
    """Compute SHA-256 hash of system prompt for drift detection."""
    return hashlib.sha256(prompt_text.encode()).hexdigest()[:16]


def get_current_logic_version(db_session) -> Optional[AILogicVersion]:
    """Get the currently active logic version.
    
    Args:
        db_session: SQLAlchemy session
        
    Returns:
        Active AILogicVersion or None
    """
    return db_session.query(AILogicVersion).filter(
        AILogicVersion.is_active == True
    ).first()


def ensure_logic_version_exists(
    db_session,
    version_id: str = CURRENT_LOGIC_VERSION_ID,
    name: str = CURRENT_LOGIC_VERSION_NAME,
    description: str = CURRENT_LOGIC_VERSION_DESCRIPTION,
    configuration: Optional[Dict[str, Any]] = None,
    max_iterations: int = 10,
    system_prompt: Optional[str] = None,
) -> AILogicVersion:
    """Ensure the specified logic version exists, creating if needed.
    
    Also sets this version as active and deactivates others.
    
    Args:
        db_session: SQLAlchemy session
        version_id: Version identifier (e.g., "v1.0.0")
        name: Human-readable name
        description: Description of this version
        configuration: Configuration parameters
        max_iterations: Max agentic loop iterations
        system_prompt: System prompt to hash for drift detection
        
    Returns:
        AILogicVersion instance
    """
    # Check if version exists
    version = db_session.query(AILogicVersion).filter(
        AILogicVersion.version_id == version_id
    ).first()
    
    if version is None:
        # Create new version
        prompt_hash = compute_prompt_hash(system_prompt) if system_prompt else None
        
        version = AILogicVersion(
            version_id=version_id,
            name=name,
            description=description.strip() if description else None,
            configuration=configuration or CURRENT_LOGIC_CONFIG,
            system_prompt_hash=prompt_hash,
            max_iterations=max_iterations,
            is_active=True,
            is_baseline=False,
        )
        
        # Deactivate other versions
        db_session.query(AILogicVersion).filter(
            AILogicVersion.is_active == True
        ).update({"is_active": False})
        
        db_session.add(version)
        db_session.commit()
        db_session.refresh(version)
        
        logger.info(
            f"Created AI logic version: {version_id}",
            extra={"version_id": version_id, "version_db_id": version.id}
        )
    elif not version.is_active:
        # Activate this version
        db_session.query(AILogicVersion).filter(
            AILogicVersion.is_active == True
        ).update({"is_active": False})
        
        version.is_active = True
        db_session.commit()
        db_session.refresh(version)
        
        logger.info(
            f"Activated AI logic version: {version_id}",
            extra={"version_id": version_id}
        )
    
    return version


class FlowLogger:
    """Context-aware logger for AI processing flow steps.
    
    Provides easy-to-use methods for logging each step of AI processing,
    automatically tracking timing and maintaining step order.
    
    Usage:
        flow_logger = FlowLogger(db_session, conversation_id=123, turn_index=0)
        
        # Log a simple step
        flow_logger.log_step(
            step_type=LogicStepType.FLOW_START,
            step_name="Processing user message",
            input_data={"content": "Hello"}
        )
        
        # Log with timing
        with flow_logger.timed_step(
            step_type=LogicStepType.LLM_CALL,
            step_name="Calling GPT-4"
        ) as step:
            response = call_llm()
            step.output_data = {"tokens": 150}
    """
    
    def __init__(
        self,
        db_session,
        conversation_id: Optional[int] = None,
        message_id: Optional[int] = None,
        turn_index: Optional[int] = None,
        logic_version: Optional[AILogicVersion] = None,
    ):
        """Initialize the flow logger.
        
        Args:
            db_session: SQLAlchemy session
            conversation_id: Conversation ID
            message_id: Message ID (can be set later)
            turn_index: Turn index within conversation
            logic_version: Logic version to use (fetched if not provided)
        """
        self.db_session = db_session
        self.conversation_id = conversation_id
        self.message_id = message_id
        self.turn_index = turn_index
        self._step_order = 0
        self._logs: List[AILogicFlowLog] = []
        
        # Get or create logic version
        if logic_version is not None:
            self._logic_version = logic_version
        else:
            self._logic_version = get_current_logic_version(db_session)
            if self._logic_version is None:
                self._logic_version = ensure_logic_version_exists(db_session)
    
    @property
    def logic_version_id(self) -> Optional[int]:
        """Get the logic version database ID."""
        return self._logic_version.id if self._logic_version else None
    
    @property
    def logic_version_string(self) -> str:
        """Get the logic version identifier string."""
        return self._logic_version.version_id if self._logic_version else "unknown"
    
    def set_message_id(self, message_id: int) -> None:
        """Set the message ID after it's created."""
        self.message_id = message_id
    
    def set_conversation_id(self, conversation_id: int) -> None:
        """Set the conversation ID after it's created."""
        self.conversation_id = conversation_id
    
    def log_step(
        self,
        step_type: LogicStepType,
        step_name: str,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None,
        tokens_used: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> AILogicFlowLog:
        """Log a single step in the flow.
        
        Args:
            step_type: Type of step
            step_name: Human-readable description
            input_data: Input to this step
            output_data: Output from this step
            duration_ms: Time taken in milliseconds
            tokens_used: Tokens used (for LLM calls)
            metadata: Additional metadata
            error_message: Error message if step failed
            
        Returns:
            Created AILogicFlowLog
        """
        # Truncate large data to prevent bloating
        truncated_input = self._truncate_data(input_data)
        truncated_output = self._truncate_data(output_data)
        
        log = AILogicFlowLog(
            logic_version_id=self.logic_version_id,
            conversation_id=self.conversation_id,
            message_id=self.message_id,
            turn_index=self.turn_index,
            step_type=step_type,
            step_name=step_name,
            step_order=self._step_order,
            input_data=truncated_input,
            output_data=truncated_output,
            duration_ms=duration_ms,
            tokens_used=tokens_used,
            metadata=metadata,
            error_message=error_message,
        )
        
        self.db_session.add(log)
        self._logs.append(log)
        self._step_order += 1
        
        # Log to standard logger as well
        log_extra = {
            "conversation_id": self.conversation_id,
            "logic_version": self.logic_version_string,
            "step_type": step_type.value,
            "step_order": self._step_order - 1,
        }
        
        if error_message:
            logger.warning(
                f"Flow step failed: {step_name} - {error_message}",
                extra=log_extra
            )
        else:
            logger.debug(
                f"Flow step: {step_name}",
                extra=log_extra
            )
        
        return log
    
    @contextmanager
    def timed_step(
        self,
        step_type: LogicStepType,
        step_name: str,
        input_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Generator["TimedStepContext", None, None]:
        """Context manager for timing a step.
        
        Usage:
            with flow_logger.timed_step(LogicStepType.LLM_CALL, "Calling LLM") as step:
                result = await call_llm()
                step.output_data = {"response": result}
                step.tokens_used = result.tokens
        
        Args:
            step_type: Type of step
            step_name: Human-readable description
            input_data: Input to this step
            metadata: Additional metadata
            
        Yields:
            TimedStepContext for setting output data
        """
        context = TimedStepContext(input_data, metadata)
        start_time = time.perf_counter()
        
        try:
            yield context
            
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            self.log_step(
                step_type=step_type,
                step_name=step_name,
                input_data=context.input_data,
                output_data=context.output_data,
                duration_ms=duration_ms,
                tokens_used=context.tokens_used,
                metadata=context.metadata,
                error_message=None,
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            self.log_step(
                step_type=step_type,
                step_name=step_name,
                input_data=context.input_data,
                output_data=context.output_data,
                duration_ms=duration_ms,
                tokens_used=context.tokens_used,
                metadata=context.metadata,
                error_message=str(e),
            )
            raise
    
    def commit(self) -> None:
        """Commit all logged steps to the database."""
        try:
            self.db_session.commit()
            
            # Refresh logs to get IDs
            for log in self._logs:
                self.db_session.refresh(log)
                
        except Exception as e:
            logger.error(f"Failed to commit flow logs: {e}", exc_info=True)
            self.db_session.rollback()
    
    def get_logs(self) -> List[AILogicFlowLog]:
        """Get all logged steps for this flow."""
        return self._logs.copy()
    
    def get_flow_summary(self) -> Dict[str, Any]:
        """Get a summary of the flow for quick analysis."""
        total_duration = sum(
            log.duration_ms or 0 for log in self._logs
        )
        total_tokens = sum(
            log.tokens_used or 0 for log in self._logs
        )
        error_count = sum(
            1 for log in self._logs if log.error_message
        )
        
        return {
            "logic_version": self.logic_version_string,
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "turn_index": self.turn_index,
            "step_count": len(self._logs),
            "total_duration_ms": total_duration,
            "total_tokens": total_tokens,
            "error_count": error_count,
            "steps": [log.to_summary() for log in self._logs],
        }
    
    def _truncate_data(
        self,
        data: Optional[Dict[str, Any]],
        max_str_len: int = 1000,
        max_list_items: int = 20,
    ) -> Optional[Dict[str, Any]]:
        """Truncate large data structures for storage.
        
        Args:
            data: Data to truncate
            max_str_len: Maximum string length
            max_list_items: Maximum list items to keep
            
        Returns:
            Truncated data
        """
        if data is None:
            return None
        
        def truncate_value(v, depth=0):
            if depth > 5:
                return "[max depth]"
            
            if isinstance(v, str):
                if len(v) > max_str_len:
                    return v[:max_str_len] + f"... [truncated {len(v) - max_str_len} chars]"
                return v
            elif isinstance(v, list):
                if len(v) > max_list_items:
                    truncated = [truncate_value(item, depth + 1) for item in v[:max_list_items]]
                    truncated.append(f"... [truncated {len(v) - max_list_items} items]")
                    return truncated
                return [truncate_value(item, depth + 1) for item in v]
            elif isinstance(v, dict):
                return {k: truncate_value(val, depth + 1) for k, val in v.items()}
            else:
                return v
        
        return truncate_value(data)


class TimedStepContext:
    """Context for timed steps, allowing output data to be set."""
    
    def __init__(
        self,
        input_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.input_data = input_data
        self.output_data: Optional[Dict[str, Any]] = None
        self.metadata = metadata
        self.tokens_used: Optional[int] = None


def create_logic_version(
    db_session,
    version_id: str,
    name: str,
    description: str,
    configuration: Dict[str, Any],
    max_iterations: int = 10,
    system_prompt: Optional[str] = None,
    is_baseline: bool = False,
    activate: bool = False,
) -> AILogicVersion:
    """Create a new logic version.
    
    Args:
        db_session: SQLAlchemy session
        version_id: Version identifier
        name: Human-readable name
        description: Description of changes
        configuration: Configuration dict
        max_iterations: Max iterations
        system_prompt: System prompt for hash
        is_baseline: Whether this is a baseline
        activate: Whether to activate this version
        
    Returns:
        Created AILogicVersion
    """
    # Check for existing
    existing = db_session.query(AILogicVersion).filter(
        AILogicVersion.version_id == version_id
    ).first()
    
    if existing:
        raise ValueError(f"Logic version {version_id} already exists")
    
    prompt_hash = compute_prompt_hash(system_prompt) if system_prompt else None
    
    version = AILogicVersion(
        version_id=version_id,
        name=name,
        description=description,
        configuration=configuration,
        system_prompt_hash=prompt_hash,
        max_iterations=max_iterations,
        is_active=activate,
        is_baseline=is_baseline,
    )
    
    if activate:
        # Deactivate others
        db_session.query(AILogicVersion).filter(
            AILogicVersion.is_active == True
        ).update({"is_active": False})
    
    db_session.add(version)
    db_session.commit()
    db_session.refresh(version)
    
    logger.info(
        f"Created logic version: {version_id}",
        extra={"version_id": version_id, "is_active": activate}
    )
    
    return version


def deprecate_logic_version(
    db_session,
    version_id: str,
) -> Optional[AILogicVersion]:
    """Deprecate a logic version.
    
    Args:
        db_session: SQLAlchemy session
        version_id: Version to deprecate
        
    Returns:
        Updated AILogicVersion or None
    """
    version = db_session.query(AILogicVersion).filter(
        AILogicVersion.version_id == version_id
    ).first()
    
    if version:
        version.deprecated_at = datetime.utcnow()
        version.is_active = False
        db_session.commit()
        db_session.refresh(version)
        
        logger.info(f"Deprecated logic version: {version_id}")
    
    return version


def get_logic_version_stats(
    db_session,
    version_id: str,
) -> Dict[str, Any]:
    """Get statistics for a logic version.
    
    Args:
        db_session: SQLAlchemy session
        version_id: Version to get stats for
        
    Returns:
        Statistics dictionary
    """
    from sqlalchemy import func
    
    version = db_session.query(AILogicVersion).filter(
        AILogicVersion.version_id == version_id
    ).first()
    
    if not version:
        return {"error": "Version not found"}
    
    # Get flow log stats
    log_count = db_session.query(func.count(AILogicFlowLog.id)).filter(
        AILogicFlowLog.logic_version_id == version.id
    ).scalar()
    
    conversation_count = db_session.query(
        func.count(func.distinct(AILogicFlowLog.conversation_id))
    ).filter(
        AILogicFlowLog.logic_version_id == version.id
    ).scalar()
    
    avg_duration = db_session.query(
        func.avg(AILogicFlowLog.duration_ms)
    ).filter(
        AILogicFlowLog.logic_version_id == version.id,
        AILogicFlowLog.step_type == LogicStepType.LLM_CALL
    ).scalar()
    
    total_tokens = db_session.query(
        func.sum(AILogicFlowLog.tokens_used)
    ).filter(
        AILogicFlowLog.logic_version_id == version.id
    ).scalar()
    
    error_count = db_session.query(func.count(AILogicFlowLog.id)).filter(
        AILogicFlowLog.logic_version_id == version.id,
        AILogicFlowLog.error_message != None
    ).scalar()
    
    return {
        "version": version.to_dict(),
        "stats": {
            "total_steps_logged": log_count or 0,
            "conversations_processed": conversation_count or 0,
            "avg_llm_call_duration_ms": float(avg_duration) if avg_duration else None,
            "total_tokens_used": total_tokens or 0,
            "error_count": error_count or 0,
        },
    }

