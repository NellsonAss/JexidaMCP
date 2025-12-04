"""Dynamic CRUD actions for database models.

Provides generic model_query, model_create, model_update, and model_delete
actions that work with any SQLAlchemy model.
"""

import sys
import os
from typing import Any, Dict, List, Optional, Type

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from logging_config import get_logger

from .registry import (
    ActionDefinition,
    ActionResult,
    ActionType,
    get_action_registry,
)
from ..model_introspection import (
    generate_model_schema,
    generate_model_query_schema,
    get_model_description,
)

logger = get_logger(__name__)


# Model permission configuration
# Customize this based on your application's needs
MODEL_PERMISSIONS: Dict[str, Dict[str, List[str]]] = {
    # Example: "Secret": {"read": ["admin"], "write": ["admin"]}
}

# Fields that are auto-assigned to the current user
OWNERSHIP_FIELDS = {"created_by", "updated_by", "owner_id", "user_id"}


def check_model_permission(
    user_roles: List[str],
    model_name: str,
    operation: str,
) -> bool:
    """Check if user has permission for a model operation.
    
    Args:
        user_roles: User's roles
        model_name: Name of the model
        operation: Operation type (read, write, delete)
        
    Returns:
        True if permitted
    """
    if model_name not in MODEL_PERMISSIONS:
        return True  # No restrictions defined
    
    allowed_roles = MODEL_PERMISSIONS[model_name].get(operation, [])
    if not allowed_roles:
        return True  # No restrictions for this operation
    
    return any(role in allowed_roles for role in user_roles)


def filter_valid_fields(
    model: Type,
    field_data: Dict[str, Any],
    operation: str,
) -> tuple:
    """Filter and validate fields for a model operation.
    
    Args:
        model: SQLAlchemy model class
        field_data: Fields to validate
        operation: Operation type (create, update)
        
    Returns:
        Tuple of (valid_fields, invalid_fields)
    """
    try:
        from sqlalchemy import inspect
        
        mapper = inspect(model)
        valid_column_names = {col.name for col in mapper.columns}
        
        # Auto-exclude fields
        auto_exclude = {"id", "created_at", "updated_at"}
        if operation == "create":
            valid_column_names = valid_column_names - auto_exclude
        
        valid_fields = {}
        invalid_fields = []
        
        for field_name, value in field_data.items():
            if field_name in valid_column_names:
                valid_fields[field_name] = value
            else:
                invalid_fields.append(field_name)
        
        return valid_fields, invalid_fields
    
    except Exception as e:
        logger.warning(f"Failed to filter fields: {e}")
        return {}, list(field_data.keys())


def get_ownership_field(model: Type) -> Optional[str]:
    """Get the ownership field for a model.
    
    Args:
        model: SQLAlchemy model class
        
    Returns:
        Field name if found, None otherwise
    """
    try:
        from sqlalchemy import inspect
        
        mapper = inspect(model)
        column_names = {col.name for col in mapper.columns}
        
        for field_name in OWNERSHIP_FIELDS:
            if field_name in column_names:
                return field_name
        
        return None
    
    except Exception:
        return None


def get_model_by_name(model_name: str) -> Optional[Type]:
    """Get a model class by name.
    
    Args:
        model_name: Name of the model
        
    Returns:
        Model class if found, None otherwise
    """
    try:
        from database import Base
        
        for mapper in Base.registry.mappers:
            if mapper.class_.__name__ == model_name:
                return mapper.class_
        
        return None
    
    except Exception as e:
        logger.warning(f"Failed to get model {model_name}: {e}")
        return None


async def execute_model_query(
    params: Dict[str, Any],
    user_id: Optional[str] = None,
) -> ActionResult:
    """Execute a model query action.
    
    Args:
        params: Query parameters including model_name and filters
        user_id: ID of user executing
        
    Returns:
        ActionResult with query results
    """
    model_name = params.get("model_name")
    filters = params.get("filters", {})
    order_by = params.get("order_by")
    limit = params.get("limit", 10)
    offset = params.get("offset", 0)
    
    if not model_name:
        return ActionResult(
            success=False,
            message="model_name is required",
            error="missing_parameter",
        )
    
    model = get_model_by_name(model_name)
    if model is None:
        return ActionResult(
            success=False,
            message=f"Model '{model_name}' not found",
            error="model_not_found",
        )
    
    try:
        from database import get_db
        
        db = next(get_db())
        try:
            query = db.query(model)
            
            # Apply filters
            for field_name, value in filters.items():
                if hasattr(model, field_name):
                    column = getattr(model, field_name)
                    if isinstance(value, str) and "%" in value:
                        query = query.filter(column.like(value))
                    else:
                        query = query.filter(column == value)
            
            # Apply ordering
            if order_by:
                descending = order_by.startswith("-")
                field_name = order_by.lstrip("-")
                if hasattr(model, field_name):
                    column = getattr(model, field_name)
                    if descending:
                        column = column.desc()
                    query = query.order_by(column)
            
            # Apply pagination
            total = query.count()
            results = query.offset(offset).limit(limit).all()
            
            # Serialize results
            data = []
            for item in results:
                item_dict = {}
                for col in model.__table__.columns:
                    value = getattr(item, col.name)
                    # Convert datetime to ISO string
                    if hasattr(value, "isoformat"):
                        value = value.isoformat()
                    item_dict[col.name] = value
                data.append(item_dict)
            
            return ActionResult(
                success=True,
                message=f"Found {total} {model_name} records",
                data={
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "results": data,
                },
            )
        
        finally:
            db.close()
    
    except Exception as e:
        logger.error(f"Model query failed: {e}")
        return ActionResult(
            success=False,
            message=f"Query failed: {str(e)}",
            error="query_error",
        )


