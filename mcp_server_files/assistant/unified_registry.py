"""Unified Model Registry and Orchestration System.

Provides a central registry for both local (Ollama/MCP) and external (OpenAI)
models, along with orchestration strategies for routing requests.

This module unifies model management for both the web dashboard and CLI.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import logging
import httpx
import asyncio

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Types
# =============================================================================

class ModelSource(str, Enum):
    """Where the model runs."""
    LOCAL = "local"      # Ollama/local LLM on MCP server
    EXTERNAL = "external"  # OpenAI/hosted API


class ModelProvider(str, Enum):
    """Specific provider type."""
    OLLAMA = "ollama"
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"


class StrategyType(str, Enum):
    """Type of orchestration strategy."""
    SINGLE = "single"      # Just one model
    CASCADE = "cascade"    # Ordered list, try cheap first
    ROUTER = "router"      # Classification-based routing


class ModelCapability(str, Enum):
    """Model capabilities."""
    CHAT = "chat"
    FUNCTION_CALLING = "function_calling"
    VISION = "vision"
    REASONING = "reasoning"
    CODE = "code"
    JSON_MODE = "json_mode"
    STREAMING = "streaming"


class ModelTier(str, Enum):
    """Model performance/cost tier."""
    BUDGET = "budget"
    STANDARD = "standard"
    PREMIUM = "premium"
    FLAGSHIP = "flagship"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ModelProfile:
    """Definition of a single model.
    
    Represents any model whether local (Ollama) or external (OpenAI).
    """
    id: str                                    # Internal key, e.g., "gpt-5-nano", "llama3:latest"
    display_name: str                          # Human-readable name
    source: ModelSource                        # local vs external
    provider: ModelProvider                    # ollama, openai, etc.
    model_id: str                              # API model identifier
    description: str = ""
    group: str = "Other"                       # UI grouping label
    tier: ModelTier = ModelTier.STANDARD
    capabilities: List[ModelCapability] = field(default_factory=list)
    context_window: int = 128000
    max_output_tokens: int = 16384
    supports_temperature: bool = True
    default_temperature: float = 0.7
    supports_tools: bool = True
    supports_parallel_tools: bool = True
    supports_max_tokens: bool = True           # False = use max_completion_tokens
    input_price_per_1m: float = 0.0
    output_price_per_1m: float = 0.0
    is_available: bool = True                  # Dynamically set based on discovery
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to API response dict."""
        return {
            "id": self.id,
            "display_name": self.display_name,
            "source": self.source.value,
            "provider": self.provider.value,
            "model_id": self.model_id,
            "description": self.description,
            "group": self.group,
            "tier": self.tier.value,
            "capabilities": [c.value for c in self.capabilities],
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "supports_temperature": self.supports_temperature,
            "default_temperature": self.default_temperature if self.supports_temperature else None,
            "supports_tools": self.supports_tools,
            "supports_parallel_tools": self.supports_parallel_tools,
            "pricing": {
                "input_per_1m": self.input_price_per_1m,
                "output_per_1m": self.output_price_per_1m,
            },
            "is_available": self.is_available,
            "notes": self.notes,
        }


