"""Structured JSON logging configuration for MCP Server.

Provides consistent, structured logging across all components.
Secrets are never included in log output.
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pythonjsonlogger import jsonlogger


class MCPJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for MCP Server logs.
    
    Adds standard fields and ensures consistent formatting.
    """
    
    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any]
    ) -> None:
        """Add custom fields to log record."""
        super().add_fields(log_record, record, message_dict)
        
        # Add timestamp in ISO format
        log_record["timestamp"] = datetime.now(timezone.utc).isoformat()
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        
        # Add source location for debugging
        log_record["source"] = {
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName,
        }


def setup_logging(level: str = "INFO", use_stderr: bool = False) -> None:
    """Configure structured JSON logging for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        use_stderr: If True, log to stderr instead of stdout (for MCP servers)
    """
    # Get numeric level
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create handler with JSON formatter
    # Use stderr for MCP servers (stdout is used for protocol messages)
    stream = sys.stderr if use_stderr else sys.stdout
    handler = logging.StreamHandler(stream)
    handler.setFormatter(MCPJsonFormatter(
        fmt="%(timestamp)s %(level)s %(name)s %(message)s"
    ))
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.handlers = [handler]
    
    # Set levels for noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class ToolInvocationLogger:
    """Helper for logging tool invocations with consistent structure.
    
    Ensures all tool calls are logged with:
    - Tool name
    - Subscription ID (if applicable)
    - Duration
    - Success/failure status
    
    Never logs full stdout/stderr which may contain secrets.
    """
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self._start_time: Optional[datetime] = None
        self._tool_name: Optional[str] = None
        self._context: Dict[str, Any] = {}
    
    def start(self, tool_name: str, **context) -> "ToolInvocationLogger":
        """Start timing a tool invocation.
        
        Args:
            tool_name: Name of the tool being invoked
            **context: Additional context (subscription_id, etc.)
            
        Returns:
            Self for chaining
        """
        self._start_time = datetime.now(timezone.utc)
        self._tool_name = tool_name
        self._context = context
        
        self.logger.info(
            "Tool invocation started",
            extra={
                "tool_name": tool_name,
                "event": "tool_start",
                **{k: v for k, v in context.items() if not self._is_sensitive(k)}
            }
        )
        return self
    
    def success(self, **result_info) -> None:
        """Log successful tool completion.
        
        Args:
            **result_info: Non-sensitive result information (exit_code, etc.)
        """
        duration_ms = self._calculate_duration()
        
        self.logger.info(
            "Tool invocation succeeded",
            extra={
                "tool_name": self._tool_name,
                "event": "tool_success",
                "duration_ms": duration_ms,
                **{k: v for k, v in self._context.items() if not self._is_sensitive(k)},
                **{k: v for k, v in result_info.items() if not self._is_sensitive(k)}
            }
        )
    
    def failure(self, error: str, **result_info) -> None:
        """Log failed tool completion.
        
        Args:
            error: Error message (sanitized, no secrets)
            **result_info: Non-sensitive result information
        """
        duration_ms = self._calculate_duration()
        
        self.logger.error(
            "Tool invocation failed",
            extra={
                "tool_name": self._tool_name,
                "event": "tool_failure",
                "duration_ms": duration_ms,
                "error": error,
                **{k: v for k, v in self._context.items() if not self._is_sensitive(k)},
                **{k: v for k, v in result_info.items() if not self._is_sensitive(k)}
            }
        )
    
    def _calculate_duration(self) -> int:
        """Calculate duration in milliseconds."""
        if self._start_time is None:
            return 0
        delta = datetime.now(timezone.utc) - self._start_time
        return int(delta.total_seconds() * 1000)
    
    @staticmethod
    def _is_sensitive(key: str) -> bool:
        """Check if a key might contain sensitive data."""
        sensitive_patterns = [
            "secret", "password", "token", "key", "credential",
            "stdout", "stderr", "output", "response_body"
        ]
        key_lower = key.lower()
        return any(pattern in key_lower for pattern in sensitive_patterns)

