"""Azure OpenAI provider implementation.

Uses the Azure OpenAI Service.
"""

import json
import os
from typing import Any, Dict, List, Optional

from .base import BaseProvider, ProviderResponse, ToolCall
from ..logging import get_logger

logger = get_logger(__name__)


class AzureOpenAIProvider(BaseProvider):
    """Azure OpenAI Service provider.
    
    Uses the openai Python package with Azure configuration.
    Configured via environment variables:
    - AZURE_OPENAI_ENDPOINT: Azure OpenAI endpoint URL (required)
    - AZURE_OPENAI_KEY: Azure OpenAI API key (required)
    - AZURE_OPENAI_DEPLOYMENT: Deployment name (required)
    - AZURE_OPENAI_API_VERSION: API version (optional)
    """
    
    def __init__(self):
        """Initialize the Azure OpenAI provider."""
        self._endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        self._api_key = os.environ.get("AZURE_OPENAI_KEY")
        self._deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
        self._api_version = os.environ.get(
            "AZURE_OPENAI_API_VERSION",
            "2024-02-15-preview"
        )
        self._client = None
    
    def _get_client(self):
        """Get or create the Azure OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncAzureOpenAI
                
                self._client = AsyncAzureOpenAI(
                    azure_endpoint=self._endpoint,
                    api_key=self._api_key,
                    api_version=self._api_version,
                )
            except ImportError:
                raise RuntimeError(
                    "openai package not installed. "
                    "Install with: pip install openai"
                )
        return self._client
    
    @property
    def provider_name(self) -> str:
        """Get the provider name."""
        return "azure_openai"
    
    @property
    def default_model(self) -> str:
        """Get the default model (deployment name for Azure)."""
        return self._deployment
    
    def is_configured(self) -> bool:
        """Check if the provider is configured."""
        return bool(self._endpoint and self._api_key and self._deployment)
    
    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        functions: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        parallel_tool_calls: bool = True,
    ) -> ProviderResponse:
        """Send a chat completion request to Azure OpenAI.
        
        Args:
            messages: Chat messages
            model: Deployment name (defaults to AZURE_OPENAI_DEPLOYMENT)
            functions: Function definitions for tool calling
            temperature: Sampling temperature
            max_tokens: Maximum tokens in completion
            parallel_tool_calls: Allow parallel tool calls
            
        Returns:
            ProviderResponse with content and/or tool calls
        """
        client = self._get_client()
        deployment = model or self._deployment
        
        params: Dict[str, Any] = {
            "model": deployment,
            "messages": messages,
            "temperature": temperature,
        }
        
        if max_tokens:
            params["max_tokens"] = max_tokens
        
        if functions:
            params["tools"] = self._convert_functions_to_tools(functions)
            params["parallel_tool_calls"] = parallel_tool_calls
        
        logger.debug(
            f"Sending chat completion request to Azure OpenAI deployment={deployment}"
        )
        
        try:
            response = await client.chat.completions.create(**params)
            
            choice = response.choices[0]
            message = choice.message
            
            tool_calls = []
            if message.tool_calls:
                for tc in message.tool_calls:
                    try:
                        arguments = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                    
                    tool_calls.append(ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=arguments,
                    ))
            
            result = ProviderResponse(
                content=message.content,
                tool_calls=tool_calls,
                prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                completion_tokens=response.usage.completion_tokens if response.usage else 0,
                model=response.model,
                finish_reason=choice.finish_reason or "stop",
            )
            
            logger.debug(
                f"Chat completion successful: {result.total_tokens} tokens"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Chat completion failed: {e}")
            raise

