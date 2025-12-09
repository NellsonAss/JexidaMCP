"""Schema-driven parameter validation for actions.

Provides utilities to:
- Extract required fields from JSON Schema or Pydantic models
- Validate parameters before confirmation is requested
- Return structured errors for missing/invalid fields
"""

import sys
import os
from typing import Any, Dict, List, Optional, Set, Tuple, Type, Union

from pydantic import BaseModel, ValidationError

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from logging_config import get_logger

logger = get_logger(__name__)


class ValidationResult:
    """Result of parameter validation.
    
    Attributes:
        is_valid: Whether all required fields are present and valid
        missing_fields: List of missing required field names
        invalid_fields: Dict mapping field names to error descriptions
        validated_data: Validated/coerced data if valid
    """
    
    def __init__(
        self,
        is_valid: bool = True,
        missing_fields: Optional[List[str]] = None,
        invalid_fields: Optional[Dict[str, str]] = None,
        validated_data: Optional[Dict[str, Any]] = None,
    ):
        self.is_valid = is_valid
        self.missing_fields = missing_fields or []
        self.invalid_fields = invalid_fields or {}
        self.validated_data = validated_data or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "is_valid": self.is_valid,
            "missing_fields": self.missing_fields,
            "invalid_fields": self.invalid_fields,
        }
    
    def get_error_message(self) -> str:
        """Generate a human-readable error message."""
        parts = []
        
        if self.missing_fields:
            fields_str = ", ".join(f"`{f}`" for f in self.missing_fields)
            parts.append(f"Missing required fields: {fields_str}")
        
        if self.invalid_fields:
            invalid_parts = [
                f"`{field}`: {error}" 
                for field, error in self.invalid_fields.items()
            ]
            parts.append("Invalid fields: " + "; ".join(invalid_parts))
        
        return ". ".join(parts) if parts else "Validation passed"


def get_required_fields_from_json_schema(schema: Dict[str, Any]) -> Set[str]:
    """Extract required field names from a JSON Schema.
    
    Args:
        schema: JSON Schema dictionary
        
    Returns:
        Set of required field names
    """
    required = set(schema.get("required", []))
    
    # Also check properties for fields that have no default
    properties = schema.get("properties", {})
    for field_name, field_def in properties.items():
        # If field has no default and isn't marked explicitly optional,
        # it might be required depending on schema style
        pass  # The 'required' array is the authoritative source
    
    return required


def get_required_fields_from_pydantic(model: Type[BaseModel]) -> Set[str]:
    """Extract required field names from a Pydantic model.
    
    Supports both Pydantic v1 and v2.
    
    Args:
        model: Pydantic model class
        
    Returns:
        Set of required field names
    """
    required = set()
    
    # Try Pydantic v2 first
    if hasattr(model, "model_fields"):
        for field_name, field_info in model.model_fields.items():
            # In Pydantic v2, is_required() method or check default
            if hasattr(field_info, "is_required"):
                if field_info.is_required():
                    required.add(field_name)
            else:
                # Check if field has a default value
                # PydanticUndefined means no default = required
                from pydantic_core import PydanticUndefined
                if field_info.default is PydanticUndefined and field_info.default_factory is None:
                    required.add(field_name)
    
    # Fallback to Pydantic v1 style
    elif hasattr(model, "__fields__"):
        for field_name, field in model.__fields__.items():
            if field.required:
                required.add(field_name)
    
    # Alternative: use JSON schema
    else:
        try:
            json_schema = model.model_json_schema()
            required = get_required_fields_from_json_schema(json_schema)
        except Exception as e:
            logger.warning(f"Could not extract required fields from Pydantic model: {e}")
    
    return required


def validate_against_json_schema(
    parameters: Dict[str, Any],
    schema: Dict[str, Any],
) -> ValidationResult:
    """Validate parameters against a JSON Schema.
    
    Args:
        parameters: Input parameters dict
        schema: JSON Schema dict
        
    Returns:
        ValidationResult with validation outcome
    """
    required_fields = get_required_fields_from_json_schema(schema)
    properties = schema.get("properties", {})
    
    missing_fields = []
    invalid_fields = {}
    
    # Check for missing required fields
    for field_name in required_fields:
        value = parameters.get(field_name)
        if value is None or (isinstance(value, str) and value.strip() == ""):
            missing_fields.append(field_name)
    
    # Basic type validation for provided fields
    for field_name, value in parameters.items():
        if field_name not in properties:
            continue  # Unknown field, skip
        
        field_def = properties[field_name]
        expected_type = field_def.get("type")
        
        if value is not None and expected_type:
            # Basic type checking
            type_valid = True
            if expected_type == "string" and not isinstance(value, str):
                type_valid = False
            elif expected_type == "integer" and not isinstance(value, int):
                type_valid = False
            elif expected_type == "number" and not isinstance(value, (int, float)):
                type_valid = False
            elif expected_type == "boolean" and not isinstance(value, bool):
                type_valid = False
            elif expected_type == "array" and not isinstance(value, list):
                type_valid = False
            elif expected_type == "object" and not isinstance(value, dict):
                type_valid = False
            
            if not type_valid:
                invalid_fields[field_name] = f"Expected {expected_type}, got {type(value).__name__}"
        
        # Check enum constraints
        if "enum" in field_def and value is not None:
            if value not in field_def["enum"]:
                invalid_fields[field_name] = f"Must be one of: {field_def['enum']}"
    
    is_valid = len(missing_fields) == 0 and len(invalid_fields) == 0
    
    return ValidationResult(
        is_valid=is_valid,
        missing_fields=missing_fields,
        invalid_fields=invalid_fields,
        validated_data=parameters if is_valid else None,
    )


