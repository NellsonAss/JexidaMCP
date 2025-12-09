"""LLM Provider abstraction layer.

Supports:
- OpenAI (standard API - for development)
- Azure OpenAI (for production)
- Mock provider (for testing)
"""

from .base import BaseProvider, ProviderResponse, ToolCall
from .openai import OpenAIProvider
from .azure_openai import AzureOpenAIProvider
from .mock import MockProvider

from typing import Optional
import os
from pathlib import Path

# Load .env file to ensure environment variables are available
from dotenv import load_dotenv

# Load .env from the mcp_server_files directory (where the server runs)
# Use absolute path resolution to avoid issues when running from different directories
_env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(_env_path, override=True)
# Also try loading from current directory as fallback
load_dotenv(override=True)


def get_provider() -> BaseProvider:
    """Get the appropriate LLM provider based on configuration.
    
    Checks in order:
    1. OPENAI_API_KEY (standard OpenAI - for development)
    2. Azure OpenAI configuration (for production)
    3. Falls back to MockProvider
    
    Returns:
        Configured provider instance
    """
    # Check for standard OpenAI first (development)
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai_key:
        return OpenAIProvider()
    
    # Check for Azure OpenAI (production)
    azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip()
    azure_key = os.environ.get("AZURE_OPENAI_KEY", "").strip()
    if azure_endpoint and azure_key:
        return AzureOpenAIProvider()
    
    # Fall back to mock provider
    return MockProvider()


__all__ = [
    "BaseProvider",
    "ProviderResponse",
    "ToolCall",
    "OpenAIProvider",
    "AzureOpenAIProvider",
    "MockProvider",
    "get_provider",
]

