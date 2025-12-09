"""Base provider interface for LLM providers.

All providers must implement this interface for consistent behavior.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolCall:
    """Represents a tool/function call from the LLM."""
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class ProviderResponse:
    """Standardized response from any LLM provider.
    
    Attributes:
        content: Text content from the assistant
        tool_calls: List of tool calls requested by the model
        prompt_tokens: Number of tokens in the prompt
        completion_tokens: Number of tokens in the completion
        model: Model identifier used
        finish_reason: Why the model stopped (stop, tool_calls, length, etc.)
    """
    content: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    finish_reason: str = "stop"
    
    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return len(self.tool_calls) > 0
    
    @property
    def total_tokens(self) -> int:
        """Total tokens used in this request."""
        return self.prompt_tokens + self.completion_tokens


class BaseProvider(ABC):
    """Abstract base class for LLM providers.
    
    All provider implementations must inherit from this class
    and implement all abstract methods.
    """
    
    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        functions: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        parallel_tool_calls: bool = True,
    ) -> ProviderResponse:
        """Send a chat completion request to the LLM.
        
        Args:
            messages: List of messages in OpenAI format
            model: Model identifier (uses default if not specified)
            functions: List of function definitions for tool calling
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens in completion
            parallel_tool_calls: Whether to allow multiple tool calls
            
        Returns:
            ProviderResponse with content and/or tool calls
        """
        pass
    
    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the provider is properly configured.
        
        Returns:
            True if all required configuration is present
        """
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the name of this provider.
        
        Returns:
            Provider identifier (e.g., "openai", "azure_openai", "mock")
        """
        pass
    
    @property
    @abstractmethod
    def default_model(self) -> str:
        """Get the default model for this provider.
        
        Returns:
            Default model identifier
        """
        pass
    
    def _convert_functions_to_tools(
        self,
        functions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert function definitions to OpenAI tools format.
        
        Args:
            functions: List of function definitions
            
        Returns:
            List of tool definitions
        """
        return [
            {
                "type": "function",
                "function": func
            }
            for func in functions
        ]

