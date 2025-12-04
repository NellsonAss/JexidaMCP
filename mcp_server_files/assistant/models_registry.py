"""Model registry for AI Assistant.

Defines supported models with their specific configurations and capabilities.
Based on actual API testing and OpenAI documentation (December 2025).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ModelProvider(str, Enum):
    """Supported model providers."""
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"


class ModelCapability(str, Enum):
    """Model capabilities."""
    CHAT = "chat"
    FUNCTION_CALLING = "function_calling"
    VISION = "vision"
    REASONING = "reasoning"
    CODE = "code"
    JSON_MODE = "json_mode"
    STREAMING = "streaming"


class ModelFamily(str, Enum):
    """Model family/generation."""
    GPT5 = "gpt-5"
    GPT4 = "gpt-4"
    GPT35 = "gpt-3.5"
    O_SERIES = "o-series"


@dataclass
class ModelConfig:
    """Configuration for a specific AI model.
    
    Attributes:
        id: Unique model identifier (used in API calls)
        name: Display name
        provider: Model provider (openai, azure_openai)
        model_id: API model identifier (same as id for OpenAI)
        description: Model description
        family: Model family/generation
        capabilities: List of model capabilities
        context_window: Maximum context window size in tokens
        max_output_tokens: Maximum output tokens
        supports_temperature: Whether temperature parameter is supported
        default_temperature: Default temperature if supported (None if not)
        supports_max_tokens: Whether max_tokens parameter works (vs max_completion_tokens)
        supports_tools: Whether tool/function calling is supported
        supports_parallel_tools: Whether parallel tool calls are supported
        supports_json_mode: Whether response_format json_object is supported
        supports_streaming: Whether streaming is supported
        input_price_per_1m: Input price per 1M tokens (USD)
        output_price_per_1m: Output price per 1M tokens (USD)
        is_reasoning_model: Whether this is a reasoning/thinking model (o-series)
        tier: Model tier (budget, standard, premium, flagship)
        notes: Additional notes about the model
    """
    id: str
    name: str
    provider: ModelProvider
    model_id: str
    description: str
    family: ModelFamily
    capabilities: List[ModelCapability] = field(default_factory=list)
    context_window: int = 128000
    max_output_tokens: int = 16384
    supports_temperature: bool = True
    default_temperature: Optional[float] = 0.7
    supports_max_tokens: bool = True  # False = use max_completion_tokens
    supports_tools: bool = True
    supports_parallel_tools: bool = True
    supports_json_mode: bool = True
    supports_streaming: bool = True
    input_price_per_1m: float = 0.0
    output_price_per_1m: float = 0.0
    is_reasoning_model: bool = False
    tier: str = "standard"
    notes: str = ""

    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "provider": self.provider.value,
            "model_id": self.model_id,
            "description": self.description,
            "family": self.family.value,
            "capabilities": [c.value for c in self.capabilities],
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "supports_temperature": self.supports_temperature,
            "default_temperature": self.default_temperature,
            "supports_tools": self.supports_tools,
            "supports_json_mode": self.supports_json_mode,
            "tier": self.tier,
            "pricing": {
                "input_per_1m": self.input_price_per_1m,
                "output_per_1m": self.output_price_per_1m,
            },
            "notes": self.notes,
        }


# =============================================================================
# Model Definitions
# =============================================================================

MODELS: Dict[str, ModelConfig] = {}


def register_model(config: ModelConfig) -> ModelConfig:
    """Register a model configuration."""
    MODELS[config.id] = config
    return config


# -----------------------------------------------------------------------------
# GPT-5 Series (Current Generation - August 2025)
# Based on actual API testing
# -----------------------------------------------------------------------------

register_model(ModelConfig(
    id="gpt-5-nano",
    name="GPT-5 Nano",
    provider=ModelProvider.OPENAI,
    model_id="gpt-5-nano",
    description="Fastest, most cost-efficient GPT-5. Great for simple tasks, classification, and high-throughput use cases.",
    family=ModelFamily.GPT5,
    capabilities=[
        ModelCapability.CHAT,
        ModelCapability.FUNCTION_CALLING,
        ModelCapability.CODE,
        ModelCapability.JSON_MODE,
        ModelCapability.STREAMING,
    ],
    context_window=400000,
    max_output_tokens=128000,
    supports_temperature=False,  # Tested: temperature not supported
    default_temperature=None,
    supports_max_tokens=False,  # Tested: must use max_completion_tokens
    supports_tools=True,  # Tested: works
    supports_parallel_tools=True,
    supports_json_mode=True,  # Tested: works
    input_price_per_1m=0.05,
    output_price_per_1m=0.40,
    tier="budget",
    notes="Temperature not supported. Use max_completion_tokens instead of max_tokens.",
))

register_model(ModelConfig(
    id="gpt-5-mini",
    name="GPT-5 Mini",
    provider=ModelProvider.OPENAI,
    model_id="gpt-5-mini",
    description="Balanced GPT-5 model. Good for general reasoning, chat, and moderate complexity tasks.",
    family=ModelFamily.GPT5,
    capabilities=[
        ModelCapability.CHAT,
        ModelCapability.FUNCTION_CALLING,
        ModelCapability.CODE,
        ModelCapability.JSON_MODE,
        ModelCapability.STREAMING,
        ModelCapability.VISION,
    ],
    context_window=400000,
    max_output_tokens=128000,
    supports_temperature=False,  # GPT-5 series doesn't support temperature
    default_temperature=None,
    supports_max_tokens=False,
    supports_tools=True,
    supports_parallel_tools=True,
    supports_json_mode=True,
    input_price_per_1m=0.25,
    output_price_per_1m=1.00,
    tier="standard",
    notes="Temperature not supported. Use max_completion_tokens instead of max_tokens.",
))

register_model(ModelConfig(
    id="gpt-5",
    name="GPT-5",
    provider=ModelProvider.OPENAI,
    model_id="gpt-5",
    description="Full GPT-5 flagship model. Excellent for complex reasoning, coding, and multi-step tasks.",
    family=ModelFamily.GPT5,
    capabilities=[
        ModelCapability.CHAT,
        ModelCapability.FUNCTION_CALLING,
        ModelCapability.CODE,
        ModelCapability.JSON_MODE,
        ModelCapability.STREAMING,
        ModelCapability.VISION,
        ModelCapability.REASONING,
    ],
    context_window=400000,
    max_output_tokens=128000,
    supports_temperature=False,
    default_temperature=None,
    supports_max_tokens=False,
    supports_tools=True,
    supports_parallel_tools=True,
    supports_json_mode=True,
    input_price_per_1m=1.25,
    output_price_per_1m=10.00,
    tier="flagship",
    notes="Temperature not supported. Use max_completion_tokens instead of max_tokens.",
))

register_model(ModelConfig(
    id="gpt-5-pro",
    name="GPT-5 Pro",
    provider=ModelProvider.OPENAI,
    model_id="gpt-5-pro",
    description="Most capable GPT-5. Maximum reasoning power for the hardest problems.",
    family=ModelFamily.GPT5,
    capabilities=[
        ModelCapability.CHAT,
        ModelCapability.FUNCTION_CALLING,
        ModelCapability.CODE,
        ModelCapability.JSON_MODE,
        ModelCapability.STREAMING,
        ModelCapability.VISION,
        ModelCapability.REASONING,
    ],
    context_window=400000,
    max_output_tokens=272000,
    supports_temperature=False,
    default_temperature=None,
    supports_max_tokens=False,
    supports_tools=True,
    supports_parallel_tools=True,
    supports_json_mode=True,
    input_price_per_1m=15.00,
    output_price_per_1m=120.00,
    tier="flagship",
    notes="Highest reasoning capability. Temperature not supported.",
))

# -----------------------------------------------------------------------------
# GPT-4.1 Series (April 2025)
# Enhanced coding and long-context
# -----------------------------------------------------------------------------

register_model(ModelConfig(
    id="gpt-4.1",
    name="GPT-4.1",
    provider=ModelProvider.OPENAI,
    model_id="gpt-4.1",
    description="Enhanced GPT-4 with improved coding and 1M token context.",
    family=ModelFamily.GPT4,
    capabilities=[
        ModelCapability.CHAT,
        ModelCapability.FUNCTION_CALLING,
        ModelCapability.CODE,
        ModelCapability.JSON_MODE,
        ModelCapability.STREAMING,
        ModelCapability.VISION,
    ],
    context_window=1000000,
    max_output_tokens=32768,
    supports_temperature=True,
    default_temperature=0.7,
    supports_max_tokens=True,
    supports_tools=True,
    supports_parallel_tools=True,
    supports_json_mode=True,
    input_price_per_1m=2.00,
    output_price_per_1m=8.00,
    tier="premium",
    notes="1M token context window. Good for long document processing.",
))

register_model(ModelConfig(
    id="gpt-4.1-mini",
    name="GPT-4.1 Mini",
    provider=ModelProvider.OPENAI,
    model_id="gpt-4.1-mini",
    description="Faster, cheaper GPT-4.1 variant with same capabilities.",
    family=ModelFamily.GPT4,
    capabilities=[
        ModelCapability.CHAT,
        ModelCapability.FUNCTION_CALLING,
        ModelCapability.CODE,
        ModelCapability.JSON_MODE,
        ModelCapability.STREAMING,
        ModelCapability.VISION,
    ],
    context_window=1000000,
    max_output_tokens=32768,
    supports_temperature=True,
    default_temperature=0.7,
    supports_max_tokens=True,
    supports_tools=True,
    supports_parallel_tools=True,
    supports_json_mode=True,
    input_price_per_1m=0.40,
    output_price_per_1m=1.60,
    tier="standard",
    notes="Cost-effective GPT-4.1 with 1M context.",
))

register_model(ModelConfig(
    id="gpt-4.1-nano",
    name="GPT-4.1 Nano",
    provider=ModelProvider.OPENAI,
    model_id="gpt-4.1-nano",
    description="Fastest GPT-4.1 for high-throughput tasks.",
    family=ModelFamily.GPT4,
    capabilities=[
        ModelCapability.CHAT,
        ModelCapability.FUNCTION_CALLING,
        ModelCapability.CODE,
        ModelCapability.JSON_MODE,
        ModelCapability.STREAMING,
    ],
    context_window=1000000,
    max_output_tokens=32768,
    supports_temperature=True,
    default_temperature=0.7,
    supports_max_tokens=True,
    supports_tools=True,
    supports_parallel_tools=True,
    supports_json_mode=True,
    input_price_per_1m=0.10,
    output_price_per_1m=0.40,
    tier="budget",
    notes="Budget GPT-4.1 option.",
))

# -----------------------------------------------------------------------------
# O-Series (Reasoning Models)
# -----------------------------------------------------------------------------

register_model(ModelConfig(
    id="o4-mini",
    name="O4 Mini",
    provider=ModelProvider.OPENAI,
    model_id="o4-mini",
    description="Latest compact reasoning model. Fast with strong reasoning.",
    family=ModelFamily.O_SERIES,
    capabilities=[
        ModelCapability.CHAT,
        ModelCapability.FUNCTION_CALLING,
        ModelCapability.REASONING,
        ModelCapability.CODE,
        ModelCapability.VISION,
    ],
    context_window=200000,
    max_output_tokens=100000,
    supports_temperature=False,
    default_temperature=None,
    supports_max_tokens=False,
    supports_tools=True,
    supports_parallel_tools=True,
    supports_json_mode=True,
    is_reasoning_model=True,
    input_price_per_1m=1.10,
    output_price_per_1m=4.40,
    tier="standard",
    notes="Reasoning model. No temperature support.",
))

register_model(ModelConfig(
    id="o3-mini",
    name="O3 Mini",
    provider=ModelProvider.OPENAI,
    model_id="o3-mini",
    description="Compact reasoning model with excellent math and code performance.",
    family=ModelFamily.O_SERIES,
    capabilities=[
        ModelCapability.CHAT,
        ModelCapability.FUNCTION_CALLING,
        ModelCapability.REASONING,
        ModelCapability.CODE,
    ],
    context_window=200000,
    max_output_tokens=100000,
    supports_temperature=False,
    default_temperature=None,
    supports_max_tokens=False,
    supports_tools=True,
    supports_parallel_tools=True,
    supports_json_mode=True,
    is_reasoning_model=True,
    input_price_per_1m=1.10,
    output_price_per_1m=4.40,
    tier="standard",
    notes="Reasoning model. Good for math and coding.",
))

register_model(ModelConfig(
    id="o1",
    name="O1",
    provider=ModelProvider.OPENAI,
    model_id="o1",
    description="Advanced reasoning model for complex multi-step problems.",
    family=ModelFamily.O_SERIES,
    capabilities=[
        ModelCapability.CHAT,
        ModelCapability.REASONING,
        ModelCapability.CODE,
    ],
    context_window=200000,
    max_output_tokens=100000,
    supports_temperature=False,
    default_temperature=None,
    supports_max_tokens=False,
    supports_tools=False,  # O1 doesn't support function calling
    supports_parallel_tools=False,
    supports_json_mode=False,
    is_reasoning_model=True,
    input_price_per_1m=15.00,
    output_price_per_1m=60.00,
    tier="flagship",
    notes="Reasoning model. No function calling or JSON mode.",
))

register_model(ModelConfig(
    id="o1-mini",
    name="O1 Mini",
    provider=ModelProvider.OPENAI,
    model_id="o1-mini",
    description="Faster reasoning model, optimized for coding and math.",
    family=ModelFamily.O_SERIES,
    capabilities=[
        ModelCapability.CHAT,
        ModelCapability.REASONING,
        ModelCapability.CODE,
    ],
    context_window=128000,
    max_output_tokens=65536,
    supports_temperature=False,
    default_temperature=None,
    supports_max_tokens=False,
    supports_tools=False,
    supports_parallel_tools=False,
    supports_json_mode=False,
    is_reasoning_model=True,
    input_price_per_1m=3.00,
    output_price_per_1m=12.00,
    tier="standard",
    notes="Reasoning model for STEM tasks. No function calling.",
))

# -----------------------------------------------------------------------------
# Legacy GPT-4 Series (for compatibility)
# These may be deprecated but included for users who still have access
# -----------------------------------------------------------------------------

register_model(ModelConfig(
    id="gpt-4o",
    name="GPT-4o (Legacy)",
    provider=ModelProvider.OPENAI,
    model_id="gpt-4o",
    description="Previous flagship multimodal model. Superseded by GPT-5.",
    family=ModelFamily.GPT4,
    capabilities=[
        ModelCapability.CHAT,
        ModelCapability.FUNCTION_CALLING,
        ModelCapability.VISION,
        ModelCapability.CODE,
        ModelCapability.JSON_MODE,
        ModelCapability.STREAMING,
    ],
    context_window=128000,
    max_output_tokens=16384,
    supports_temperature=True,
    default_temperature=0.7,
    supports_max_tokens=True,
    supports_tools=True,
    supports_parallel_tools=True,
    supports_json_mode=True,
    input_price_per_1m=2.50,
    output_price_per_1m=10.00,
    tier="premium",
    notes="Legacy model. Consider using GPT-5 series.",
))

register_model(ModelConfig(
    id="gpt-4o-mini",
    name="GPT-4o Mini (Legacy)",
    provider=ModelProvider.OPENAI,
    model_id="gpt-4o-mini",
    description="Fast and affordable GPT-4 variant. Superseded by GPT-5-nano.",
    family=ModelFamily.GPT4,
    capabilities=[
        ModelCapability.CHAT,
        ModelCapability.FUNCTION_CALLING,
        ModelCapability.VISION,
        ModelCapability.CODE,
        ModelCapability.JSON_MODE,
        ModelCapability.STREAMING,
    ],
    context_window=128000,
    max_output_tokens=16384,
    supports_temperature=True,
    default_temperature=0.7,
    supports_max_tokens=True,
    supports_tools=True,
    supports_parallel_tools=True,
    supports_json_mode=True,
    input_price_per_1m=0.15,
    output_price_per_1m=0.60,
    tier="budget",
    notes="Legacy budget model. Consider GPT-5-nano.",
))


# =============================================================================
# Model Registry Functions
# =============================================================================

def get_model(model_id: str) -> Optional[ModelConfig]:
    """Get a model configuration by ID.
    
    Args:
        model_id: Model identifier
        
    Returns:
        ModelConfig if found, None otherwise
    """
    return MODELS.get(model_id)


def get_all_models() -> List[ModelConfig]:
    """Get all registered models.
    
    Returns:
        List of all model configurations
    """
    return list(MODELS.values())


def get_models_by_provider(provider: ModelProvider) -> List[ModelConfig]:
    """Get models by provider.
    
    Args:
        provider: Model provider
        
    Returns:
        List of models for that provider
    """
    return [m for m in MODELS.values() if m.provider == provider]


def get_models_by_family(family: ModelFamily) -> List[ModelConfig]:
    """Get models by family.
    
    Args:
        family: Model family (gpt-5, gpt-4, o-series, etc.)
        
    Returns:
        List of models in that family
    """
    return [m for m in MODELS.values() if m.family == family]


def get_models_by_tier(tier: str) -> List[ModelConfig]:
    """Get models by tier.
    
    Args:
        tier: Model tier (budget, standard, premium, flagship)
        
    Returns:
        List of models in that tier
    """
    return [m for m in MODELS.values() if m.tier == tier]


def get_models_with_capability(capability: ModelCapability) -> List[ModelConfig]:
    """Get models with a specific capability.
    
    Args:
        capability: Required capability
        
    Returns:
        List of models with that capability
    """
    return [m for m in MODELS.values() if capability in m.capabilities]


def get_models_supporting_tools() -> List[ModelConfig]:
    """Get models that support function calling/tools.
    
    Returns:
        List of models with tool support
    """
    return [m for m in MODELS.values() if m.supports_tools]


# =============================================================================
# Active Model State
# =============================================================================

_active_model_id: str = "gpt-5-nano"  # Default model


def get_active_model() -> ModelConfig:
    """Get the currently active model configuration.
    
    Returns:
        Active ModelConfig
    """
    model = MODELS.get(_active_model_id)
    if model is None:
        # Fallback to first available model
        return list(MODELS.values())[0] if MODELS else None
    return model


def set_active_model(model_id: str) -> ModelConfig:
    """Set the active model by ID.
    
    Args:
        model_id: Model identifier to activate
        
    Returns:
        The newly active ModelConfig
        
    Raises:
        ValueError: If model_id is not found
    """
    global _active_model_id
    
    if model_id not in MODELS:
        available = ", ".join(MODELS.keys())
        raise ValueError(f"Unknown model: {model_id}. Available: {available}")
    
    _active_model_id = model_id
    return MODELS[model_id]


def get_active_model_id() -> str:
    """Get the ID of the currently active model.
    
    Returns:
        Active model ID
    """
    return _active_model_id
