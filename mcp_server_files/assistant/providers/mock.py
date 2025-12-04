"""Mock provider for testing.

Returns predefined responses without making API calls.
"""

import uuid
from typing import Any, Dict, List, Optional

from .base import BaseProvider, ProviderResponse, ToolCall


class MockProvider(BaseProvider):
    """Mock LLM provider for testing.
    
    Returns configurable predefined responses without API calls.
    Useful for unit tests and development without API keys.
    """
    
    def __init__(
        self,
        default_response: str = "I'm a mock assistant. How can I help?",
        responses: Optional[List[str]] = None,
        tool_calls: Optional[List[ToolCall]] = None,
    ):
        """Initialize the mock provider.
        
        Args:
            default_response: Default response content
            responses: List of responses to cycle through
            tool_calls: Tool calls to return
        """
        self._default_response = default_response
        self._responses = responses or []
        self._tool_calls = tool_calls or []
        self._call_index = 0
        self._call_history: List[Dict[str, Any]] = []
    
    @property
    def provider_name(self) -> str:
        """Get the provider name."""
        return "mock"
    
    @property
    def default_model(self) -> str:
        """Get the default model."""
        return "mock-gpt-4"
    
    def is_configured(self) -> bool:
        """Mock provider is always configured."""
        return True
    
    @property
    def call_history(self) -> List[Dict[str, Any]]:
        """Get history of all calls made to this provider."""
        return self._call_history
    
    def reset(self):
        """Reset call history and index."""
        self._call_index = 0
        self._call_history = []
    
    def set_next_response(
        self,
        content: Optional[str] = None,
        tool_calls: Optional[List[ToolCall]] = None,
    ):
        """Set the next response to return.
        
        Args:
            content: Response content
            tool_calls: Tool calls to include
        """
        self._responses.append(content or self._default_response)
        if tool_calls:
            self._tool_calls = tool_calls
    
    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        functions: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        parallel_tool_calls: bool = True,
    ) -> ProviderResponse:
        """Return a mock chat completion response.
        
        Records the call for later inspection in tests.
        
        Args:
            messages: Chat messages
            model: Model (ignored)
            functions: Function definitions
            temperature: Temperature (ignored)
            max_tokens: Max tokens (ignored)
            parallel_tool_calls: Parallel tool calls (ignored)
            
        Returns:
            Mock ProviderResponse
        """
        # Record the call
        self._call_history.append({
            "messages": messages,
            "model": model,
            "functions": functions,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "parallel_tool_calls": parallel_tool_calls,
        })
        
        # Get response content
        if self._responses:
            content = self._responses[self._call_index % len(self._responses)]
            self._call_index += 1
        else:
            content = self._default_response
        
        # Calculate mock token counts based on message content
        prompt_tokens = sum(len(str(m.get("content", ""))) // 4 for m in messages)
        completion_tokens = len(content) // 4 if content else 0
        
        # Check if we should return tool calls
        tool_calls = []
        if functions and self._tool_calls:
            tool_calls = self._tool_calls
            self._tool_calls = []  # Clear after returning
        
        return ProviderResponse(
            content=content if not tool_calls else None,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model="mock-gpt-4",
            finish_reason="tool_calls" if tool_calls else "stop",
        )
    
    @classmethod
    def create_tool_call(
        cls,
        name: str,
        arguments: Dict[str, Any],
        call_id: Optional[str] = None,
    ) -> ToolCall:
        """Helper to create a ToolCall for testing.
        
        Args:
            name: Function name
            arguments: Function arguments
            call_id: Optional call ID (auto-generated if not provided)
            
        Returns:
            ToolCall instance
        """
        return ToolCall(
            id=call_id or f"call_{uuid.uuid4().hex[:8]}",
            name=name,
            arguments=arguments,
        )