@dataclass
class ModelStrategy:
    """Orchestration strategy for model selection.
    
    Can be a single model, a cascade (try cheap first), or a router.
    """
    id: str                                    # e.g., "single:gpt-5-nano", "cascade:cloud-cheapest"
    display_name: str                          # Human-readable name
    strategy_type: StrategyType
    models: List[str] = field(default_factory=list)  # Ordered list of model profile IDs
    description: str = ""
    group: str = "Strategies"                  # UI grouping
    escalation_rules: Dict[str, Any] = field(default_factory=dict)  # Future: routing rules
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to API response dict."""
        return {
            "id": self.id,
            "display_name": self.display_name,
            "strategy_type": self.strategy_type.value,
            "models": self.models,
            "description": self.description,
            "group": self.group,
            "escalation_rules": self.escalation_rules,
        }


@dataclass 
class ExecutionResult:
    """Result from executing a request through a strategy."""
    success: bool
    content: str
    model_used: str                            # Which model actually answered
    strategy_id: str                           # Which strategy was used
    tool_calls: Optional[List[Dict]] = None
    tokens_used: Optional[Dict[str, int]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


# =============================================================================
# Model Registry
# =============================================================================

class UnifiedModelRegistry:
    """Central registry for all models and strategies.
    
    Manages:
    - External model profiles (OpenAI, etc.)
    - Local model discovery (Ollama)
    - Orchestration strategies
    - Active selection state
    """
    
    def __init__(self):
        self._models: Dict[str, ModelProfile] = {}
        self._strategies: Dict[str, ModelStrategy] = {}
        self._active_strategy_id: str = "single:gpt-5-nano"
        self._local_models_discovered: bool = False
        self._ollama_host: Optional[str] = None
        
    # -------------------------------------------------------------------------
    # Model Management
    # -------------------------------------------------------------------------
    
    def register_model(self, profile: ModelProfile) -> None:
        """Register a model profile."""
        self._models[profile.id] = profile
        logger.debug(f"Registered model: {profile.id}")
        
    def get_model(self, model_id: str) -> Optional[ModelProfile]:
        """Get a model by ID."""
        return self._models.get(model_id)
    
    def get_all_models(self) -> List[ModelProfile]:
        """Get all registered models."""
        return list(self._models.values())
    
    def get_models_by_source(self, source: ModelSource) -> List[ModelProfile]:
        """Get models filtered by source."""
        return [m for m in self._models.values() if m.source == source]
    
    def get_models_by_group(self, group: str) -> List[ModelProfile]:
        """Get models filtered by UI group."""
        return [m for m in self._models.values() if m.group == group]
    
    def get_available_models(self) -> List[ModelProfile]:
        """Get only available models."""
        return [m for m in self._models.values() if m.is_available]
    
    # -------------------------------------------------------------------------
    # Strategy Management
    # -------------------------------------------------------------------------
    
    def register_strategy(self, strategy: ModelStrategy) -> None:
        """Register a strategy."""
        self._strategies[strategy.id] = strategy
        logger.debug(f"Registered strategy: {strategy.id}")
        
    def get_strategy(self, strategy_id: str) -> Optional[ModelStrategy]:
        """Get a strategy by ID."""
        return self._strategies.get(strategy_id)
    
    def get_all_strategies(self) -> List[ModelStrategy]:
        """Get all registered strategies."""
        return list(self._strategies.values())
    
    def get_strategies_by_type(self, strategy_type: StrategyType) -> List[ModelStrategy]:
        """Get strategies filtered by type."""
        return [s for s in self._strategies.values() if s.strategy_type == strategy_type]
    
    # -------------------------------------------------------------------------
    # Active Selection
    # -------------------------------------------------------------------------
    
    def get_active_strategy(self) -> Optional[ModelStrategy]:
        """Get the currently active strategy."""
        return self._strategies.get(self._active_strategy_id)
    
    def get_active_strategy_id(self) -> str:
        """Get the ID of the active strategy."""
        return self._active_strategy_id
    
    def set_active_strategy(self, strategy_id: str) -> ModelStrategy:
        """Set the active strategy by ID.
        
        Raises:
            ValueError: If strategy_id is not found
        """
        if strategy_id not in self._strategies:
            available = ", ".join(self._strategies.keys())
            raise ValueError(f"Unknown strategy: {strategy_id}. Available: {available}")
        
        self._active_strategy_id = strategy_id
        logger.info(f"Active strategy set to: {strategy_id}")
        return self._strategies[strategy_id]
    
    # -------------------------------------------------------------------------
    # Local Model Discovery
    # -------------------------------------------------------------------------
    
    def set_ollama_host(self, host: str) -> None:
        """Set the Ollama host for local model discovery."""
        self._ollama_host = host
        self._local_models_discovered = False
        
    async def discover_local_models(self, host: Optional[str] = None) -> List[ModelProfile]:
        """Discover local models from Ollama.
        
        Marks pre-registered models as available if found, and creates
        new entries for any additional models discovered.
        
        Args:
            host: Ollama host (defaults to configured host or localhost:11434)
            
        Returns:
            List of discovered/activated local model profiles
        """
        if host:
            self._ollama_host = host
            
        ollama_url = self._ollama_host or "http://localhost:11434"
        
        discovered = []
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{ollama_url}/api/tags")
                
                if response.status_code != 200:
                    logger.warning(f"Ollama discovery failed: {response.status_code}")
                    return discovered
                    
                data = response.json()
                models = data.get("models", [])
                
                for model_info in models:
                    name = model_info.get("name", "")
                    if not name:
                        continue
                    
                    model_id = f"local:{name}"
                    
                    # Check if we have a pre-registered profile for this model
                    existing = self._models.get(model_id)
                    if existing:
                        # Mark as available
                        existing.is_available = True
                        discovered.append(existing)
                        logger.info(f"Activated pre-registered model: {name}")
                        continue
                    
                    # Create profile for newly discovered model
                    # Extract base name for display (e.g., "llama3.2" from "llama3.2:latest")
                    base_name = name.split(":")[0]
                    display_name = base_name.replace("-", " ").replace("_", " ").title()
                    
                    profile = ModelProfile(
                        id=model_id,
                        display_name=display_name,
                        source=ModelSource.LOCAL,
                        provider=ModelProvider.OLLAMA,
                        model_id=name,
                        description=f"Local Ollama model: {name}",
                        group="🖥️ Local Models",
                        tier=ModelTier.STANDARD,
                        capabilities=[ModelCapability.CHAT, ModelCapability.CODE],
                        context_window=model_info.get("context_length", 4096),
                        supports_temperature=True,
                        default_temperature=0.7,
                        supports_tools=False,
                        input_price_per_1m=0.0,
                        output_price_per_1m=0.0,
                        is_available=True,
                        notes="Local model - no API costs",
                    )
                    
                    # Register and track
                    self.register_model(profile)
                    discovered.append(profile)
                    
                    # Also create a single-model strategy for it
                    self._create_single_strategy(profile)
                    
                self._local_models_discovered = True
                logger.info(f"Discovered/activated {len(discovered)} local models from Ollama")
                
        except Exception as e:
            logger.warning(f"Failed to discover local models: {e}")
            
        return discovered
    
    def discover_local_models_sync(self, host: Optional[str] = None) -> List[ModelProfile]:
        """Synchronous wrapper for discover_local_models."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        return loop.run_until_complete(self.discover_local_models(host))
    
    # -------------------------------------------------------------------------
    # Strategy Helpers
    # -------------------------------------------------------------------------
    
    def _create_single_strategy(self, profile: ModelProfile) -> ModelStrategy:
        """Create a single-model strategy for a profile."""
        strategy = ModelStrategy(
            id=f"single:{profile.id}",
            display_name=profile.display_name,
            strategy_type=StrategyType.SINGLE,
            models=[profile.id],
            description=f"Use {profile.display_name} only",
            group=profile.group,
        )
        self.register_strategy(strategy)
        return strategy
    
    def create_cascade_strategy(
        self,
        strategy_id: str,
        display_name: str,
        model_ids: List[str],
        description: str = "",
        group: str = "🔀 Auto / Orchestration",
    ) -> ModelStrategy:
        """Create a cascade strategy.
        
        Args:
            strategy_id: Unique ID for the strategy
            display_name: Human-readable name
            model_ids: Ordered list of model IDs (cheap first)
            description: Strategy description
            group: UI grouping
            
        Returns:
            Created ModelStrategy
        """
        strategy = ModelStrategy(
            id=strategy_id,
            display_name=display_name,
            strategy_type=StrategyType.CASCADE,
            models=model_ids,
            description=description,
            group=group,
            escalation_rules={
                "fallthrough_on_error": True,
                "fallthrough_on_uncertainty": True,
            },
        )
        self.register_strategy(strategy)
        return strategy
    
    # -------------------------------------------------------------------------
    # Combined List for UI
    # -------------------------------------------------------------------------
    
    def get_combined_options_for_ui(self, include_unavailable_local: bool = True) -> List[Dict[str, Any]]:
        """Get combined list of models and strategies for UI dropdown.
        
        Groups:
        - 🔀 Auto / Orchestration
        - 🚀 GPT-5 Series (Latest)
        - 🧠 O-Series (Reasoning)
        - ⭐ GPT-4 Series
        - 🖥️ Local Models
        
        Args:
            include_unavailable_local: If True, show local models even if not discovered yet
        
        Returns:
            List of dicts with id, display_name, type, group, etc.
        """
        options = []
        
        # Sort strategies by group
        group_order = [
            "🔀 Auto / Orchestration",
            "🚀 GPT-5 Series (Latest)",
            "🧠 O-Series (Reasoning)", 
            "⭐ GPT-4 Series",
            "🖥️ Local Models",
        ]
        
        tier_order = {
            ModelTier.FLAGSHIP: 0,
            ModelTier.PREMIUM: 1,
            ModelTier.STANDARD: 2,
            ModelTier.BUDGET: 3,
        }
        
        # Add cascade/orchestration strategies first
        for strategy in self.get_strategies_by_type(StrategyType.CASCADE):
            options.append({
                "id": strategy.id,
                "display_name": strategy.display_name,
                "type": "strategy",
                "strategy_type": strategy.strategy_type.value,
                "group": strategy.group,
                "description": strategy.description,
                "models": strategy.models,
            })
        
        # Add single-model strategies (which wrap models)
        for strategy in sorted(
            self.get_strategies_by_type(StrategyType.SINGLE),
            key=lambda s: (
                group_order.index(s.group) if s.group in group_order else 99,
                tier_order.get(self._models.get(s.models[0], ModelProfile(
                    id="", display_name="", source=ModelSource.EXTERNAL, 
                    provider=ModelProvider.OPENAI, model_id=""
                )).tier, 99) if s.models else 99,
            )
        ):
            model = self._models.get(strategy.models[0]) if strategy.models else None
            if not model:
                continue
                
            # For external models, only show if available (always true)
            # For local models, show if available OR if include_unavailable_local is True
            is_local = model.source == ModelSource.LOCAL
            should_show = model.is_available or (is_local and include_unavailable_local)
            
            if should_show:
                options.append({
                    "id": strategy.id,
                    "display_name": strategy.display_name,
                    "type": "single",
                    "strategy_type": strategy.strategy_type.value,
                    "group": strategy.group,
                    "description": model.description,
                    "model_id": model.id,
                    "supports_temperature": model.supports_temperature,
                    "supports_tools": model.supports_tools,
                    "tier": model.tier.value,
                    "source": model.source.value,
                    "is_available": model.is_available,
                    "notes": model.notes if not model.is_available else "",
                })
                
        return options


