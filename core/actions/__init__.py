"""Action registry for AI-accessible operations.

Provides:
- ActionRegistry for registering and discovering actions
- ActionDefinition for defining action metadata
- Schema-driven validation for pre-confirmation checks
"""

from .registry import (
    ActionRegistry,
    ActionDefinition,
    ActionResult,
    ActionType,
    get_action_registry,
    action,
)
from .validation import (
    ValidationResult,
    validate_parameters,
    get_required_fields_from_json_schema,
    get_required_fields_from_pydantic,
    format_missing_fields_message,
)

__all__ = [
    # Registry
    "ActionRegistry",
    "ActionDefinition",
    "ActionResult",
    "ActionType",
    "get_action_registry",
    "action",
    # Validation
    "ValidationResult",
    "validate_parameters",
    "get_required_fields_from_json_schema",
    "get_required_fields_from_pydantic",
    "format_missing_fields_message",
]

