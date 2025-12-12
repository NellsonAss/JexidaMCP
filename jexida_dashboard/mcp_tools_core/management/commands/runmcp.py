"""MCP Server management command for Cursor integration.

This command starts an MCP-protocol-compliant server using stdio transport.
Cursor and other MCP clients can connect to this server to use the registered tools.

Usage:
    python manage.py runmcp

Cursor configuration (.cursor/mcp.json):
    {
      "mcpServers": {
        "jexida-mcp": {
          "command": "python",
          "args": ["path/to/jexida_dashboard/manage.py", "runmcp"]
        }
      }
    }

IMPORTANT: All logging MUST go to stderr, not stdout!
The MCP protocol uses stdout for JSON-RPC communication.
"""

import asyncio
import json
import logging
import sys
from typing import Any

from django.core.management.base import BaseCommand

# Configure logging to stderr BEFORE any other imports
def setup_mcp_logging(level: str = "WARNING") -> None:
    """Configure logging for MCP server - all output to stderr."""
    numeric_level = getattr(logging, level.upper(), logging.WARNING)
    
    # Create handler that writes to stderr ONLY
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(numeric_level)
    root_logger.addHandler(handler)
    
    # Quiet down noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("django").setLevel(logging.WARNING)


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Django management command to run the MCP server."""
    
    help = "Run the MCP server for Cursor integration (stdio transport)"
    
    def add_arguments(self, parser):
        parser.add_argument(
            "--log-level",
            type=str,
            default="WARNING",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            help="Logging level (default: WARNING)",
        )
    
    def handle(self, *args, **options):
        """Handle the command execution."""
        # Set up logging first
        setup_mcp_logging(options["log_level"])
        
        logger.info("Starting Jexida MCP Server (Django)")
        
        # Run the async MCP server
        try:
            asyncio.run(self.run_mcp_server())
        except KeyboardInterrupt:
            logger.info("MCP Server stopped by user")
        except Exception as e:
            logger.error(f"MCP Server error: {e}")
            sys.exit(1)
    
    async def run_mcp_server(self):
        """Run the MCP server using stdio transport."""
        try:
            from mcp.server import Server
            from mcp.server.stdio import stdio_server
            from mcp.types import Tool as MCPTool, TextContent
        except ImportError:
            logger.error(
                "MCP library not installed. Install it with: pip install mcp"
            )
            sys.exit(1)
        
        from mcp_tools_core.models import Tool, ToolRequest
        from mcp_tools_core.executor import execute_tool, ToolNotFoundError
        
        # Create the MCP server instance
        mcp = Server("jexida-mcp")
        
        @mcp.list_tools()
        async def list_tools() -> list[MCPTool]:
            """Return the list of available tools from the database."""
            tools = Tool.objects.filter(is_active=True)
            return [
                MCPTool(
                    name=t.name,
                    description=t.description,
                    inputSchema=t.input_schema,
                )
                for t in tools
            ]
        
        @mcp.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            """Execute a tool and return the result."""
            logger.info(f"Tool call: {name}")
            
            try:
                result = await execute_tool(name, arguments)
                
                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, default=str),
                )]
                
            except ToolNotFoundError as e:
                # Log a tool request for missing tools
                logger.warning(f"Tool not found: {name}")
                
                # Create a ToolRequest for this missing tool
                ToolRequest.objects.create(
                    prompt=f"Tool '{name}' was requested but not found",
                    suggested_name=name,
                    suggested_description=f"Automatically logged: tool '{name}' was requested with arguments: {arguments}",
                    suggested_schema={"type": "object", "properties": {}},
                )
                
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": str(e),
                        "suggestion": f"Tool '{name}' is not available. A request has been logged.",
                    }, indent=2),
                )]
                
            except Exception as e:
                logger.error(f"Tool execution failed: {name} - {e}")
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": str(e),
                    }, indent=2),
                )]
        
        # Run the server
        logger.info("MCP Server ready, waiting for connections...")
        
        async with stdio_server() as (read_stream, write_stream):
            await mcp.run(
                read_stream,
                write_stream,
                mcp.create_initialization_options(),
            )

