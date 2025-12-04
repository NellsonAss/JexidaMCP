"""Main entry point for MCP Server.

Starts the uvicorn server with configured settings.
Imports tools to trigger registration.
"""

import uvicorn

from config import get_settings
from logging_config import get_logger, setup_logging

# Import tools to register them
import mcp_tools.azure  # noqa: F401
import mcp_tools.unifi  # noqa: F401

from server import app

logger = get_logger(__name__)


def main() -> None:
    """Start the MCP server."""
    settings = get_settings()
    setup_logging(settings.mcp_log_level)
    
    logger.info(
        "Starting MCP Server",
        extra={
            "host": settings.mcp_server_host,
            "port": settings.mcp_server_port,
            "config": settings.get_safe_dict()
        }
    )
    
    uvicorn.run(
        app,
        host=settings.mcp_server_host,
        port=settings.mcp_server_port,
        log_level=settings.mcp_log_level.lower(),
    )


if __name__ == "__main__":
    main()

