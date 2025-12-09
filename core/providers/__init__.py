"""LLM Provider abstraction layer.

Supports:
- OpenAI (standard API)
- Azure OpenAI (for production)
- Mock provider (for testing)
"""

import os
from typing import Optional

from .base import BaseProvider, ProviderResponse, ToolCall
from .openai import OpenAIProvider
from .azure_openai import AzureOpenAIProvider
from .mock import MockProvider


def get_provider() -> BaseProvider:
    """Get the appropriate LLM provider based on configuration.
    
    Checks in order:
    1. OPENAI_API_KEY (standard OpenAI)
    2. Azure OpenAI configuration
    3. Falls back to MockProvider
    
    Returns:
        Configured provider instance
    """
    # Check for standard OpenAI first
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai_key:
        return OpenAIProvider()
    
    # Check for Azure OpenAI
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