# =============================================================================
# Global Registry Instance
# =============================================================================

_registry: Optional[UnifiedModelRegistry] = None


def get_registry() -> UnifiedModelRegistry:
    """Get the global registry instance, initializing if needed."""
    global _registry
    if _registry is None:
        _registry = UnifiedModelRegistry()
        _initialize_default_models(_registry)
        _initialize_default_local_models(_registry)
        _initialize_default_strategies(_registry)
    return _registry


def _initialize_default_models(registry: UnifiedModelRegistry) -> None:
    """Initialize default external models."""
    
    # GPT-5 Series
    registry.register_model(ModelProfile(
        id="gpt-5-nano",
        display_name="GPT-5 Nano",
        source=ModelSource.EXTERNAL,
        provider=ModelProvider.OPENAI,
        model_id="gpt-5-nano",
        description="Fastest, most cost-efficient GPT-5. Great for simple tasks.",
        group="🚀 GPT-5 Series (Latest)",
        tier=ModelTier.BUDGET,
        capabilities=[ModelCapability.CHAT, ModelCapability.FUNCTION_CALLING, ModelCapability.CODE],
        context_window=400000,
        max_output_tokens=128000,
        supports_temperature=False,
        supports_max_tokens=False,
        input_price_per_1m=0.05,
        output_price_per_1m=0.40,
        notes="No temperature support. Use max_completion_tokens.",
    ))
    
    registry.register_model(ModelProfile(
        id="gpt-5-mini",
        display_name="GPT-5 Mini",
        source=ModelSource.EXTERNAL,
        provider=ModelProvider.OPENAI,
        model_id="gpt-5-mini",
        description="Balanced GPT-5 for general reasoning and chat.",
        group="🚀 GPT-5 Series (Latest)",
        tier=ModelTier.STANDARD,
        capabilities=[ModelCapability.CHAT, ModelCapability.FUNCTION_CALLING, ModelCapability.CODE, ModelCapability.VISION],
        context_window=400000,
        max_output_tokens=128000,
        supports_temperature=False,
        supports_max_tokens=False,
        input_price_per_1m=0.25,
        output_price_per_1m=1.00,
    ))
    
    registry.register_model(ModelProfile(
        id="gpt-5",
        display_name="GPT-5",
        source=ModelSource.EXTERNAL,
        provider=ModelProvider.OPENAI,
        model_id="gpt-5",
        description="Full GPT-5 flagship for complex reasoning and coding.",
        group="🚀 GPT-5 Series (Latest)",
        tier=ModelTier.FLAGSHIP,
        capabilities=[ModelCapability.CHAT, ModelCapability.FUNCTION_CALLING, ModelCapability.CODE, ModelCapability.VISION, ModelCapability.REASONING],
        context_window=400000,
        max_output_tokens=128000,
        supports_temperature=False,
        supports_max_tokens=False,
        input_price_per_1m=1.25,
        output_price_per_1m=10.00,
    ))
    
    registry.register_model(ModelProfile(
        id="gpt-5-pro",
        display_name="GPT-5 Pro",
        source=ModelSource.EXTERNAL,
        provider=ModelProvider.OPENAI,
        model_id="gpt-5-pro",
        description="Maximum reasoning power for the hardest problems.",
        group="🚀 GPT-5 Series (Latest)",
        tier=ModelTier.FLAGSHIP,
        capabilities=[ModelCapability.CHAT, ModelCapability.FUNCTION_CALLING, ModelCapability.CODE, ModelCapability.VISION, ModelCapability.REASONING],
        context_window=400000,
        max_output_tokens=272000,
        supports_temperature=False,
        supports_max_tokens=False,
        input_price_per_1m=15.00,
        output_price_per_1m=120.00,
    ))
    
    # O-Series (Reasoning)
    registry.register_model(ModelProfile(
        id="o4-mini",
        display_name="O4 Mini",
        source=ModelSource.EXTERNAL,
        provider=ModelProvider.OPENAI,
        model_id="o4-mini",
        description="Latest compact reasoning model. Fast with strong reasoning.",
        group="🧠 O-Series (Reasoning)",
        tier=ModelTier.STANDARD,
        capabilities=[ModelCapability.CHAT, ModelCapability.FUNCTION_CALLING, ModelCapability.REASONING, ModelCapability.CODE, ModelCapability.VISION],
        context_window=200000,
        max_output_tokens=100000,
        supports_temperature=False,
        supports_max_tokens=False,
        input_price_per_1m=1.10,
        output_price_per_1m=4.40,
    ))
    
    registry.register_model(ModelProfile(
        id="o3-mini",
        display_name="O3 Mini",
        source=ModelSource.EXTERNAL,
        provider=ModelProvider.OPENAI,
        model_id="o3-mini",
        description="Compact reasoning model for math and code.",
        group="🧠 O-Series (Reasoning)",
        tier=ModelTier.STANDARD,
        capabilities=[ModelCapability.CHAT, ModelCapability.FUNCTION_CALLING, ModelCapability.REASONING, ModelCapability.CODE],
        context_window=200000,
        max_output_tokens=100000,
        supports_temperature=False,
        supports_max_tokens=False,
        input_price_per_1m=1.10,
        output_price_per_1m=4.40,
    ))
    
    registry.register_model(ModelProfile(
        id="o1",
        display_name="O1",
        source=ModelSource.EXTERNAL,
        provider=ModelProvider.OPENAI,
        model_id="o1",
        description="Advanced reasoning model for complex problems. No tools.",
        group="🧠 O-Series (Reasoning)",
        tier=ModelTier.FLAGSHIP,
        capabilities=[ModelCapability.CHAT, ModelCapability.REASONING, ModelCapability.CODE],
        context_window=200000,
        max_output_tokens=100000,
        supports_temperature=False,
        supports_max_tokens=False,
        supports_tools=False,
        input_price_per_1m=15.00,
        output_price_per_1m=60.00,
        notes="No function calling support.",
    ))
    
    registry.register_model(ModelProfile(
        id="o1-mini",
        display_name="O1 Mini",
        source=ModelSource.EXTERNAL,
        provider=ModelProvider.OPENAI,
        model_id="o1-mini",
        description="Faster reasoning model for STEM tasks. No tools.",
        group="🧠 O-Series (Reasoning)",
        tier=ModelTier.STANDARD,
        capabilities=[ModelCapability.CHAT, ModelCapability.REASONING, ModelCapability.CODE],
        context_window=128000,
        max_output_tokens=65536,
        supports_temperature=False,
        supports_max_tokens=False,
        supports_tools=False,
        input_price_per_1m=3.00,
        output_price_per_1m=12.00,
        notes="No function calling support.",
    ))
    
    # GPT-4.1 Series
    registry.register_model(ModelProfile(
        id="gpt-4.1",
        display_name="GPT-4.1",
        source=ModelSource.EXTERNAL,
        provider=ModelProvider.OPENAI,
        model_id="gpt-4.1",
        description="Enhanced GPT-4 with 1M token context. Supports temperature.",
        group="⭐ GPT-4 Series",
        tier=ModelTier.PREMIUM,
        capabilities=[ModelCapability.CHAT, ModelCapability.FUNCTION_CALLING, ModelCapability.CODE, ModelCapability.VISION],
        context_window=1000000,
        max_output_tokens=32768,
        supports_temperature=True,
        default_temperature=0.7,
        input_price_per_1m=2.00,
        output_price_per_1m=8.00,
    ))
    
    registry.register_model(ModelProfile(
        id="gpt-4.1-mini",
        display_name="GPT-4.1 Mini",
        source=ModelSource.EXTERNAL,
        provider=ModelProvider.OPENAI,
        model_id="gpt-4.1-mini",
        description="Faster, cheaper GPT-4.1. Supports temperature.",
        group="⭐ GPT-4 Series",
        tier=ModelTier.STANDARD,
        capabilities=[ModelCapability.CHAT, ModelCapability.FUNCTION_CALLING, ModelCapability.CODE, ModelCapability.VISION],
        context_window=1000000,
        max_output_tokens=32768,
        supports_temperature=True,
        default_temperature=0.7,
        input_price_per_1m=0.40,
        output_price_per_1m=1.60,
    ))
    
    registry.register_model(ModelProfile(
        id="gpt-4.1-nano",
        display_name="GPT-4.1 Nano",
        source=ModelSource.EXTERNAL,
        provider=ModelProvider.OPENAI,
        model_id="gpt-4.1-nano",
        description="Fastest GPT-4.1 for high-throughput. Supports temperature.",
        group="⭐ GPT-4 Series",
        tier=ModelTier.BUDGET,
        capabilities=[ModelCapability.CHAT, ModelCapability.FUNCTION_CALLING, ModelCapability.CODE],
        context_window=1000000,
        max_output_tokens=32768,
        supports_temperature=True,
        default_temperature=0.7,
        input_price_per_1m=0.10,
        output_price_per_1m=0.40,
    ))
    
    # Legacy models
    registry.register_model(ModelProfile(
        id="gpt-4o",
        display_name="GPT-4o (Legacy)",
        source=ModelSource.EXTERNAL,
        provider=ModelProvider.OPENAI,
        model_id="gpt-4o",
        description="Previous flagship. Supports temperature.",
        group="⭐ GPT-4 Series",
        tier=ModelTier.PREMIUM,
        capabilities=[ModelCapability.CHAT, ModelCapability.FUNCTION_CALLING, ModelCapability.VISION, ModelCapability.CODE],
        context_window=128000,
        max_output_tokens=16384,
        supports_temperature=True,
        default_temperature=0.7,
        input_price_per_1m=2.50,
        output_price_per_1m=10.00,
    ))
    
    registry.register_model(ModelProfile(
        id="gpt-4o-mini",
        display_name="GPT-4o Mini (Legacy)",
        source=ModelSource.EXTERNAL,
        provider=ModelProvider.OPENAI,
        model_id="gpt-4o-mini",
        description="Fast and affordable legacy model. Supports temperature.",
        group="⭐ GPT-4 Series",
        tier=ModelTier.BUDGET,
        capabilities=[ModelCapability.CHAT, ModelCapability.FUNCTION_CALLING, ModelCapability.VISION, ModelCapability.CODE],
        context_window=128000,
        max_output_tokens=16384,
        supports_temperature=True,
        default_temperature=0.7,
        input_price_per_1m=0.15,
        output_price_per_1m=0.60,
    ))


