"""Task progress tracking and SSE event emission for AI assistant.

Provides real-time progress updates for multi-step agentic tasks using
Server-Sent Events (SSE). Supports hierarchical task trees with
auto-expand/collapse behavior.

Event Types:
- task.start: New task begins (UI auto-expands)
- task.update: Progress update (e.g., "thinking...")
- task.done: Task completed (UI auto-collapses to summary)
- task.error: Task failed
- message.chunk: Streaming text content
- done: Full response complete
"""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional, Union


class TaskStatus(str, Enum):
    """Status of a task in the progress tree."""
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class EventType(str, Enum):
    """SSE event types for progress updates."""
    TASK_START = "task.start"
    TASK_UPDATE = "task.update"
    TASK_DONE = "task.done"
    TASK_ERROR = "task.error"
    MESSAGE_CHUNK = "message.chunk"
    DONE = "done"


@dataclass
class TaskProgress:
    """Represents a task in the hierarchical progress tree.
    
    Attributes:
        id: Unique task identifier
        parent_id: Parent task ID for hierarchy (None for root tasks)
        title: Display title for the task
        status: Current task status
        summary: Brief result summary (shown when collapsed)
        detail: Extended detail information
        children: List of child task IDs
        started_at: When the task started
        completed_at: When the task completed (if done)
        metadata: Additional task metadata
    """
    id: str
    title: str
    parent_id: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    summary: str = ""
    detail: str = ""
    children: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "title": self.title,
            "status": self.status.value,
            "summary": self.summary,
            "detail": self.detail,
            "children": self.children,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata,
        }


@dataclass 
class ProgressEvent:
    """An SSE event for progress updates.
    
    Attributes:
        event_type: Type of event
        task: Task progress data (for task events)
        content: Content data (for message events)
        conversation_id: Associated conversation ID
        timestamp: When the event was created
    """
    event_type: EventType
    task: Optional[TaskProgress] = None
    content: Optional[str] = None
    conversation_id: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_sse(self) -> str:
        """Format as Server-Sent Event string.
        
        Returns SSE-formatted string: 'event: <type>\ndata: <json>\n\n'
        """
        data = {
            "event": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "conversation_id": self.conversation_id,
        }
        
        if self.task:
            data["task"] = self.task.to_dict()
        
        if self.content is not None:
            data["content"] = self.content
            
        return f"event: {self.event_type.value}\ndata: {json.dumps(data)}\n\n"


