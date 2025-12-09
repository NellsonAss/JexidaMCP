"""Logging utilities for core package.

Provides a simple logging interface that works with any framework.
"""

import logging
from typing import Optional


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def setup_logging(level: str = "INFO") -> None:
    """Configure basic logging for the core package.
    
    This is a fallback; the web framework should configure logging.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