def _initialize_default_local_models(registry: UnifiedModelRegistry) -> None:
    """Initialize recommended local Ollama models.
    
    These are popular, well-performing models that work great locally.
    Users can pull them with: ollama pull <model_name>
    """
    
    # Llama 3.2 - Latest Meta model, excellent all-around
    registry.register_model(ModelProfile(
        id="local:llama3.2:latest",
        display_name="Llama 3.2",
        source=ModelSource.LOCAL,
        provider=ModelProvider.OLLAMA,
        model_id="llama3.2:latest",
        description="Latest Meta Llama. Excellent general-purpose model.",
        group="🖥️ Local Models",
        tier=ModelTier.STANDARD,
        capabilities=[ModelCapability.CHAT, ModelCapability.CODE, ModelCapability.REASONING],
        context_window=128000,
        supports_temperature=True,
        default_temperature=0.7,
        supports_tools=False,
        input_price_per_1m=0.0,
        output_price_per_1m=0.0,
        is_available=False,  # Set to True after discovery
        notes="Pull with: ollama pull llama3.2",
    ))
    
    # Llama 3.1 - Previous gen, very stable
    registry.register_model(ModelProfile(
        id="local:llama3.1:latest",
        display_name="Llama 3.1",
        source=ModelSource.LOCAL,
        provider=ModelProvider.OLLAMA,
        model_id="llama3.1:latest",
        description="Stable Meta Llama 3.1. Great for general tasks.",
        group="🖥️ Local Models",
        tier=ModelTier.STANDARD,
        capabilities=[ModelCapability.CHAT, ModelCapability.CODE],
        context_window=128000,
        supports_temperature=True,
        default_temperature=0.7,
        supports_tools=False,
        input_price_per_1m=0.0,
        output_price_per_1m=0.0,
        is_available=False,
        notes="Pull with: ollama pull llama3.1",
    ))
    
    # Qwen 2.5 - Alibaba's excellent model
    registry.register_model(ModelProfile(
        id="local:qwen2.5:latest",
        display_name="Qwen 2.5",
        source=ModelSource.LOCAL,
        provider=ModelProvider.OLLAMA,
        model_id="qwen2.5:latest",
        description="Alibaba's Qwen 2.5. Strong reasoning and multilingual.",
        group="🖥️ Local Models",
        tier=ModelTier.STANDARD,
        capabilities=[ModelCapability.CHAT, ModelCapability.CODE, ModelCapability.REASONING],
        context_window=32000,
        supports_temperature=True,
        default_temperature=0.7,
        supports_tools=True,  # Qwen supports tool use
        input_price_per_1m=0.0,
        output_price_per_1m=0.0,
        is_available=False,
        notes="Pull with: ollama pull qwen2.5",
    ))
    
    # Qwen 2.5 Coder - Specialized for code
    registry.register_model(ModelProfile(
        id="local:qwen2.5-coder:latest",
        display_name="Qwen 2.5 Coder",
        source=ModelSource.LOCAL,
        provider=ModelProvider.OLLAMA,
        model_id="qwen2.5-coder:latest",
        description="Code-specialized Qwen. Excellent for programming tasks.",
        group="🖥️ Local Models",
        tier=ModelTier.STANDARD,
        capabilities=[ModelCapability.CHAT, ModelCapability.CODE],
        context_window=32000,
        supports_temperature=True,
        default_temperature=0.3,  # Lower temp for code
        supports_tools=False,
        input_price_per_1m=0.0,
        output_price_per_1m=0.0,
        is_available=False,
        notes="Pull with: ollama pull qwen2.5-coder",
    ))
    
    # Mistral - Fast and efficient
    registry.register_model(ModelProfile(
        id="local:mistral:latest",
        display_name="Mistral",
        source=ModelSource.LOCAL,
        provider=ModelProvider.OLLAMA,
        model_id="mistral:latest",
        description="Mistral AI's efficient model. Fast responses.",
        group="🖥️ Local Models",
        tier=ModelTier.BUDGET,
        capabilities=[ModelCapability.CHAT, ModelCapability.CODE],
        context_window=32000,
        supports_temperature=True,
        default_temperature=0.7,
        supports_tools=False,
        input_price_per_1m=0.0,
        output_price_per_1m=0.0,
        is_available=False,
        notes="Pull with: ollama pull mistral",
    ))
    
    # DeepSeek Coder V2 - Excellent for code
    registry.register_model(ModelProfile(
        id="local:deepseek-coder-v2:latest",
        display_name="DeepSeek Coder V2",
        source=ModelSource.LOCAL,
        provider=ModelProvider.OLLAMA,
        model_id="deepseek-coder-v2:latest",
        description="DeepSeek's code model. Top-tier for programming.",
        group="🖥️ Local Models",
        tier=ModelTier.PREMIUM,
        capabilities=[ModelCapability.CHAT, ModelCapability.CODE, ModelCapability.REASONING],
        context_window=128000,
        supports_temperature=True,
        default_temperature=0.3,
        supports_tools=False,
        input_price_per_1m=0.0,
        output_price_per_1m=0.0,
        is_available=False,
        notes="Pull with: ollama pull deepseek-coder-v2",
    ))
    
    # Phi-3 - Microsoft's small but capable model
    registry.register_model(ModelProfile(
        id="local:phi3:latest",
        display_name="Phi-3",
        source=ModelSource.LOCAL,
        provider=ModelProvider.OLLAMA,
        model_id="phi3:latest",
        description="Microsoft's Phi-3. Small but surprisingly capable.",
        group="🖥️ Local Models",
        tier=ModelTier.BUDGET,
        capabilities=[ModelCapability.CHAT, ModelCapability.CODE],
        context_window=4096,
        supports_temperature=True,
        default_temperature=0.7,
        supports_tools=False,
        input_price_per_1m=0.0,
        output_price_per_1m=0.0,
        is_available=False,
        notes="Pull with: ollama pull phi3",
    ))
    
    # Gemma 2 - Google's open model
    registry.register_model(ModelProfile(
        id="local:gemma2:latest",
        display_name="Gemma 2",
        source=ModelSource.LOCAL,
        provider=ModelProvider.OLLAMA,
        model_id="gemma2:latest",
        description="Google's Gemma 2. Good balance of speed and quality.",
        group="🖥️ Local Models",
        tier=ModelTier.STANDARD,
        capabilities=[ModelCapability.CHAT, ModelCapability.CODE],
        context_window=8192,
        supports_temperature=True,
        default_temperature=0.7,
        supports_tools=False,
        input_price_per_1m=0.0,
        output_price_per_1m=0.0,
        is_available=False,
        notes="Pull with: ollama pull gemma2",
    ))
    
    # CodeLlama - Meta's code-focused Llama
    registry.register_model(ModelProfile(
        id="local:codellama:latest",
        display_name="Code Llama",
        source=ModelSource.LOCAL,
        provider=ModelProvider.OLLAMA,
        model_id="codellama:latest",
        description="Meta's Code Llama. Optimized for code generation.",
        group="🖥️ Local Models",
        tier=ModelTier.STANDARD,
        capabilities=[ModelCapability.CHAT, ModelCapability.CODE],
        context_window=16384,
        supports_temperature=True,
        default_temperature=0.3,
        supports_tools=False,
        input_price_per_1m=0.0,
        output_price_per_1m=0.0,
        is_available=False,
        notes="Pull with: ollama pull codellama",
    ))
    
    # Mixtral - Mistral's MoE model
    registry.register_model(ModelProfile(
        id="local:mixtral:latest",
        display_name="Mixtral 8x7B",
        source=ModelSource.LOCAL,
        provider=ModelProvider.OLLAMA,
        model_id="mixtral:latest",
        description="Mistral's Mixture of Experts. High quality, needs more RAM.",
        group="🖥️ Local Models",
        tier=ModelTier.PREMIUM,
        capabilities=[ModelCapability.CHAT, ModelCapability.CODE, ModelCapability.REASONING],
        context_window=32000,
        supports_temperature=True,
        default_temperature=0.7,
        supports_tools=False,
        input_price_per_1m=0.0,
        output_price_per_1m=0.0,
        is_available=False,
        notes="Pull with: ollama pull mixtral (requires ~26GB RAM)",
    ))


