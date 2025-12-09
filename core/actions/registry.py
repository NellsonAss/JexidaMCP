"""Action registry for AI-accessible operations.

Manages action registration, permission checking, and execution.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union

from pydantic import BaseModel

from ..logging import get_logger
from .validation import (
    ValidationResult,
    validate_parameters,
    format_missing_fields_message,
)

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
        action_type: Type of action
        parameters: JSON Schema for action parameters
        execute_fn: Async function to execute the action
        requires_confirmation: Whether user must confirm before executing
        is_destructive: Whether action has destructive effects
        required_roles: List of roles that can perform this action
        tags: Optional tags for categorization
        input_schema: Optional Pydantic model for input validation
        pre_validate_fn: Optional custom validator called before confirmation
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
    input_schema: Optional[Type[BaseModel]] = None
    pre_validate_fn: Optional[Callable] = None
    
    def check_permission(self, user_roles: List[str]) -> bool:
        """Check if user has permission to perform this action."""
        if not self.required_roles:
            return True
        return any(role in self.required_roles for role in user_roles)
    
    def get_validation_schema(self) -> Union[Dict[str, Any], Type[BaseModel], None]:
        """Get the schema to use for validation."""
        if self.input_schema is not None:
            return self.input_schema
        return self.parameters
    
    def to_function_definition(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling format."""
        if self.input_schema is not None:
            try:
                json_schema = self.input_schema.model_json_schema()
                params = {
                    "type": "object",
                    "properties": json_schema.get("properties", {}),
                    "required": json_schema.get("required", []),
                }
            except Exception:
                params = self.parameters
        else:
            params = self.parameters
        
        return {
            "name": self.name,
            "description": self.description,
            "parameters": params,
        }


class ActionRegistry:
    """Central registry for AI-accessible actions."""
    
    def __init__(self):
        """Initialize the action registry."""
        self._actions: Dict[str, ActionDefinition] = {}
        self._pending_confirmations: Dict[str, Dict[str, Any]] = {}
    
    def register(self, action: ActionDefinition) -> None:
        """Register a new action."""
        if action.name in self._actions:
            raise ValueError(f"Action '{action.name}' is already registered")
        
        self._actions[action.name] = action
        logger.debug(f"Registered action: {action.name}")
    
    def get(self, name: str) -> Optional[ActionDefinition]:
        """Get an action by name."""
        return self._actions.get(name)
    
    def list_actions(self) -> List[ActionDefinition]:
        """Get all registered actions."""
        return list(self._actions.values())
    
    def get_available_actions(
        self,
        user_roles: Optional[List[str]] = None,
        action_types: Optional[List[ActionType]] = None,
        tags: Optional[List[str]] = None,
    ) -> List[ActionDefinition]:
        """Get actions available to a user."""
        user_roles = user_roles or []
        actions = self.list_actions()
        
        actions = [a for a in actions if a.check_permission(user_roles)]
        
        if action_types:
            actions = [a for a in actions if a.action_type in action_types]
        
        if tags:
            actions = [a for a in actions if any(tag in a.tags for tag in tags)]
        
        return actions
    
    def get_function_definitions(
        self,
        user_roles: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Get function definitions for available actions."""
        actions = self.get_available_actions(user_roles)
        return [action.to_function_definition() for action in actions]
    
    async def execute(
        self,
        name: str,
        parameters: Dict[str, Any],
        user_id: Optional[str] = None,
        user_roles: Optional[List[str]] = None,
        skip_confirmation: bool = False,
        skip_validation: bool = False,
    ) -> ActionResult:
        """Execute an action."""
        action = self.get(name)
        
        if action is None:
            return ActionResult(
                success=False,
                message=f"Action '{name}' not found",
                error="action_not_found",
            )
        
        if not action.check_permission(user_roles or []):
            return ActionResult(
                success=False,
                message="You don't have permission to perform this action",
                error="permission_denied",
            )
        
        if not skip_validation:
            validation_schema = action.get_validation_schema()
            validation_result = validate_parameters(parameters, validation_schema)
            
            if not validation_result.is_valid:
                error_message = format_missing_fields_message(
                    validation_result.missing_fields,
                    validation_schema,
                )
                
                return ActionResult(
                    success=False,
                    message=error_message,
                    error="missing_required_fields",
                    data={
                        "missing_fields": validation_result.missing_fields,
                        "invalid_fields": validation_result.invalid_fields,
                    },
                )
            
            if action.pre_validate_fn is not None:
                try:
                    pre_valid, pre_error_msg, pre_error_data = action.pre_validate_fn(parameters)
                    if not pre_valid:
                        return ActionResult(
                            success=False,
                            message=pre_error_msg,
                            error="pre_validation_failed",
                            data=pre_error_data,
                        )
                except Exception as e:
                    return ActionResult(
                        success=False,
                        message=f"Validation error: {str(e)}",
                        error="pre_validation_error",
                    )
        
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
        
        try:
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
            logger.error(f"Action execution failed: {name} - {e}")
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
        """Confirm and execute a pending action."""
        pending = self._pending_confirmations.pop(confirmation_id, None)
        
        if pending is None:
            return ActionResult(
                success=False,
                message="Confirmation not found or expired",
                error="confirmation_not_found",
            )
        
        if pending["user_id"] != user_id:
            self._pending_confirmations[confirmation_id] = pending
            return ActionResult(
                success=False,
                message="You cannot confirm another user's action",
                error="user_mismatch",
            )
        
        return await self.execute(
            name=pending["action_name"],
            parameters=pending["parameters"],
            user_id=user_id,
            skip_confirmation=True,
            skip_validation=True,
        )
    
    def cancel_confirmation(self, confirmation_id: str) -> bool:
        """Cancel a pending confirmation."""
        return self._pending_confirmations.pop(confirmation_id, None) is not None


# Global registry instance
_registry: Optional[ActionRegistry] = None


def get_action_registry() -> ActionRegistry:
    """Get the global action registry."""
    global _registry
    if _registry is None:
        _registry = ActionRegistry()
    return _registry


def action(
    name: str,
    display_name: str,
    description: str,
    action_type: ActionType,
    parameters: Optional[Dict[str, Any]] = None,
    requires_confirmation: bool = False,
    is_destructive: bool = False,
    required_roles: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    input_schema: Optional[Type[BaseModel]] = None,
    pre_validate_fn: Optional[Callable] = None,
) -> Callable:
    """Decorator to register a function as an action."""
    def decorator(func: Callable) -> Callable:
        effective_parameters = parameters or {"type": "object", "properties": {}}
        
        if input_schema is not None and parameters is None:
            try:
                json_schema = input_schema.model_json_schema()
                effective_parameters = {
                    "type": "object",
                    "properties": json_schema.get("properties", {}),
                    "required": json_schema.get("required", []),
                }
            except Exception as e:
                logger.warning(f"Could not generate schema from input_schema: {e}")
        
        action_def = ActionDefinition(
            name=name,
            display_name=display_name,
            description=description,
            action_type=action_type,
            parameters=effective_parameters,
            execute_fn=func,
            requires_confirmation=requires_confirmation,
            is_destructive=is_destructive,
            required_roles=required_roles or [],
            tags=tags or [],
            input_schema=input_schema,
            pre_validate_fn=pre_validate_fn,
        )
        get_action_registry().register(action_def)
        return func
    return decorator

