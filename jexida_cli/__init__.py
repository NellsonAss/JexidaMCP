"""Jexida Agent CLI - A terminal agent for remote MCP server interaction.

A clean, modular CLI for:
- Interacting with MCP server tools
- Managing AI models and strategies
- Executing SSH commands
- Chatting with LLM agents

Usage:
    jexida

Commands:
    /help       Show help
    /model      Manage models
    /cmd        Run remote commands
    /shell      Open SSH shell
    /routines   View/run routines
"""

__version__ = "0.2.0"

from .main import main
from .state.config import Config
from .state.session import Session
from .ui.renderer import Renderer
from .mcp_client import MCPClient
from .ssh_client import SSHClient
from .agent import Agent

__all__ = [
    "main",
    "Config",
    "Session",
    "Renderer",
    "MCPClient",
    "SSHClient",
    "Agent",
]