def _initialize_default_strategies(registry: UnifiedModelRegistry) -> None:
    """Initialize default strategies including cascades."""
    
    # Create single-model strategies for all registered models
    for model in registry.get_all_models():
        registry._create_single_strategy(model)
    
    # Cloud cascade: cheapest first
    registry.create_cascade_strategy(
        strategy_id="cascade:cloud-cheapest-first",
        display_name="Auto — Cheapest First (Cloud)",
        model_ids=["gpt-5-nano", "gpt-5-mini", "gpt-5", "o1"],
        description="Try cheapest cloud model first, escalate if needed.",
        group="🔀 Auto / Orchestration",
    )
    
    # Local-first cascade with common local models
    registry.create_cascade_strategy(
        strategy_id="cascade:local-first",
        display_name="Auto — Local First",
        model_ids=["local:llama3.2:latest", "local:qwen2.5:latest", "gpt-5-nano", "gpt-5-mini"],
        description="Try local models first, fall back to cloud.",
        group="🔀 Auto / Orchestration",
    )
    
    # Reasoning cascade
    registry.create_cascade_strategy(
        strategy_id="cascade:reasoning",
        display_name="Auto — Reasoning Focus",
        model_ids=["o3-mini", "o4-mini", "o1"],
        description="Reasoning models, escalate complexity.",
        group="🔀 Auto / Orchestration",
    )
    
    # Local code cascade
    registry.create_cascade_strategy(
        strategy_id="cascade:local-code",
        display_name="Auto — Local Code Focus",
        model_ids=["local:qwen2.5-coder:latest", "local:deepseek-coder-v2:latest", "local:codellama:latest", "gpt-5-nano"],
        description="Code-focused local models with cloud fallback.",
        group="🔀 Auto / Orchestration",
    )


