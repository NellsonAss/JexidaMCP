"""OpenAI provider implementation.

Uses the standard OpenAI API.
"""

import json
import os
from typing import Any, Dict, List, Optional

from .base import BaseProvider, ProviderResponse, ToolCall
from ..logging import get_logger

logger = get_logger(__name__)


class OpenAIProvider(BaseProvider):
    """OpenAI API provider.
    
    Uses the openai Python package to interact with the OpenAI API.
    Configured via environment variables:
    - OPENAI_API_KEY: API key (required)
    - OPENAI_MODEL: Default model (optional, defaults to gpt-4)
    - OPENAI_ORG_ID: Organization ID (optional)
    """
    
    def __init__(self):
        """Initialize the OpenAI provider."""
        self._api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        self._model = os.environ.get("OPENAI_MODEL", "gpt-4")
        self._org_id = os.environ.get("OPENAI_ORG_ID", "").strip() or None
        self._client = None
    
    def _get_client(self):
        """Get or create the OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                
                kwargs = {"api_key": self._api_key}
                if self._org_id:
                    kwargs["organization"] = self._org_id
                    
                self._client = AsyncOpenAI(**kwargs)
            except ImportError:
                raise RuntimeError(
                    "openai package not installed. "
                    "Install with: pip install openai"
                )
        return self._client
    
    @property
    def provider_name(self) -> str:
        """Get the provider name."""
        return "openai"
    
    @property
    def default_model(self) -> str:
        """Get the default model."""
        return self._model
    
    def is_configured(self) -> bool:
        """Check if the provider is configured."""
        return bool(self._api_key)
    
    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        functions: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        parallel_tool_calls: bool = True,
    ) -> ProviderResponse:
        """Send a chat completion request to OpenAI.
        
        Args:
            messages: Chat messages
            model: Model to use (defaults to gpt-4)
            functions: Function definitions for tool calling
            temperature: Sampling temperature
            max_tokens: Maximum tokens in completion
            parallel_tool_calls: Allow parallel tool calls
            
        Returns:
            ProviderResponse with content and/or tool calls
        """
        client = self._get_client()
        model = model or self._model
        
        # Detect model capabilities by prefix patterns
        newer_prefixes = ("gpt-5", "gpt-4.1", "o1", "o3", "o4")
        is_newer_model = any(model.startswith(prefix) for prefix in newer_prefixes)
        supports_temperature = not is_newer_model
        supports_max_tokens = not is_newer_model
        supports_tools = "o1" not in model
        
        # Build request parameters
        params: Dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        
        if supports_temperature and temperature is not None:
            params["temperature"] = temperature
        
        if max_tokens:
            if supports_max_tokens:
                params["max_tokens"] = max_tokens
            else:
                params["max_completion_tokens"] = max_tokens
        
        if functions and supports_tools:
            params["tools"] = self._convert_functions_to_tools(functions)
            params["parallel_tool_calls"] = parallel_tool_calls
        
        logger.debug(
            f"Sending chat completion request to OpenAI model={model}"
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

