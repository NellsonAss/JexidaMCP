"""Action registry for AI-accessible operations.

Manages action registration, permission checking, and execution.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

# Import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from logging_config import get_logger

logger = get_logger(__name__)


class ActionType(str, Enum):
    """Types of actions that can be performed."""
    QUERY = "query"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"


@dataclass
class ActionResult:
    """Result from executing an action.
    
    Attributes:
        success: Whether the action succeeded
        message: Human-readable result message
        data: Optional data returned by the action
        requires_confirmation: Whether user must confirm
        confirmation_id: ID for pending confirmation
        error: Error message if failed
    """
    success: bool
    message: str
    data: Optional[Any] = None
    requires_confirmation: bool = False
    confirmation_id: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "success": self.success,
            "message": self.message,
        }
        if self.data is not None:
            result["data"] = self.data
        if self.requires_confirmation:
            result["requires_confirmation"] = True
            result["confirmation_id"] = self.confirmation_id
        if self.error:
            result["error"] = self.error
        return result


@dataclass
class ActionDefinition:
    """Definition of an AI-accessible action.
    
    Attributes:
        name: Unique identifier for the action
        display_name: Human-readable name
        description: What the action does
        action_type: Type of action (query, create, update, delete, execute)
        parameters: JSON Schema for action parameters
        execute_fn: Async function to execute the action
        requires_confirmation: Whether user must confirm before executing
        is_destructive: Whether action has destructive effects
        required_roles: List of roles that can perform this action
        tags: Optional tags for categorization
    """
    name: str
    display_name: str
    description: str
    action_type: ActionType
    parameters: Dict[str, Any]
    execute_fn: Callable
    requires_confirmation: bool = False
    is_destructive: bool = False
    required_roles: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    
    def check_permission(self, user_roles: List[str]) -> bool:
        """Check if user has permission to perform this action.
        
        Args:
            user_roles: List of roles the user has
            
        Returns:
            True if user can perform the action
        """
        if not self.required_roles:
            return True  # No role requirements
        
        return any(role in self.required_roles for role in user_roles)
    
    def to_function_definition(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling format.
        
        Returns:
            Function definition dictionary
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class ActionRegistry:
    """Central registry for AI-accessible actions.
    
    Manages action registration, discovery, and execution with
    permission checking and audit logging.
    """
    
    def __init__(self):
        """Initialize the action registry."""
        self._actions: Dict[str, ActionDefinition] = {}
        self._pending_confirmations: Dict[str, Dict[str, Any]] = {}
    
    def register(self, action: ActionDefinition) -> None:
        """Register a new action.
        
        Args:
            action: Action definition to register
            
        Raises:
            ValueError: If action with same name already exists
        """
        if action.name in self._actions:
            raise ValueError(f"Action '{action.name}' is already registered")
        
        self._actions[action.name] = action
        logger.debug(
            f"Registered action: {action.name}",
            extra={"action": action.name, "type": action.action_type.value}
        )
    
    def get(self, name: str) -> Optional[ActionDefinition]:
        """Get an action by name.
        
        Args:
            name: Action identifier
            
        Returns:
            ActionDefinition if found, None otherwise
        """
        return self._actions.get(name)
    
    def list_actions(self) -> List[ActionDefinition]:
        """Get all registered actions.
        
        Returns:
            List of all action definitions
        """
        return list(self._actions.values())
    
    def get_available_actions(
        self,
        user_roles: Optional[List[str]] = None,
        action_types: Optional[List[ActionType]] = None,
        tags: Optional[List[str]] = None,
    ) -> List[ActionDefinition]:
        """Get actions available to a user.
        
        Args:
            user_roles: User's roles for permission filtering
            action_types: Filter by action types
            tags: Filter by tags
            
        Returns:
            List of available action definitions
        """
        user_roles = user_roles or []
        actions = self.list_actions()
        
        # Filter by permissions
        actions = [a for a in actions if a.check_permission(user_roles)]
        
        # Filter by action type
        if action_types:
            actions = [a for a in actions if a.action_type in action_types]
        
        # Filter by tags
        if tags:
            actions = [
                a for a in actions
                if any(tag in a.tags for tag in tags)
            ]
        
        return actions
    
    def get_function_definitions(
        self,
        user_roles: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Get function definitions for available actions.
        
        Args:
            user_roles: User's roles for permission filtering
            
        Returns:
            List of function definitions in OpenAI format
        """
        actions = self.get_available_actions(user_roles)
        return [action.to_function_definition() for action in actions]
    
    async def execute(
        self,
        name: str,
        parameters: Dict[str, Any],
        user_id: Optional[str] = None,
        user_roles: Optional[List[str]] = None,
        skip_confirmation: bool = False,
    ) -> ActionResult:
        """Execute an action.
        
        Args:
            name: Action name
            parameters: Action parameters
            user_id: ID of user executing the action
            user_roles: User's roles for permission checking
            skip_confirmation: Skip confirmation for actions that require it
            
        Returns:
            ActionResult with execution outcome
        """
        action = self.get(name)
        
        if action is None:
            return ActionResult(
                success=False,
                message=f"Action '{name}' not found",
                error="action_not_found",
            )
        
        # Check permissions
        if not action.check_permission(user_roles or []):
            logger.warning(
                f"Permission denied for action: {name}",
                extra={
                    "action": name,
                    "user_id": user_id,
                    "user_roles": user_roles,
                }
            )
            return ActionResult(
                success=False,
                message="You don't have permission to perform this action",
                error="permission_denied",
            )
        
        # Check if confirmation required
        if action.requires_confirmation and not skip_confirmation:
            confirmation_id = str(uuid.uuid4())
            self._pending_confirmations[confirmation_id] = {
                "action_name": name,
                "parameters": parameters,
                "user_id": user_id,
                "created_at": datetime.now(timezone.utc),
            }
            
            return ActionResult(
                success=True,
                message=f"Action '{action.display_name}' requires confirmation",
                requires_confirmation=True,
                confirmation_id=confirmation_id,
            )
        
        # Execute the action
        try:
            logger.info(
                f"Executing action: {name}",
                extra={
                    "action": name,
                    "user_id": user_id,
                    "action_type": action.action_type.value,
                }
            )
            
            result = await action.execute_fn(parameters, user_id=user_id)
            
            if isinstance(result, ActionResult):
                return result
            elif isinstance(result, dict):
                return ActionResult(
                    success=True,
                    message="Action completed successfully",
                    data=result,
                )
            else:
                return ActionResult(
                    success=True,
                    message=str(result) if result else "Action completed",
                )
        
        except Exception as e:
            logger.error(
                f"Action execution failed: {name}",
                extra={
                    "action": name,
                    "user_id": user_id,
                    "error": str(e),
                }
            )
            return ActionResult(
                success=False,
                message=f"Action failed: {str(e)}",
                error="execution_error",
            )
    
    async def confirm_action(
        self,
        confirmation_id: str,
        user_id: Optional[str] = None,
    ) -> ActionResult:
        """Confirm and execute a pending action.
        
        Args:
            confirmation_id: ID from requires_confirmation response
            user_id: ID of user confirming
            
        Returns:
            ActionResult from execution
        """
        pending = self._pending_confirmations.pop(confirmation_id, None)
        
        if pending is None:
            return ActionResult(
                success=False,
                message="Confirmation not found or expired",
                error="confirmation_not_found",
            )
        
        # Verify user matches
        if pending["user_id"] != user_id:
            # Put it back
            self._pending_confirmations[confirmation_id] = pending
            return ActionResult(
                success=False,
                message="You cannot confirm another user's action",
                error="user_mismatch",
            )
        
        # Execute with skip_confirmation
        return await self.execute(
            name=pending["action_name"],
            parameters=pending["parameters"],
            user_id=user_id,
            skip_confirmation=True,
        )
    
    def cancel_confirmation(self, confirmation_id: str) -> bool:
        """Cancel a pending confirmation.
        
        Args:
            confirmation_id: ID to cancel
            
        Returns:
            True if cancelled, False if not found
        """
        return self._pending_confirmations.pop(confirmation_id, None) is not None


# Global registry instance
_registry: Optional[ActionRegistry] = None


def get_action_registry() -> ActionRegistry:
    """Get the global action registry.
    
    Returns:
        Global ActionRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = ActionRegistry()
    return _registry


def action(
    name: str,
    display_name: str,
    description: str,
    action_type: ActionType,
    parameters: Dict[str, Any],
    requires_confirmation: bool = False,
    is_destructive: bool = False,
    required_roles: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
) -> Callable:
    """Decorator to register a function as an action.
    
    Args:
        name: Unique action identifier
        display_name: Human-readable name
        description: Action description
        action_type: Type of action
        parameters: JSON Schema for parameters
        requires_confirmation: Whether confirmation is needed
        is_destructive: Whether action is destructive
        required_roles: Required roles
        tags: Optional tags
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        action_def = ActionDefinition(
            name=name,
            display_name=display_name,
            description=description,
            action_type=action_type,
            parameters=parameters,
            execute_fn=func,
            requires_confirmation=requires_confirmation,
            is_destructive=is_destructive,
            required_roles=required_roles or [],
            tags=tags or [],
        )
        get_action_registry().register(action_def)
        return func
    return decorator

