"""Model introspection utilities for generating AI function schemas.

Provides automatic schema generation from SQLAlchemy models and Pydantic schemas
for use with LLM function calling.
"""

import sys
import os
from datetime import datetime, date, time
from decimal import Decimal
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Tuple, Type, Union, get_args, get_origin
)

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from logging_config import get_logger

logger = get_logger(__name__)

# Type mapping for SQLAlchemy column types to JSON Schema types
SQLALCHEMY_TYPE_MAP = {
    "String": "string",
    "Text": "string",
    "Unicode": "string",
    "UnicodeText": "string",
    "Integer": "integer",
    "SmallInteger": "integer",
    "BigInteger": "integer",
    "Float": "number",
    "Numeric": "number",
    "Boolean": "boolean",
    "Date": "string",
    "DateTime": "string",
    "Time": "string",
    "LargeBinary": "string",
    "JSON": "object",
    "ARRAY": "array",
}

# Python type mapping for Pydantic models
PYTHON_TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    bytes: "string",
    datetime: "string",
    date: "string",
    time: "string",
    Decimal: "number",
    dict: "object",
    list: "array",
    type(None): "null",
}


def get_json_schema_type(python_type: Type) -> Dict[str, Any]:
    """Convert a Python type to JSON Schema format.
    
    Args:
        python_type: Python type annotation
        
    Returns:
        JSON Schema type definition
    """
    # Handle None type
    if python_type is type(None):
        return {"type": "null"}
    
    # Handle Optional types
    origin = get_origin(python_type)
    args = get_args(python_type)
    
    if origin is Union:
        # Check if it's Optional (Union with None)
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            # Optional[X] -> X with nullable
            schema = get_json_schema_type(non_none_args[0])
            return schema
        else:
            # Union of multiple types
            return {
                "oneOf": [get_json_schema_type(a) for a in args]
            }
    
    # Handle List types
    if origin is list or origin is List:
        item_type = args[0] if args else Any
        return {
            "type": "array",
            "items": get_json_schema_type(item_type)
        }
    
    # Handle Dict types
    if origin is dict or origin is Dict:
        return {"type": "object"}
    
    # Handle Enum types
    if isinstance(python_type, type) and issubclass(python_type, Enum):
        return {
            "type": "string",
            "enum": [e.value for e in python_type]
        }
    
    # Handle basic types
    if python_type in PYTHON_TYPE_MAP:
        schema_type = PYTHON_TYPE_MAP[python_type]
        schema: Dict[str, Any] = {"type": schema_type}
        
        # Add format for date/time types
        if python_type is datetime:
            schema["format"] = "date-time"
        elif python_type is date:
            schema["format"] = "date"
        elif python_type is time:
            schema["format"] = "time"
        
        return schema
    
    # Default to string for unknown types
    return {"type": "string"}


def get_sqlalchemy_field_schema(column) -> Tuple[Dict[str, Any], bool]:
    """Convert a SQLAlchemy column to JSON Schema format.
    
    Args:
        column: SQLAlchemy Column object
        
    Returns:
        Tuple of (schema_dict, is_required)
    """
    # Get the column type name
    type_name = column.type.__class__.__name__
    
    # Map to JSON Schema type
    json_type = SQLALCHEMY_TYPE_MAP.get(type_name, "string")
    
    schema: Dict[str, Any] = {"type": json_type}
    
    # Add format for specific types
    if type_name == "DateTime":
        schema["format"] = "date-time"
    elif type_name == "Date":
        schema["format"] = "date"
    elif type_name == "Time":
        schema["format"] = "time"
    
    # Add description from column doc or comment
    if hasattr(column, "doc") and column.doc:
        schema["description"] = column.doc
    elif hasattr(column, "comment") and column.comment:
        schema["description"] = column.comment
    
    # Add string length constraint
    if type_name in ("String", "Unicode") and hasattr(column.type, "length"):
        if column.type.length:
            schema["maxLength"] = column.type.length
    
    # Add enum values if applicable
    if hasattr(column.type, "enums"):
        schema["enum"] = list(column.type.enums)
    
    # Determine if required
    is_required = not column.nullable and column.default is None and not column.autoincrement
    
    return schema, is_required


