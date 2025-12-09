"""Tests for tool registry functionality."""

import pytest
from pydantic import BaseModel, Field

from tool_registry import ToolRegistry, get_registry, tool


class SampleInput(BaseModel):
    """Sample input schema for testing."""
    name: str = Field(description="A name")
    count: int = Field(default=1, description="A count")


class SampleOutput(BaseModel):
    """Sample output schema for testing."""
    result: str = Field(description="The result")


class TestToolRegistry:
    """Tests for ToolRegistry class."""
    
    def test_register_tool(self):
        """Test registering a new tool."""
        registry = ToolRegistry()
        
        async def handler(params: SampleInput) -> SampleOutput:
            return SampleOutput(result=f"Hello {params.name}")
        
        registry.register(
            name="test.tool",
            description="A test tool",
            input_schema=SampleInput,
            output_schema=SampleOutput,
            handler=handler,
            tags=["test"]
        )
        
        assert registry.get("test.tool") is not None
        assert registry.get("test.tool").name == "test.tool"
        assert registry.get("test.tool").description == "A test tool"
    
    def test_register_duplicate_raises(self):
        """Test that registering duplicate tool raises error."""
        registry = ToolRegistry()
        
        async def handler(params: SampleInput) -> SampleOutput:
            return SampleOutput(result="test")
        
        registry.register(
            name="test.tool",
            description="First tool",
            input_schema=SampleInput,
            output_schema=SampleOutput,
            handler=handler
        )
        
        with pytest.raises(ValueError, match="already registered"):
            registry.register(
                name="test.tool",
                description="Duplicate tool",
                input_schema=SampleInput,
                output_schema=SampleOutput,
                handler=handler
            )
    
    def test_get_nonexistent_returns_none(self):
        """Test getting a nonexistent tool returns None."""
        registry = ToolRegistry()
        assert registry.get("nonexistent.tool") is None
    
    def test_list_tools(self):
        """Test listing all registered tools."""
        registry = ToolRegistry()
        
        async def handler(params: SampleInput) -> SampleOutput:
            return SampleOutput(result="test")
        
        registry.register(
            name="test.tool1",
            description="Tool 1",
            input_schema=SampleInput,
            output_schema=SampleOutput,
            handler=handler
        )
        registry.register(
            name="test.tool2",
            description="Tool 2",
            input_schema=SampleInput,
            output_schema=SampleOutput,
            handler=handler
        )
        
        tools = registry.list_tools()
        assert len(tools) == 2
        names = [t.name for t in tools]
        assert "test.tool1" in names
        assert "test.tool2" in names
    
    def test_get_manifest(self):
        """Test getting tool manifest for API."""
        registry = ToolRegistry()
        
        async def handler(params: SampleInput) -> SampleOutput:
            return SampleOutput(result="test")
        
        registry.register(
            name="test.tool",
            description="A test tool",
            input_schema=SampleInput,
            output_schema=SampleOutput,
            handler=handler,
            tags=["test", "sample"]
        )
        
        manifest = registry.get_manifest()
        assert len(manifest) == 1
        
        tool_manifest = manifest[0]
        assert tool_manifest["name"] == "test.tool"
        assert tool_manifest["description"] == "A test tool"
        assert tool_manifest["tags"] == ["test", "sample"]
        assert "parameters" in tool_manifest
        assert "returns" in tool_manifest
    
    @pytest.mark.asyncio
    async def test_execute_tool(self):
        """Test executing a registered tool."""
        registry = ToolRegistry()
        
        async def handler(params: SampleInput) -> SampleOutput:
            return SampleOutput(result=f"Hello {params.name} x{params.count}")
        
        registry.register(
            name="test.tool",
            description="A test tool",
            input_schema=SampleInput,
            output_schema=SampleOutput,
            handler=handler
        )
        
        result = await registry.execute("test.tool", {"name": "World", "count": 3})
        assert result["result"] == "Hello World x3"
    
    @pytest.mark.asyncio
    async def test_execute_nonexistent_raises(self):
        """Test executing nonexistent tool raises error."""
        registry = ToolRegistry()
        
        with pytest.raises(ValueError, match="not found"):
            await registry.execute("nonexistent.tool", {})
    
    @pytest.mark.asyncio
    async def test_execute_with_invalid_params(self):
        """Test executing with invalid params raises validation error."""
        registry = ToolRegistry()
        
        async def handler(params: SampleInput) -> SampleOutput:
            return SampleOutput(result="test")
        
        registry.register(
            name="test.tool",
            description="A test tool",
            input_schema=SampleInput,
            output_schema=SampleOutput,
            handler=handler
        )
        
        # Missing required field 'name'
        with pytest.raises(Exception):  # Pydantic ValidationError
            await registry.execute("test.tool", {"count": 5})


class TestToolDecorator:
    """Tests for @tool decorator."""
    
    def test_decorator_registers_tool(self):
        """Test that decorator registers the tool."""
        # Note: This uses the global registry
        registry = get_registry()
        initial_count = len(registry.list_tools())
        
        @tool(
            name="decorator.test",
            description="Decorator test tool",
            input_schema=SampleInput,
            output_schema=SampleOutput,
            tags=["decorator"]
        )
        async def decorated_handler(params: SampleInput) -> SampleOutput:
            return SampleOutput(result=f"Decorated: {params.name}")
        
        # Tool should be registered
        assert registry.get("decorator.test") is not None
        assert len(registry.list_tools()) == initial_count + 1