# =============================================================================
# Execution Engine
# =============================================================================

async def execute_with_strategy(
    strategy_id: str,
    messages: List[Dict[str, Any]],
    functions: Optional[List[Dict[str, Any]]] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    registry: Optional[UnifiedModelRegistry] = None,
) -> ExecutionResult:
    """Execute a request using the specified strategy.
    
    Args:
        strategy_id: ID of the strategy to use
        messages: Chat messages
        functions: Optional function definitions for tool use
        temperature: Optional temperature override
        max_tokens: Optional max tokens override
        registry: Optional registry instance (uses global if not provided)
        
    Returns:
        ExecutionResult with response and metadata
    """
    if registry is None:
        registry = get_registry()
        
    strategy = registry.get_strategy(strategy_id)
    if not strategy:
        return ExecutionResult(
            success=False,
            content="",
            model_used="",
            strategy_id=strategy_id,
            error=f"Unknown strategy: {strategy_id}",
        )
    
    if strategy.strategy_type == StrategyType.SINGLE:
        # Direct execution with single model
        if not strategy.models:
            return ExecutionResult(
                success=False,
                content="",
                model_used="",
                strategy_id=strategy_id,
                error="Strategy has no models configured",
            )
            
        model_id = strategy.models[0]
        return await _execute_with_model(
            model_id=model_id,
            messages=messages,
            functions=functions,
            temperature=temperature,
            max_tokens=max_tokens,
            strategy_id=strategy_id,
            registry=registry,
        )
        
    elif strategy.strategy_type == StrategyType.CASCADE:
        # Try models in order
        last_error = None
        for model_id in strategy.models:
            result = await _execute_with_model(
                model_id=model_id,
                messages=messages,
                functions=functions,
                temperature=temperature,
                max_tokens=max_tokens,
                strategy_id=strategy_id,
                registry=registry,
            )
            
            if result.success:
                return result
            
            last_error = result.error
            logger.info(f"Cascade: {model_id} failed, trying next. Error: {last_error}")
            
        # All models failed
        return ExecutionResult(
            success=False,
            content="",
            model_used="",
            strategy_id=strategy_id,
            error=f"All models in cascade failed. Last error: {last_error}",
        )
        
    else:
        return ExecutionResult(
            success=False,
            content="",
            model_used="",
            strategy_id=strategy_id,
            error=f"Unsupported strategy type: {strategy.strategy_type}",
        )


