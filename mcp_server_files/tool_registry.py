"""Tool registration and discovery system for MCP Server.

Provides a central registry for all MCP tools with:
- Schema validation using Pydantic
- Tool discovery endpoint
- Execution routing
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type, Union

from pydantic import BaseModel


@dataclass
class ToolDefinition:
    """Definition of an MCP tool.
    
    Attributes:
        name: Unique tool identifier (e.g., "azure_cli.run")
        description: Human-readable description
        input_schema: Pydantic model for input validation
        output_schema: Pydantic model for output structure
        handler: Async function that executes the tool
        tags: Optional tags for categorization
    """
    name: str
    description: str
    input_schema: Type[BaseModel]
    output_schema: Type[BaseModel]
    handler: Callable
    tags: List[str] = field(default_factory=list)
    
    def to_manifest_dict(self) -> Dict[str, Any]:
        """Convert to manifest dictionary for API response.
        
        Returns:
            Dictionary with tool metadata and schemas
        """
        return {
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "parameters": self._schema_to_parameters(self.input_schema),
            "returns": self._schema_to_parameters(self.output_schema),
        }
    
    @staticmethod
    def _schema_to_parameters(schema: Type[BaseModel]) -> List[Dict[str, Any]]:
        """Convert Pydantic schema to parameter list.
        
        Args:
            schema: Pydantic model class
            
        Returns:
            List of parameter definitions
        """
        parameters = []
        json_schema = schema.model_json_schema()
        properties = json_schema.get("properties", {})
        required = json_schema.get("required", [])
        
        for name, prop in properties.items():
            param = {
                "name": name,
                "type": prop.get("type", "string"),
                "description": prop.get("description", ""),
                "required": name in required,
            }
            
            # Add default if present
            if "default" in prop:
                param["default"] = prop["default"]
            
            # Add enum values if present
            if "enum" in prop:
                param["enum"] = prop["enum"]
            
            parameters.append(param)
        
        return parameters


class ToolRegistry:
    """Central registry for MCP tools.
    
    Manages tool registration, discovery, and execution.
    Thread-safe for concurrent access.
    """
    
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._lock = asyncio.Lock()
    
    def register(
        self,
        name: str,
        description: str,
        input_schema: Type[BaseModel],
        output_schema: Type[BaseModel],
        handler: Callable,
        tags: Optional[List[str]] = None
    ) -> None:
        """Register a new tool.
        
        Args:
            name: Unique tool identifier
            description: Human-readable description
            input_schema: Pydantic model for input validation
            output_schema: Pydantic model for output structure
            handler: Async function that executes the tool
            tags: Optional tags for categorization
            
        Raises:
            ValueError: If tool with same name already exists
        """
        if name in self._tools:
            raise ValueError(f"Tool '{name}' is already registered")
        
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
            handler=handler,
            tags=tags or []
        )
    
    def get(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool by name.
        
        Args:
            name: Tool identifier
            
        Returns:
            ToolDefinition if found, None otherwise
        """
        return self._tools.get(name)
    
    def list_tools(self) -> List[ToolDefinition]:
        """Get all registered tools.
        
        Returns:
            List of all tool definitions
        """
        return list(self._tools.values())
    
    def get_manifest(self) -> List[Dict[str, Any]]:
        """Get tool manifest for API response.
        
        Returns:
            List of tool metadata dictionaries
        """
        return [tool.to_manifest_dict() for tool in self._tools.values()]
    
    async def execute(
        self,
        name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a tool with the given parameters.
        
        Args:
            name: Tool identifier
            parameters: Input parameters
            
        Returns:
            Tool execution result
            
        Raises:
            ValueError: If tool not found
            ValidationError: If parameters invalid
        """
        tool = self.get(name)
        if tool is None:
            raise ValueError(f"Tool '{name}' not found")
        
        # Validate input
        validated_input = tool.input_schema(**parameters)
        
        # Execute handler
        if asyncio.iscoroutinefunction(tool.handler):
            result = await tool.handler(validated_input)
        else:
            result = tool.handler(validated_input)
        
        # Validate and return output
        if isinstance(result, BaseModel):
            return result.model_dump()
        elif isinstance(result, dict):
            validated_output = tool.output_schema(**result)
            return validated_output.model_dump()
        else:
            return result


# Global registry instance
_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """Get the global tool registry.
    
    Creates the instance on first call.
    
    Returns:
        Global ToolRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def tool(
    name: str,
    description: str,
    input_schema: Type[BaseModel],
    output_schema: Type[BaseModel],
    tags: Optional[List[str]] = None
) -> Callable:
    """Decorator to register a function as an MCP tool.
    
    Args:
        name: Unique tool identifier
        description: Human-readable description
        input_schema: Pydantic model for input validation
        output_schema: Pydantic model for output structure
        tags: Optional tags for categorization
        
    Returns:
        Decorator function
        
    Example:
        @tool(
            name="azure_cli.run",
            description="Execute Azure CLI command",
            input_schema=AzureCliInput,
            output_schema=AzureCliOutput,
            tags=["azure", "cli"]
        )
        async def run_azure_cli(params: AzureCliInput) -> AzureCliOutput:
            ...
    """
    def decorator(func: Callable) -> Callable:
        get_registry().register(
            name=name,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
            handler=func,
            tags=tags
        )
        return func
    return decorator

