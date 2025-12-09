"""Configuration for the AI Assistant module.

Provides settings specific to the assistant, including:
- Provider configuration
- Model settings
- Token limits
- Behavior flags
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AssistantConfig:
    """Configuration for the AI Assistant.
    
    Attributes:
        openai_api_key: OpenAI API key
        openai_model: Default OpenAI model
        openai_org_id: OpenAI organization ID
        azure_openai_endpoint: Azure OpenAI endpoint URL
        azure_openai_key: Azure OpenAI API key
        azure_openai_deployment: Azure OpenAI deployment name
        azure_openai_api_version: Azure OpenAI API version
        max_tokens: Maximum tokens in completion
        temperature: Default sampling temperature
        max_context_tokens: Maximum tokens in context
        max_iterations: Maximum iterations for agentic loops
        require_confirmation_for: Action types requiring confirmation
    """
    # OpenAI Configuration
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4"
    openai_org_id: Optional[str] = None
    
    # Azure OpenAI Configuration
    azure_openai_endpoint: Optional[str] = None
    azure_openai_key: Optional[str] = None
    azure_openai_deployment: str = "gpt-4"
    azure_openai_api_version: str = "2024-02-15-preview"
    
    # Generation Settings
    max_tokens: int = 4096
    temperature: float = 0.7
    
    # Context Settings
    max_context_tokens: int = 8000
    preserve_recent_messages: int = 4
    
    # Agentic Settings
    max_iterations: int = 10
    
    # Confirmation Settings
    require_confirmation_for: List[str] = field(default_factory=lambda: [
        "create", "update", "delete"
    ])
    
    @classmethod
    def from_environment(cls) -> "AssistantConfig":
        """Create configuration from environment variables.
        
        Returns:
            AssistantConfig instance
        """
        return cls(
            # OpenAI
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            openai_model=os.environ.get("OPENAI_MODEL", "gpt-4"),
            openai_org_id=os.environ.get("OPENAI_ORG_ID"),
            
            # Azure OpenAI
            azure_openai_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
            azure_openai_key=os.environ.get("AZURE_OPENAI_KEY"),
            azure_openai_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4"),
            azure_openai_api_version=os.environ.get(
                "AZURE_OPENAI_API_VERSION",
                "2024-02-15-preview"
            ),
            
            # Generation
            max_tokens=int(os.environ.get("ASSISTANT_MAX_TOKENS", "4096")),
            temperature=float(os.environ.get("ASSISTANT_TEMPERATURE", "0.7")),
            
            # Context
            max_context_tokens=int(os.environ.get("ASSISTANT_MAX_CONTEXT_TOKENS", "8000")),
            preserve_recent_messages=int(os.environ.get("ASSISTANT_PRESERVE_MESSAGES", "4")),
            
            # Agentic
            max_iterations=int(os.environ.get("ASSISTANT_MAX_ITERATIONS", "10")),
        )
    
    @property
    def is_openai_configured(self) -> bool:
        """Check if OpenAI is configured."""
        return bool(self.openai_api_key)
    
    @property
    def is_azure_configured(self) -> bool:
        """Check if Azure OpenAI is configured."""
        return bool(self.azure_openai_endpoint and self.azure_openai_key)
    
    @property
    def is_any_provider_configured(self) -> bool:
        """Check if any provider is configured."""
        return self.is_openai_configured or self.is_azure_configured
    
    @property
    def active_provider(self) -> str:
        """Get the name of the active provider.
        
        Returns:
            Provider name: 'openai', 'azure_openai', or 'mock'
        """
        if self.is_openai_configured:
            return "openai"
        elif self.is_azure_configured:
            return "azure_openai"
        else:
            return "mock"


# Global configuration instance
_config: Optional[AssistantConfig] = None


def get_assistant_config() -> AssistantConfig:
    """Get the global assistant configuration.
    
    Creates from environment on first call.
    
    Returns:
        AssistantConfig instance
    """
    global _config
    if _config is None:
        _config = AssistantConfig.from_environment()
    return _config


def reload_assistant_config() -> AssistantConfig:
    """Reload configuration from environment.
    
    Returns:
        New AssistantConfig instance
    """
    global _config
    _config = AssistantConfig.from_environment()
    return _config