async def _execute_with_model(
    model_id: str,
    messages: List[Dict[str, Any]],
    functions: Optional[List[Dict[str, Any]]],
    temperature: Optional[float],
    max_tokens: Optional[int],
    strategy_id: str,
    registry: UnifiedModelRegistry,
) -> ExecutionResult:
    """Execute a request with a specific model.
    
    Routes to appropriate provider (OpenAI, Ollama, etc.)
    """
    model = registry.get_model(model_id)
    if not model:
        return ExecutionResult(
            success=False,
            content="",
            model_used=model_id,
            strategy_id=strategy_id,
            error=f"Unknown model: {model_id}",
        )
    
    if not model.is_available:
        return ExecutionResult(
            success=False,
            content="",
            model_used=model_id,
            strategy_id=strategy_id,
            error=f"Model not available: {model_id}",
        )
    
    try:
        if model.provider == ModelProvider.OPENAI:
            return await _execute_openai(model, messages, functions, temperature, max_tokens, strategy_id)
        elif model.provider == ModelProvider.OLLAMA:
            return await _execute_ollama(model, messages, functions, temperature, max_tokens, strategy_id)
        else:
            return ExecutionResult(
                success=False,
                content="",
                model_used=model_id,
                strategy_id=strategy_id,
                error=f"Unsupported provider: {model.provider}",
            )
    except Exception as e:
        logger.error(f"Model execution failed: {model_id}: {e}")
        return ExecutionResult(
            success=False,
            content="",
            model_used=model_id,
            strategy_id=strategy_id,
            error=str(e),
        )