def validate_against_pydantic(
    parameters: Dict[str, Any],
    model: Type[BaseModel],
) -> ValidationResult:
    """Validate parameters against a Pydantic model.
    
    Args:
        parameters: Input parameters dict
        model: Pydantic model class
        
    Returns:
        ValidationResult with validation outcome
    """
    try:
        # Try to construct the model - this validates everything
        validated = model(**parameters)
        
        return ValidationResult(
            is_valid=True,
            validated_data=validated.model_dump() if hasattr(validated, "model_dump") else validated.dict(),
        )
    
    except ValidationError as e:
        missing_fields = []
        invalid_fields = {}
        
        for error in e.errors():
            field_path = ".".join(str(loc) for loc in error["loc"])
            error_type = error["type"]
            error_msg = error.get("msg", str(error_type))
            
            # Identify missing vs invalid
            if error_type in ("missing", "value_error.missing"):
                missing_fields.append(field_path)
            else:
                invalid_fields[field_path] = error_msg
        
        return ValidationResult(
            is_valid=False,
            missing_fields=missing_fields,
            invalid_fields=invalid_fields,
        )
    
    except Exception as e:
        logger.error(f"Unexpected validation error: {e}")
        return ValidationResult(
            is_valid=False,
            invalid_fields={"_error": str(e)},
        )


def validate_parameters(
    parameters: Dict[str, Any],
    schema: Union[Dict[str, Any], Type[BaseModel], None],
) -> ValidationResult:
    """Validate parameters against a schema (JSON Schema or Pydantic).
    
    This is the main entry point for parameter validation.
    
    Args:
        parameters: Input parameters dict
        schema: JSON Schema dict or Pydantic model class
        
    Returns:
        ValidationResult with validation outcome
    """
    if schema is None:
        # No schema = no validation required
        return ValidationResult(is_valid=True, validated_data=parameters)
    
    # Check if it's a Pydantic model
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        return validate_against_pydantic(parameters, schema)
    
    # Assume it's a JSON Schema dict
    if isinstance(schema, dict):
        return validate_against_json_schema(parameters, schema)
    
    # Unknown schema type
    logger.warning(f"Unknown schema type: {type(schema)}")
    return ValidationResult(is_valid=True, validated_data=parameters)


def get_field_descriptions(
    schema: Union[Dict[str, Any], Type[BaseModel], None],
) -> Dict[str, str]:
    """Get field descriptions from a schema.
    
    Useful for generating helpful prompts about missing fields.
    
    Args:
        schema: JSON Schema dict or Pydantic model class
        
    Returns:
        Dict mapping field names to descriptions
    """
    descriptions = {}
    
    if schema is None:
        return descriptions
    
    # Handle Pydantic models
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        try:
            json_schema = schema.model_json_schema()
            properties = json_schema.get("properties", {})
            for field_name, field_def in properties.items():
                if "description" in field_def:
                    descriptions[field_name] = field_def["description"]
        except Exception:
            pass
        return descriptions
    
    # Handle JSON Schema dict
    if isinstance(schema, dict):
        properties = schema.get("properties", {})
        for field_name, field_def in properties.items():
            if isinstance(field_def, dict) and "description" in field_def:
                descriptions[field_name] = field_def["description"]
    
    return descriptions


def format_missing_fields_message(
    missing_fields: List[str],
    schema: Union[Dict[str, Any], Type[BaseModel], None],
) -> str:
    """Format a helpful message about missing fields.
    
    Args:
        missing_fields: List of missing field names
        schema: Schema for getting field descriptions
        
    Returns:
        Formatted message string
    """
    descriptions = get_field_descriptions(schema)
    
    parts = []
    for field in missing_fields:
        desc = descriptions.get(field)
        if desc:
            parts.append(f"- `{field}`: {desc}")
        else:
            parts.append(f"- `{field}`")
    
    return "The following required fields are missing:\n" + "\n".join(parts)

