"""OpenAI provider implementation.

Uses the standard OpenAI API for development and testing.
Now supports dynamic model selection from the model registry.
"""

import json
import os
from typing import Any, Dict, List, Optional

# Load .env file, overriding system environment variables
from dotenv import load_dotenv
load_dotenv(override=True)

from .base import BaseProvider, ProviderResponse, ToolCall
from ..models_registry import get_model, get_active_model, ModelConfig

# Import logging
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from logging_config import get_logger

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
        self._org_id = os.environ.get("OPENAI_ORG_ID", "").strip() if os.environ.get("OPENAI_ORG_ID") else None
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
        """Get the default model from the registry or environment."""
        active = get_active_model()
        if active:
            return active.model_id
        return self._model
    
    def is_configured(self) -> bool:
        """Check if the provider is configured."""
        return bool(self._api_key)
    
    def _get_model_config(self, model_id: str) -> Optional[ModelConfig]:
        """Get model configuration from registry.
        
        Args:
            model_id: Model identifier
            
        Returns:
            ModelConfig if found in registry, None otherwise
        """
        return get_model(model_id)
    
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
        
        Uses model configuration from the registry when available.
        
        Args:
            messages: Chat messages
            model: Model to use (defaults to active model or gpt-4)
            functions: Function definitions for tool calling
            temperature: Sampling temperature (may be overridden by model config)
            max_tokens: Maximum tokens in completion
            parallel_tool_calls: Allow parallel tool calls
            
        Returns:
            ProviderResponse with content and/or tool calls
        """
        client = self._get_client()
        
        # Get model from registry or use default
        if model is None:
            active = get_active_model()
            model = active.model_id if active else self._model
        
        # Get model configuration from registry
        model_config = self._get_model_config(model)
        
        # Determine model capabilities from registry or fall back to heuristics
        if model_config:
            supports_temperature = model_config.supports_temperature
            supports_max_tokens = model_config.supports_max_tokens
            supports_tools = model_config.supports_tools
            supports_parallel_tools = model_config.supports_parallel_tools
            
            logger.debug(
                f"Using model config for {model}",
                extra={
                    "model": model,
                    "supports_temperature": supports_temperature,
                    "supports_max_tokens": supports_max_tokens,
                    "supports_tools": supports_tools,
                }
            )
        else:
            # Fallback: Detect model capabilities by prefix patterns
            newer_prefixes = ("gpt-5", "gpt-4.1", "o1", "o3", "o4")
            is_newer_model = any(model.startswith(prefix) for prefix in newer_prefixes)
            supports_temperature = not is_newer_model
            supports_max_tokens = not is_newer_model  # Newer models use max_completion_tokens
            supports_tools = "o1" not in model  # O1 models don't support tools
            supports_parallel_tools = supports_tools
            
            logger.debug(
                f"Using heuristic detection for unknown model {model}",
                extra={
                    "model": model,
                    "is_newer_model": is_newer_model,
                }
            )
        
        # Build request parameters
        params: Dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        
        # Only set temperature if model supports it
        if supports_temperature and temperature is not None:
            params["temperature"] = temperature
        
        # Use correct token limit parameter based on model
        if max_tokens:
            if supports_max_tokens:
                params["max_tokens"] = max_tokens
            else:
                # Newer models require max_completion_tokens
                params["max_completion_tokens"] = max_tokens
        
        # Add tools if functions provided and model supports them
        if functions and supports_tools:
            params["tools"] = self._convert_functions_to_tools(functions)
            if supports_parallel_tools:
                params["parallel_tool_calls"] = parallel_tool_calls
        elif functions and not supports_tools:
            logger.warning(
                f"Model {model} does not support tools, ignoring function definitions",
                extra={"model": model}
            )
        
        logger.debug(
            "Sending chat completion request",
            extra={
                "provider": "openai",
                "model": model,
                "message_count": len(messages),
                "has_tools": bool(functions),
            }
        )
        
        try:
            response = await client.chat.completions.create(**params)
            
            # Extract response data
            choice = response.choices[0]
            message = choice.message
            
            # Parse tool calls if present
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
                "Chat completion successful",
                extra={
                    "provider": "openai",
                    "model": response.model,
                    "finish_reason": choice.finish_reason,
                    "prompt_tokens": result.prompt_tokens,
                    "completion_tokens": result.completion_tokens,
                    "tool_calls_count": len(tool_calls),
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Chat completion failed",
                extra={
                    "provider": "openai",
                    "error": str(e),
                }
            )
            raise