class ProgressEmitter:
    """Manages progress events for a single request/conversation.
    
    Creates and emits SSE events for task progress, supporting
    hierarchical task trees with parent-child relationships.
    
    Usage:
        emitter = ProgressEmitter(conversation_id=123)
        
        # Start a parent task
        await emitter.emit_start("main", "Processing request")
        
        # Start a child task
        await emitter.emit_start("tool-1", "Executing list_devices", parent_id="main")
        
        # Complete the child
        await emitter.emit_done("tool-1", "Found 12 devices")
        
        # Complete the parent
        await emitter.emit_done("main", "Request completed")
        
        # Get events as SSE stream
        async for event in emitter.stream():
            yield event
    """
    
    def __init__(self, conversation_id: Optional[int] = None):
        """Initialize the progress emitter.
        
        Args:
            conversation_id: Associated conversation ID
        """
        self.conversation_id = conversation_id
        self._queue: asyncio.Queue[ProgressEvent] = asyncio.Queue()
        self._tasks: Dict[str, TaskProgress] = {}
        self._closed = False
        self._root_task_id: Optional[str] = None
    
    def generate_task_id(self, prefix: str = "task") -> str:
        """Generate a unique task ID.
        
        Args:
            prefix: Prefix for the task ID
            
        Returns:
            Unique task ID string
        """
        return f"{prefix}-{uuid.uuid4().hex[:8]}"
    
    async def emit_start(
        self,
        task_id: str,
        title: str,
        parent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TaskProgress:
        """Emit a task start event.
        
        Args:
            task_id: Unique task identifier
            title: Display title for the task
            parent_id: Parent task ID (None for root tasks)
            metadata: Additional task metadata
            
        Returns:
            The created TaskProgress instance
        """
        task = TaskProgress(
            id=task_id,
            title=title,
            parent_id=parent_id,
            status=TaskStatus.RUNNING,
            started_at=datetime.utcnow(),
            metadata=metadata or {},
        )
        
        self._tasks[task_id] = task
        
        # Track root task
        if parent_id is None and self._root_task_id is None:
            self._root_task_id = task_id
        
        # Add to parent's children list
        if parent_id and parent_id in self._tasks:
            self._tasks[parent_id].children.append(task_id)
        
        event = ProgressEvent(
            event_type=EventType.TASK_START,
            task=task,
            conversation_id=self.conversation_id,
        )
        await self._queue.put(event)
        
        return task
    
    async def emit_update(
        self,
        task_id: str,
        detail: str,
        title: Optional[str] = None,
    ) -> None:
        """Emit a task update event.
        
        Args:
            task_id: Task to update
            detail: Progress detail/status text
            title: Optional new title
        """
        if task_id not in self._tasks:
            return
        
        task = self._tasks[task_id]
        task.detail = detail
        if title:
            task.title = title
        
        event = ProgressEvent(
            event_type=EventType.TASK_UPDATE,
            task=task,
            conversation_id=self.conversation_id,
        )
        await self._queue.put(event)
    
    async def emit_done(
        self,
        task_id: str,
        summary: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit a task completion event.
        
        Args:
            task_id: Task that completed
            summary: Brief result summary
            metadata: Additional result metadata
        """
        if task_id not in self._tasks:
            return
        
        task = self._tasks[task_id]
        task.status = TaskStatus.DONE
        task.summary = summary
        task.completed_at = datetime.utcnow()
        if metadata:
            task.metadata.update(metadata)
        
        event = ProgressEvent(
            event_type=EventType.TASK_DONE,
            task=task,
            conversation_id=self.conversation_id,
        )
        await self._queue.put(event)
    
    async def emit_error(
        self,
        task_id: str,
        error_message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit a task error event.
        
        Args:
            task_id: Task that failed
            error_message: Error description
            metadata: Additional error metadata
        """
        if task_id not in self._tasks:
            return
        
        task = self._tasks[task_id]
        task.status = TaskStatus.ERROR
        task.summary = error_message
        task.completed_at = datetime.utcnow()
        if metadata:
            task.metadata.update(metadata)
        
        event = ProgressEvent(
            event_type=EventType.TASK_ERROR,
            task=task,
            conversation_id=self.conversation_id,
        )
        await self._queue.put(event)
    
    async def emit_message_chunk(self, content: str) -> None:
        """Emit a streaming message chunk.
        
        Args:
            content: Text content chunk
        """
        event = ProgressEvent(
            event_type=EventType.MESSAGE_CHUNK,
            content=content,
            conversation_id=self.conversation_id,
        )
        await self._queue.put(event)
    
    async def emit_done_signal(
        self,
        final_content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit the final done signal.
        
        Args:
            final_content: Optional final message content
            metadata: Optional final metadata (tokens_used, etc.)
        """
        # Create a synthetic task for the done signal with metadata
        done_task = TaskProgress(
            id="__done__",
            title="Complete",
            status=TaskStatus.DONE,
            summary=final_content or "",
            metadata=metadata or {},
        )
        
        event = ProgressEvent(
            event_type=EventType.DONE,
            task=done_task,
            content=final_content,
            conversation_id=self.conversation_id,
        )
        await self._queue.put(event)
        self._closed = True
    
    async def stream(self) -> AsyncGenerator[str, None]:
        """Stream events as SSE-formatted strings.
        
        Yields:
            SSE-formatted event strings
        """
        while not self._closed or not self._queue.empty():
            try:
                # Wait for event with timeout to allow checking closed status
                event = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=0.5
                )
                yield event.to_sse()
                
                # Stop after done signal
                if event.event_type == EventType.DONE:
                    break
                    
            except asyncio.TimeoutError:
                # Send keepalive comment
                yield ": keepalive\n\n"
                continue
    
    def get_task(self, task_id: str) -> Optional[TaskProgress]:
        """Get a task by ID.
        
        Args:
            task_id: Task identifier
            
        Returns:
            TaskProgress if found, None otherwise
        """
        return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> List[TaskProgress]:
        """Get all tasks.
        
        Returns:
            List of all TaskProgress instances
        """
        return list(self._tasks.values())
    
    def get_task_tree(self) -> Optional[Dict[str, Any]]:
        """Get the full task tree starting from root.
        
        Returns:
            Nested dictionary representation of task tree
        """
        if not self._root_task_id:
            return None
        
        def build_tree(task_id: str) -> Dict[str, Any]:
            task = self._tasks.get(task_id)
            if not task:
                return {}
            
            result = task.to_dict()
            result["children"] = [
                build_tree(child_id) 
                for child_id in task.children
            ]
            return result
        
        return build_tree(self._root_task_id)


class ProgressContext:
    """Context manager for scoped progress tracking.
    
    Usage:
        async with ProgressContext(emitter, "task-1", "Processing") as ctx:
            # Do work...
            ctx.update("50% complete")
            # More work...
        # Automatically emits done on exit
    """
    
    def __init__(
        self,
        emitter: ProgressEmitter,
        task_id: str,
        title: str,
        parent_id: Optional[str] = None,
    ):
        self.emitter = emitter
        self.task_id = task_id
        self.title = title
        self.parent_id = parent_id
        self._summary = "Completed"
        self._error: Optional[str] = None
    
    async def __aenter__(self) -> "ProgressContext":
        await self.emitter.emit_start(
            self.task_id,
            self.title,
            self.parent_id,
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            await self.emitter.emit_error(
                self.task_id,
                str(exc_val) if exc_val else "Unknown error",
            )
        else:
            await self.emitter.emit_done(self.task_id, self._summary)
    
    async def update(self, detail: str) -> None:
        """Update progress detail."""
        await self.emitter.emit_update(self.task_id, detail)
    
    def set_summary(self, summary: str) -> None:
        """Set the completion summary."""
        self._summary = summary