async def execute_model_create(
    params: Dict[str, Any],
    user_id: Optional[str] = None,
) -> ActionResult:
    """Execute a model create action.
    
    Args:
        params: Create parameters including model_name and field_data
        user_id: ID of user executing
        
    Returns:
        ActionResult with created record
    """
    model_name = params.get("model_name")
    field_data = params.get("data", {})
    
    if not model_name:
        return ActionResult(
            success=False,
            message="model_name is required",
            error="missing_parameter",
        )
    
    model = get_model_by_name(model_name)
    if model is None:
        return ActionResult(
            success=False,
            message=f"Model '{model_name}' not found",
            error="model_not_found",
        )
    
    # Filter valid fields
    valid_fields, invalid_fields = filter_valid_fields(model, field_data, "create")
    
    if invalid_fields:
        logger.warning(
            f"Ignoring invalid fields for {model_name}: {invalid_fields}"
        )
    
    # Auto-assign ownership
    ownership_field = get_ownership_field(model)
    if ownership_field and user_id and ownership_field not in valid_fields:
        valid_fields[ownership_field] = user_id
    
    try:
        from database import get_db
        
        db = next(get_db())
        try:
            instance = model(**valid_fields)
            db.add(instance)
            db.commit()
            db.refresh(instance)
            
            # Serialize created record
            result_data = {}
            for col in model.__table__.columns:
                value = getattr(instance, col.name)
                if hasattr(value, "isoformat"):
                    value = value.isoformat()
                result_data[col.name] = value
            
            return ActionResult(
                success=True,
                message=f"Created {model_name} successfully",
                data=result_data,
            )
        
        except Exception as e:
            db.rollback()
            raise
        
        finally:
            db.close()
    
    except Exception as e:
        logger.error(f"Model create failed: {e}")
        return ActionResult(
            success=False,
            message=f"Create failed: {str(e)}",
            error="create_error",
        )


async def execute_model_update(
    params: Dict[str, Any],
    user_id: Optional[str] = None,
) -> ActionResult:
    """Execute a model update action.
    
    Args:
        params: Update parameters including model_name, id, and data
        user_id: ID of user executing
        
    Returns:
        ActionResult with updated record
    """
    model_name = params.get("model_name")
    record_id = params.get("id")
    field_data = params.get("data", {})
    
    if not model_name:
        return ActionResult(
            success=False,
            message="model_name is required",
            error="missing_parameter",
        )
    
    if record_id is None:
        return ActionResult(
            success=False,
            message="id is required for update",
            error="missing_parameter",
        )
    
    model = get_model_by_name(model_name)
    if model is None:
        return ActionResult(
            success=False,
            message=f"Model '{model_name}' not found",
            error="model_not_found",
        )
    
    # Filter valid fields
    valid_fields, invalid_fields = filter_valid_fields(model, field_data, "update")
    
    if invalid_fields:
        logger.warning(
            f"Ignoring invalid fields for {model_name}: {invalid_fields}"
        )
    
    if not valid_fields:
        return ActionResult(
            success=False,
            message="No valid fields to update",
            error="no_valid_fields",
        )
    
    try:
        from database import get_db
        
        db = next(get_db())
        try:
            instance = db.query(model).filter(model.id == record_id).first()
            
            if instance is None:
                return ActionResult(
                    success=False,
                    message=f"{model_name} with id {record_id} not found",
                    error="not_found",
                )
            
            # Update fields
            for field_name, value in valid_fields.items():
                setattr(instance, field_name, value)
            
            db.commit()
            db.refresh(instance)
            
            # Serialize updated record
            result_data = {}
            for col in model.__table__.columns:
                value = getattr(instance, col.name)
                if hasattr(value, "isoformat"):
                    value = value.isoformat()
                result_data[col.name] = value
            
            return ActionResult(
                success=True,
                message=f"Updated {model_name} successfully",
                data=result_data,
            )
        
        except Exception as e:
            db.rollback()
            raise
        
        finally:
            db.close()
    
    except Exception as e:
        logger.error(f"Model update failed: {e}")
        return ActionResult(
            success=False,
            message=f"Update failed: {str(e)}",
            error="update_error",
        )


