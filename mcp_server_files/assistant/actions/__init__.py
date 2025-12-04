"""Action registry for AI-accessible operations.

Provides:
- ActionRegistry for registering and discovering actions
- ActionDefinition for defining action metadata
- Dynamic CRUD actions for database models
"""

from .registry import (
    ActionRegistry,
    ActionDefinition,
    ActionResult,
    get_action_registry,
    action,
)
from .dynamic import register_dynamic_actions

__all__ = [
    "ActionRegistry",
    "ActionDefinition",
    "ActionResult",
    "get_action_registry",
    "action",
    "register_dynamic_actions",
]

