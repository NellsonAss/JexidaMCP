"""Tests for the AI Assistant module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

# Import test fixtures
from .conftest import *


class TestProviders:
    """Tests for LLM provider implementations."""
    
    def test_mock_provider_basic_response(self):
        """Test MockProvider returns default response."""
        from assistant.providers.mock import MockProvider
        
        provider = MockProvider(default_response="Hello, test!")
        
        assert provider.is_configured() is True
        assert provider.provider_name == "mock"
        assert provider.default_model == "mock-gpt-4"
    
    @pytest.mark.asyncio
    async def test_mock_provider_chat_completion(self):
        """Test MockProvider chat completion."""
        from assistant.providers.mock import MockProvider
        
        provider = MockProvider(default_response="Test response")
        
        response = await provider.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
        )
        
        assert response.content == "Test response"
        assert response.finish_reason == "stop"
        assert not response.has_tool_calls
    
    @pytest.mark.asyncio
    async def test_mock_provider_with_tool_calls(self):
        """Test MockProvider with tool calls."""
        from assistant.providers.mock import MockProvider, ToolCall
        
        tool_call = ToolCall(
            id="call_123",
            name="test_function",
            arguments={"arg1": "value1"},
        )
        
        provider = MockProvider(
            default_response="",
            tool_calls=[tool_call],
        )
        
        response = await provider.chat_completion(
            messages=[{"role": "user", "content": "Call a function"}],
            functions=[{"name": "test_function", "parameters": {}}],
        )
        
        assert response.has_tool_calls
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "test_function"
        assert response.finish_reason == "tool_calls"
    
    def test_mock_provider_call_history(self):
        """Test MockProvider records call history."""
        from assistant.providers.mock import MockProvider
        
        provider = MockProvider()
        
        # Make a sync test of the call history tracking
        assert len(provider.call_history) == 0
        
        provider.reset()
        assert len(provider.call_history) == 0
    
    @pytest.mark.asyncio
    async def test_openai_provider_not_configured(self):
        """Test OpenAI provider when not configured."""
        from assistant.providers.openai import OpenAIProvider
        
        with patch.dict('os.environ', {}, clear=True):
            provider = OpenAIProvider()
            assert provider.is_configured() is False
    
    @pytest.mark.asyncio
    async def test_azure_provider_not_configured(self):
        """Test Azure provider when not configured."""
        from assistant.providers.azure_openai import AzureOpenAIProvider
        
        with patch.dict('os.environ', {}, clear=True):
            provider = AzureOpenAIProvider()
            assert provider.is_configured() is False
    
    def test_get_provider_returns_mock_when_unconfigured(self):
        """Test get_provider returns mock when no credentials."""
        from assistant.providers import get_provider
        
        with patch.dict('os.environ', {}, clear=True):
            provider = get_provider()
            assert provider.provider_name == "mock"


class TestActionRegistry:
    """Tests for the action registry."""
    
    def test_register_action(self):
        """Test registering an action."""
        from assistant.actions.registry import (
            ActionRegistry,
            ActionDefinition,
            ActionType,
        )
        
        registry = ActionRegistry()
        
        async def test_action(params, user_id=None):
            return {"result": "success"}
        
        action = ActionDefinition(
            name="test_action",
            display_name="Test Action",
            description="A test action",
            action_type=ActionType.EXECUTE,
            parameters={"type": "object", "properties": {}},
            execute_fn=test_action,
        )
        
        registry.register(action)
        
        assert registry.get("test_action") is not None
        assert registry.get("test_action").name == "test_action"
    
    def test_duplicate_registration_fails(self):
        """Test that duplicate registration raises error."""
        from assistant.actions.registry import (
            ActionRegistry,
            ActionDefinition,
            ActionType,
        )
        
        registry = ActionRegistry()
        
        async def test_action(params, user_id=None):
            return {"result": "success"}
        
        action = ActionDefinition(
            name="test_action",
            display_name="Test Action",
            description="A test action",
            action_type=ActionType.EXECUTE,
            parameters={"type": "object", "properties": {}},
            execute_fn=test_action,
        )
        
        registry.register(action)
        
        with pytest.raises(ValueError):
            registry.register(action)
    
    def test_action_permission_check(self):
        """Test action permission checking."""
        from assistant.actions.registry import ActionDefinition, ActionType
        
        async def test_action(params, user_id=None):
            return {"result": "success"}
        
        action = ActionDefinition(
            name="admin_action",
            display_name="Admin Action",
            description="Admin only",
            action_type=ActionType.EXECUTE,
            parameters={},
            execute_fn=test_action,
            required_roles=["admin"],
        )
        
        assert action.check_permission(["admin"]) is True
        assert action.check_permission(["user"]) is False
        assert action.check_permission([]) is False
    
    def test_action_no_role_requirements(self):
        """Test action with no role requirements."""
        from assistant.actions.registry import ActionDefinition, ActionType
        
        async def test_action(params, user_id=None):
            return {"result": "success"}
        
        action = ActionDefinition(
            name="public_action",
            display_name="Public Action",
            description="Anyone can use",
            action_type=ActionType.EXECUTE,
            parameters={},
            execute_fn=test_action,
            required_roles=[],  # Empty = no restrictions
        )
        
        assert action.check_permission([]) is True
        assert action.check_permission(["user"]) is True
    
    def test_to_function_definition(self):
        """Test converting action to OpenAI function definition."""
        from assistant.actions.registry import ActionDefinition, ActionType
        
        async def test_action(params, user_id=None):
            return {"result": "success"}
        
        action = ActionDefinition(
            name="test_func",
            display_name="Test Function",
            description="Test description",
            action_type=ActionType.QUERY,
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"],
            },
            execute_fn=test_action,
        )
        
        func_def = action.to_function_definition()
        
        assert func_def["name"] == "test_func"
        assert func_def["description"] == "Test description"
        assert "properties" in func_def["parameters"]
    
    @pytest.mark.asyncio
    async def test_execute_action(self):
        """Test executing an action."""
        from assistant.actions.registry import (
            ActionRegistry,
            ActionDefinition,
            ActionType,
        )
        
        registry = ActionRegistry()
        
        async def test_action(params, user_id=None):
            return {"value": params.get("input", "") * 2}
        
        action = ActionDefinition(
            name="double_action",
            display_name="Double",
            description="Doubles input",
            action_type=ActionType.EXECUTE,
            parameters={"type": "object"},
            execute_fn=test_action,
        )
        
        registry.register(action)
        
        result = await registry.execute(
            "double_action",
            {"input": "test"},
        )
        
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_execute_nonexistent_action(self):
        """Test executing a non-existent action."""
        from assistant.actions.registry import ActionRegistry
        
        registry = ActionRegistry()
        
        result = await registry.execute(
            "nonexistent",
            {},
        )
        
        assert result.success is False
        assert "not found" in result.message


class TestContext:
    """Tests for context building."""
    
    def test_build_system_prompt_basic(self):
        """Test building a basic system prompt."""
        from assistant.context import build_system_prompt
        
        prompt = build_system_prompt()
        
        assert "JexidaMCP" in prompt
        assert "AI assistant" in prompt.lower()
    
    def test_build_system_prompt_with_user_context(self):
        """Test building prompt with user context."""
        from assistant.context import build_system_prompt
        
        prompt = build_system_prompt(
            user_id="test_user",
            user_roles=["admin"],
        )
        
        assert "test_user" in prompt or "admin" in prompt.lower()
    
    def test_build_system_prompt_with_page_context(self):
        """Test building prompt with page context."""
        from assistant.context import build_system_prompt
        
        prompt = build_system_prompt(
            page_context={
                "page": "secrets",
                "model": "Secret",
            }
        )
        
        assert "secrets" in prompt.lower() or "Secret" in prompt
    
    def test_build_conversation_messages(self):
        """Test building conversation messages."""
        from assistant.context import build_conversation_messages
        
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        
        result = build_conversation_messages(messages, "You are a helper.")
        
        assert len(result) == 3  # system + 2 messages
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "You are a helper."
    
    def test_truncate_context(self):
        """Test truncating context to fit token limits."""
        from assistant.context import truncate_context
        
        # Create many messages
        messages = [
            {"role": "user", "content": "A" * 1000}
            for _ in range(50)
        ]
        
        truncated = truncate_context(messages, max_tokens=2000)
        
        # Should have fewer messages
        assert len(truncated) < len(messages)
        # Should preserve recent messages
        assert len(truncated) >= 4
    
    def test_estimate_token_count(self):
        """Test token count estimation."""
        from assistant.context import estimate_token_count
        
        # Rough estimate: ~4 chars per token
        text = "a" * 100
        tokens = estimate_token_count(text)
        
        assert tokens == 25  # 100 / 4


class TestModelIntrospection:
    """Tests for model introspection utilities."""
    
    def test_get_json_schema_type_string(self):
        """Test JSON schema type for string."""
        from assistant.model_introspection import get_json_schema_type
        
        schema = get_json_schema_type(str)
        assert schema["type"] == "string"
    
    def test_get_json_schema_type_int(self):
        """Test JSON schema type for int."""
        from assistant.model_introspection import get_json_schema_type
        
        schema = get_json_schema_type(int)
        assert schema["type"] == "integer"
    
    def test_get_json_schema_type_bool(self):
        """Test JSON schema type for bool."""
        from assistant.model_introspection import get_json_schema_type
        
        schema = get_json_schema_type(bool)
        assert schema["type"] == "boolean"
    
    def test_get_json_schema_type_list(self):
        """Test JSON schema type for List."""
        from typing import List
        from assistant.model_introspection import get_json_schema_type
        
        schema = get_json_schema_type(List[str])
        assert schema["type"] == "array"
        assert schema["items"]["type"] == "string"
    
    def test_get_json_schema_type_optional(self):
        """Test JSON schema type for Optional."""
        from typing import Optional
        from assistant.model_introspection import get_json_schema_type
        
        schema = get_json_schema_type(Optional[str])
        # Optional should return the inner type
        assert schema["type"] == "string"
    
    def test_get_json_schema_type_datetime(self):
        """Test JSON schema type for datetime."""
        from datetime import datetime
        from assistant.model_introspection import get_json_schema_type
        
        schema = get_json_schema_type(datetime)
        assert schema["type"] == "string"
        assert schema["format"] == "date-time"


class TestConfig:
    """Tests for assistant configuration."""
    
    def test_config_from_environment_empty(self):
        """Test config from empty environment."""
        from assistant.config import AssistantConfig
        
        with patch.dict('os.environ', {}, clear=True):
            config = AssistantConfig.from_environment()
            
            assert config.is_openai_configured is False
            assert config.is_azure_configured is False
            assert config.active_provider == "mock"
    
    def test_config_from_environment_openai(self):
        """Test config with OpenAI credentials."""
        from assistant.config import AssistantConfig
        
        with patch.dict('os.environ', {
            'OPENAI_API_KEY': 'sk-test123',
            'OPENAI_MODEL': 'gpt-4-turbo',
        }, clear=True):
            config = AssistantConfig.from_environment()
            
            assert config.is_openai_configured is True
            assert config.openai_api_key == 'sk-test123'
            assert config.openai_model == 'gpt-4-turbo'
            assert config.active_provider == "openai"
    
    def test_config_from_environment_azure(self):
        """Test config with Azure credentials."""
        from assistant.config import AssistantConfig
        
        with patch.dict('os.environ', {
            'AZURE_OPENAI_ENDPOINT': 'https://test.openai.azure.com',
            'AZURE_OPENAI_KEY': 'azure-key-123',
            'AZURE_OPENAI_DEPLOYMENT': 'gpt-4-deployment',
        }, clear=True):
            config = AssistantConfig.from_environment()
            
            assert config.is_azure_configured is True
            assert config.azure_openai_endpoint == 'https://test.openai.azure.com'
            assert config.active_provider == "azure_openai"
    
    def test_config_openai_takes_priority(self):
        """Test that OpenAI takes priority over Azure."""
        from assistant.config import AssistantConfig
        
        with patch.dict('os.environ', {
            'OPENAI_API_KEY': 'sk-test123',
            'AZURE_OPENAI_ENDPOINT': 'https://test.openai.azure.com',
            'AZURE_OPENAI_KEY': 'azure-key-123',
        }, clear=True):
            config = AssistantConfig.from_environment()
            
            # OpenAI should take priority
            assert config.active_provider == "openai"


class TestSchemas:
    """Tests for Pydantic schemas."""
    
    def test_chat_request_validation(self):
        """Test ChatRequest validation."""
        from assistant.schemas import ChatRequest
        
        request = ChatRequest(
            message="Hello",
            conversation_id=1,
            page_context={"page": "test"},
        )
        
        assert request.message == "Hello"
        assert request.conversation_id == 1
    
    def test_chat_request_minimal(self):
        """Test ChatRequest with minimal fields."""
        from assistant.schemas import ChatRequest
        
        request = ChatRequest(message="Hello")
        
        assert request.message == "Hello"
        assert request.conversation_id is None
        assert request.page_context is None
    
    def test_chat_response_structure(self):
        """Test ChatResponse structure."""
        from assistant.schemas import ChatResponse
        
        response = ChatResponse(
            conversation_id=1,
            message_id=1,
            content="Hello!",
            tool_calls=None,
            pending_confirmations=None,
            tokens_used=10,
        )
        
        assert response.conversation_id == 1
        assert response.content == "Hello!"