async def _execute_openai(
    model: ModelProfile,
    messages: List[Dict[str, Any]],
    functions: Optional[List[Dict[str, Any]]],
    temperature: Optional[float],
    max_tokens: Optional[int],
    strategy_id: str,
) -> ExecutionResult:
    """Execute request with OpenAI provider."""
    from .providers.openai import OpenAIProvider
    
    provider = OpenAIProvider()
    
    # Use model's default temperature if not overridden
    if temperature is None and model.supports_temperature:
        temperature = model.default_temperature
    elif not model.supports_temperature:
        temperature = None
    
    response = await provider.chat_completion(
        messages=messages,
        model=model.model_id,
        functions=functions if model.supports_tools else None,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    
    return ExecutionResult(
        success=True,
        content=response.content,
        model_used=model.id,
        strategy_id=strategy_id,
        tool_calls=[tc.__dict__ for tc in response.tool_calls] if response.tool_calls else None,
        tokens_used={
            "input": response.usage.get("prompt_tokens", 0) if response.usage else 0,
            "output": response.usage.get("completion_tokens", 0) if response.usage else 0,
        },
        metadata={"provider": "openai", "raw_model": response.model},
    )


async def _execute_ollama(
    model: ModelProfile,
    messages: List[Dict[str, Any]],
    functions: Optional[List[Dict[str, Any]]],
    temperature: Optional[float],
    max_tokens: Optional[int],
    strategy_id: str,
) -> ExecutionResult:
    """Execute request with Ollama provider."""
    registry = get_registry()
    ollama_url = registry._ollama_host or "http://localhost:11434"
    
    # Convert messages to Ollama format
    ollama_messages = []
    for msg in messages:
        ollama_messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", ""),
        })
    
    payload = {
        "model": model.model_id,
        "messages": ollama_messages,
        "stream": False,
    }
    
    if temperature is not None:
        payload["options"] = {"temperature": temperature}
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{ollama_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            
            content = data.get("message", {}).get("content", "")
            
            return ExecutionResult(
                success=True,
                content=content,
                model_used=model.id,
                strategy_id=strategy_id,
                tokens_used={
                    "input": data.get("prompt_eval_count", 0),
                    "output": data.get("eval_count", 0),
                },
                metadata={"provider": "ollama", "raw_model": model.model_id},
            )
            
    except Exception as e:
        return ExecutionResult(
            success=False,
            content="",
            model_used=model.id,
            strategy_id=strategy_id,
            error=f"Ollama error: {e}",
        )