async def execute_model_delete(
    params: Dict[str, Any],
    user_id: Optional[str] = None,
) -> ActionResult:
    """Execute a model delete action.
    
    Args:
        params: Delete parameters including model_name and id
        user_id: ID of user executing
        
    Returns:
        ActionResult indicating success
    """
    model_name = params.get("model_name")
    record_id = params.get("id")
    
    if not model_name:
        return ActionResult(
            success=False,
            message="model_name is required",
            error="missing_parameter",
        )
    
    if record_id is None:
        return ActionResult(
            success=False,
            message="id is required for delete",
            error="missing_parameter",
        )
    
    model = get_model_by_name(model_name)
    if model is None:
        return ActionResult(
            success=False,
            message=f"Model '{model_name}' not found",
            error="model_not_found",
        )
    
    try:
        from database import get_db
        
        db = next(get_db())
        try:
            instance = db.query(model).filter(model.id == record_id).first()
            
            if instance is None:
                return ActionResult(
                    success=False,
                    message=f"{model_name} with id {record_id} not found",
                    error="not_found",
                )
            
            db.delete(instance)
            db.commit()
            
            return ActionResult(
                success=True,
                message=f"Deleted {model_name} with id {record_id}",
            )
        
        except Exception as e:
            db.rollback()
            raise
        
        finally:
            db.close()
    
    except Exception as e:
        logger.error(f"Model delete failed: {e}")
        return ActionResult(
            success=False,
            message=f"Delete failed: {str(e)}",
            error="delete_error",
        )


def register_dynamic_actions() -> None:
    """Register dynamic CRUD actions for database models.
    
    Registers:
    - model_query: Search/filter any model
    - model_create: Create record in any model
    - model_update: Update record in any model
    - model_delete: Delete record in any model
    """
    registry = get_action_registry()
    
    # Get list of available models for description
    try:
        from database import Base
        model_names = [
            mapper.class_.__name__
            for mapper in Base.registry.mappers
            if not mapper.class_.__name__.startswith("_")
        ]
        model_list = ", ".join(model_names) if model_names else "Secret"
    except Exception:
        model_list = "Secret"
    
    # model_query action
    registry.register(ActionDefinition(
        name="model_query",
        display_name="Query Records",
        description=f"Search and filter records from any model. Available models: {model_list}",
        action_type=ActionType.QUERY,
        parameters={
            "type": "object",
            "properties": {
                "model_name": {
                    "type": "string",
                    "description": f"Name of the model to query. Options: {model_list}",
                },
                "filters": {
                    "type": "object",
                    "description": "Field filters to apply (field_name: value)",
                },
                "order_by": {
                    "type": "string",
                    "description": "Field to order by (prefix with - for descending)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 10)",
                    "default": 10,
                },
                "offset": {
                    "type": "integer",
                    "description": "Number of results to skip (default: 0)",
                    "default": 0,
                },
            },
            "required": ["model_name"],
        },
        execute_fn=execute_model_query,
        requires_confirmation=False,
        tags=["data", "query"],
    ))
    
    # model_create action
    registry.register(ActionDefinition(
        name="model_create",
        display_name="Create Record",
        description=f"Create a new record in any model. Available models: {model_list}",
        action_type=ActionType.CREATE,
        parameters={
            "type": "object",
            "properties": {
                "model_name": {
                    "type": "string",
                    "description": f"Name of the model. Options: {model_list}",
                },
                "data": {
                    "type": "object",
                    "description": "Field values for the new record",
                },
            },
            "required": ["model_name", "data"],
        },
        execute_fn=execute_model_create,
        requires_confirmation=True,
        tags=["data", "create"],
    ))
    
    # model_update action
    registry.register(ActionDefinition(
        name="model_update",
        display_name="Update Record",
        description=f"Update an existing record. Available models: {model_list}",
        action_type=ActionType.UPDATE,
        parameters={
            "type": "object",
            "properties": {
                "model_name": {
                    "type": "string",
                    "description": f"Name of the model. Options: {model_list}",
                },
                "id": {
                    "type": "integer",
                    "description": "ID of the record to update",
                },
                "data": {
                    "type": "object",
                    "description": "Field values to update",
                },
            },
            "required": ["model_name", "id", "data"],
        },
        execute_fn=execute_model_update,
        requires_confirmation=True,
        tags=["data", "update"],
    ))
    
    # model_delete action
    registry.register(ActionDefinition(
        name="model_delete",
        display_name="Delete Record",
        description=f"Delete a record. Available models: {model_list}",
        action_type=ActionType.DELETE,
        parameters={
            "type": "object",
            "properties": {
                "model_name": {
                    "type": "string",
                    "description": f"Name of the model. Options: {model_list}",
                },
                "id": {
                    "type": "integer",
                    "description": "ID of the record to delete",
                },
            },
            "required": ["model_name", "id"],
        },
        execute_fn=execute_model_delete,
        requires_confirmation=True,
        is_destructive=True,
        tags=["data", "delete"],
    ))
    
    logger.info("Registered dynamic CRUD actions")

