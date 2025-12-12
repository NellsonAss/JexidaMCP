"""Tool executor that routes tool calls to implementations.

This module provides the execute_tool function that:
1. Looks up the Tool by name from the database
2. Dynamically imports the handler function
3. Executes it with the given parameters
4. Logs the execution to ExecutionLog
"""

import asyncio
import importlib
import inspect
import json
import logging
import time
from typing import Any, Dict, get_type_hints

from asgiref.sync import sync_to_async
from django.utils import timezone

logger = logging.getLogger(__name__)


def prepare_handler_input(handler, arguments: Dict[str, Any]) -> Any:
    """Convert dict arguments to the appropriate input type for the handler.
    
    If the handler expects a Pydantic model as its first parameter,
    construct it from the dict. Otherwise, return the dict as-is.
    """
    try:
        # Get type hints for the handler
        hints = get_type_hints(handler)
        
        # Get the signature to find the first parameter
        sig = inspect.signature(handler)
        params = list(sig.parameters.values())
        
        if not params:
            return arguments
        
        first_param = params[0]
        first_param_type = hints.get(first_param.name)
        
        # Check if it's a Pydantic model (has model_validate method)
        if first_param_type and hasattr(first_param_type, "model_validate"):
            return first_param_type.model_validate(arguments)
        
        return arguments
        
    except Exception as e:
        logger.debug(f"Could not determine handler input type: {e}")
        return arguments


class ToolNotFoundError(Exception):
    """Raised when a tool is not found in the registry."""
    pass


class ToolExecutionError(Exception):
    """Raised when tool execution fails."""
    pass


def import_handler(handler_path: str):
    """Dynamically import a handler function from its path.
    
    Args:
        handler_path: Dot-separated path like 'mcp_tools_core.tools.azure.cli.azure_cli_run'
        
    Returns:
        The imported function
        
    Raises:
        ImportError: If the module or function cannot be imported
    """
    parts = handler_path.rsplit(".", 1)
    if len(parts) != 2:
        raise ImportError(f"Invalid handler path: {handler_path}")
    
    module_path, function_name = parts
    module = importlib.import_module(module_path)
    return getattr(module, function_name)


async def execute_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool by name with the given arguments.
    
    This function:
    1. Looks up the tool in the database
    2. Imports the handler function
    3. Executes it
    4. Logs the execution
    5. Updates tool statistics
    
    Args:
        name: Tool name
        arguments: Tool arguments/parameters
        
    Returns:
        Tool execution result as a dictionary
        
    Raises:
        ToolNotFoundError: If tool doesn't exist or is inactive
        ToolExecutionError: If execution fails
    """
    # Import models here to avoid circular imports
    from .models import Tool, ExecutionLog
    
    start_time = time.perf_counter()
    
    # Look up the tool (using sync_to_async for ORM call)
    @sync_to_async
    def get_tool():
        return Tool.objects.get(name=name, is_active=True)
    
    try:
        tool = await get_tool()
    except Tool.DoesNotExist:
        raise ToolNotFoundError(f"Tool '{name}' not found or is inactive")
    
    logger.info(f"Executing tool: {name} with arguments: {arguments}")
    
    # Import and execute the handler
    try:
        handler = import_handler(tool.handler_path)
        
        # Convert dict to Pydantic model if handler expects it
        prepared_input = prepare_handler_input(handler, arguments)
        
        # Execute the handler - check if it's async or sync
        if inspect.iscoroutinefunction(handler):
            result = await handler(prepared_input)
        elif callable(handler):
            # Wrap sync handler in sync_to_async
            result = await sync_to_async(handler)(prepared_input)
        else:
            result = handler
        
        # Handle Pydantic model results
        if hasattr(result, "model_dump"):
            result_dict = result.model_dump()
        elif isinstance(result, dict):
            result_dict = result
        else:
            result_dict = {"result": str(result)}
        
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        
        # Log successful execution (using sync_to_async for ORM calls)
        @sync_to_async
        def log_success():
            ExecutionLog.objects.create(
                tool=tool,
                parameters=arguments,
                result=json.dumps(result_dict, default=str)[:10000],  # Truncate large results
                success=True,
                duration_ms=duration_ms,
            )
            # Update tool statistics
            tool.last_run = timezone.now()
            tool.run_count += 1
            tool.save(update_fields=["last_run", "run_count"])
        
        await log_success()
        
        logger.info(f"Tool {name} executed successfully in {duration_ms}ms")
        
        return result_dict
        
    except Exception as e:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        error_msg = str(e)
        
        # Log failed execution (using sync_to_async for ORM call)
        @sync_to_async
        def log_failure():
            ExecutionLog.objects.create(
                tool=tool,
                parameters=arguments,
                result="",
                success=False,
                duration_ms=duration_ms,
                error_message=error_msg,
            )
        
        await log_failure()
        
        logger.error(f"Tool {name} failed after {duration_ms}ms: {error_msg}")
        raise ToolExecutionError(f"Tool execution failed: {error_msg}") from e


async def execute_tool_by_handler(handler_path: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool directly by its handler path (for tools not yet in database).
    
    This is useful during development when adding new tools that aren't
    yet registered in the database.
    
    Args:
        handler_path: Full import path to the handler function
        arguments: Tool arguments
        
    Returns:
        Tool execution result
    """
    logger.info(f"Executing handler: {handler_path}")
    
    try:
        handler = import_handler(handler_path)
        
        # Convert dict to Pydantic model if handler expects it
        prepared_input = prepare_handler_input(handler, arguments)
        
        # Execute the handler - check if it's async or sync
        if inspect.iscoroutinefunction(handler):
            result = await handler(prepared_input)
        elif callable(handler):
            result = await sync_to_async(handler)(prepared_input)
        else:
            result = handler
        
        if hasattr(result, "model_dump"):
            return result.model_dump()
        elif isinstance(result, dict):
            return result
        else:
            return {"result": str(result)}
            
    except Exception as e:
        logger.error(f"Handler {handler_path} failed: {e}")
        raise ToolExecutionError(f"Handler execution failed: {e}") from e


def get_tool_schema(name: str) -> Dict[str, Any]:
    """Get the input schema for a tool.
    
    Args:
        name: Tool name
        
    Returns:
        JSON Schema for the tool's input
    """
    from .models import Tool
    
    try:
        tool = Tool.objects.get(name=name, is_active=True)
        return tool.input_schema
    except Tool.DoesNotExist:
        raise ToolNotFoundError(f"Tool '{name}' not found")


def list_active_tools() -> list:
    """List all active tools.
    
    Returns:
        List of tool dictionaries with name, description, and schema
    """
    from .models import Tool
    
    tools = Tool.objects.filter(is_active=True).order_by("name")
    return [
        {
            "name": t.name,
            "description": t.description,
            "tags": t.get_tags_list(),
            "input_schema": t.input_schema,
        }
        for t in tools
    ]