def generate_model_schema(
    model: Type,
    operation: str = "create",
    exclude_fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Generate JSON Schema from a SQLAlchemy model.
    
    Args:
        model: SQLAlchemy model class
        operation: Operation type ('create', 'update', 'query')
        exclude_fields: List of field names to exclude
        
    Returns:
        JSON Schema dictionary
    """
    exclude_fields = exclude_fields or []
    
    # Auto-exclude fields based on operation
    auto_exclude = {"id", "created_at", "updated_at", "created_by", "updated_by"}
    if operation == "create":
        exclude_fields = list(set(exclude_fields) | auto_exclude)
    elif operation == "update":
        # For update, we typically need the ID
        exclude_fields = list(set(exclude_fields) | (auto_exclude - {"id"}))
    
    properties: Dict[str, Any] = {}
    required: List[str] = []
    
    try:
        from sqlalchemy import inspect
        
        mapper = inspect(model)
        
        # Get columns
        for column in mapper.columns:
            column_name = column.name
            
            if column_name in exclude_fields:
                continue
            
            schema, is_required = get_sqlalchemy_field_schema(column)
            properties[column_name] = schema
            
            # For create/update operations, determine required fields
            if operation in ("create", "update") and is_required:
                # For update, no fields are strictly required
                if operation == "create":
                    required.append(column_name)
        
        # Get relationships (as foreign key IDs)
        for rel in mapper.relationships:
            # Only include the local foreign key columns
            for local_col in rel.local_columns:
                col_name = local_col.name
                if col_name not in properties and col_name not in exclude_fields:
                    schema, is_required = get_sqlalchemy_field_schema(local_col)
                    # Mark relationship fields with a hint
                    schema["description"] = (
                        schema.get("description", "") +
                        f" (Reference to {rel.mapper.class_.__name__})"
                    ).strip()
                    properties[col_name] = schema
                    
                    if operation == "create" and is_required:
                        required.append(col_name)
    
    except Exception as e:
        logger.warning(
            f"Failed to inspect model {model.__name__}: {e}",
            extra={"model": model.__name__, "error": str(e)}
        )
        return {"type": "object", "properties": {}}
    
    return {
        "type": "object",
        "properties": properties,
        "required": required if required else None,
    }


def generate_pydantic_function_schema(
    model: Type,
    operation: str = "create",
) -> Dict[str, Any]:
    """Generate function schema from a Pydantic model.
    
    Args:
        model: Pydantic model class
        operation: Operation type (used for description)
        
    Returns:
        JSON Schema dictionary suitable for function calling
    """
    try:
        # Use Pydantic's built-in schema generation
        schema = model.model_json_schema()
        
        # Clean up the schema for function calling
        if "$defs" in schema:
            # Inline definitions for simpler schema
            defs = schema.pop("$defs")
            schema = _inline_refs(schema, defs)
        
        return {
            "type": "object",
            "properties": schema.get("properties", {}),
            "required": schema.get("required", []),
        }
    
    except Exception as e:
        logger.warning(
            f"Failed to generate schema for Pydantic model: {e}",
            extra={"error": str(e)}
        )
        return {"type": "object", "properties": {}}


def _inline_refs(schema: Dict[str, Any], defs: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively inline $ref references in a schema.
    
    Args:
        schema: Schema with potential $refs
        defs: Definitions to inline
        
    Returns:
        Schema with inlined definitions
    """
    if isinstance(schema, dict):
        if "$ref" in schema:
            ref_name = schema["$ref"].split("/")[-1]
            if ref_name in defs:
                return _inline_refs(defs[ref_name], defs)
        
        return {
            k: _inline_refs(v, defs)
            for k, v in schema.items()
        }
    
    elif isinstance(schema, list):
        return [_inline_refs(item, defs) for item in schema]
    
    return schema


def get_model_description(model: Type) -> str:
    """Get a description for a model.
    
    Args:
        model: Model class
        
    Returns:
        Description string
    """
    if model.__doc__:
        return model.__doc__.strip().split("\n")[0]
    return f"Operations on {model.__name__}"


def get_accessible_models() -> List[Type]:
    """Get all models that can be accessed via AI.
    
    This function should be customized based on your application's
    model registration system.
    
    Returns:
        List of accessible model classes
    """
    # Import your database models here
    try:
        from database import Base
        from sqlalchemy import inspect
        
        models = []
        for mapper in Base.registry.mappers:
            model_class = mapper.class_
            # Filter out system/internal models
            if not model_class.__name__.startswith("_"):
                models.append(model_class)
        
        return models
    
    except Exception as e:
        logger.warning(f"Failed to get accessible models: {e}")
        return []


def generate_model_query_schema(
    model: Type,
    searchable_fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Generate a query schema for filtering a model.
    
    Args:
        model: Model class
        searchable_fields: List of fields that can be searched
        
    Returns:
        JSON Schema for query parameters
    """
    full_schema = generate_model_schema(model, operation="query")
    properties = full_schema.get("properties", {})
    
    # Filter to searchable fields if specified
    if searchable_fields:
        properties = {
            k: v for k, v in properties.items()
            if k in searchable_fields
        }
    
    # Add common query parameters
    query_properties = {
        "filters": {
            "type": "object",
            "description": "Field filters to apply",
            "properties": properties,
        },
        "order_by": {
            "type": "string",
            "description": "Field to order by (prefix with - for descending)",
        },
        "limit": {
            "type": "integer",
            "description": "Maximum number of results",
            "default": 10,
            "minimum": 1,
            "maximum": 100,
        },
        "offset": {
            "type": "integer",
            "description": "Number of results to skip",
            "default": 0,
            "minimum": 0,
        },
    }
    
    return {
        "type": "object",
        "properties": query_properties,
    }

