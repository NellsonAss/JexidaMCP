"""Tests for azure_cli.run tool."""

import pytest
from unittest.mock import AsyncMock, patch

from mcp_tools.azure.cli import AzureCliInput, AzureCliOutput, run_azure_cli
from mcp_tools.azure.utils import (
    CommandLengthError,
    CommandSanitizationError,
    sanitize_command,
    validate_subscription_id,
)


class TestSubscriptionValidation:
    """Tests for subscription ID validation."""
    
    def test_valid_subscription_id(self):
        """Test valid GUID format is accepted."""
        valid_id = "12345678-1234-1234-1234-123456789abc"
        assert validate_subscription_id(valid_id) is True
    
    def test_invalid_subscription_id_format(self):
        """Test invalid formats are rejected."""
        invalid_ids = [
            "not-a-guid",
            "12345678-1234-1234-1234",  # Too short
            "12345678-1234-1234-1234-123456789abcdef",  # Too long
            "12345678_1234_1234_1234_123456789abc",  # Wrong separator
            "",
            "   ",
        ]
        for invalid_id in invalid_ids:
            assert validate_subscription_id(invalid_id) is False


class TestCommandSanitization:
    """Tests for command sanitization."""
    
    def test_valid_commands(self):
        """Test that valid commands pass sanitization."""
        valid_commands = [
            "group list --output json",
            "vm list -g my-resource-group",
            "account show",
            "webapp create --name myapp --resource-group myrg --plan myplan",
            "storage account list --query '[].name'",
        ]
        for cmd in valid_commands:
            result = sanitize_command(cmd)
            assert result == cmd.strip()
    
    def test_semicolon_injection(self):
        """Test that semicolon injection is blocked."""
        with pytest.raises(CommandSanitizationError, match="dangerous pattern"):
            sanitize_command("group list; rm -rf /")
    
    def test_and_injection(self):
        """Test that && injection is blocked."""
        with pytest.raises(CommandSanitizationError, match="dangerous pattern"):
            sanitize_command("group list && cat /etc/passwd")
    
    def test_or_injection(self):
        """Test that || injection is blocked."""
        with pytest.raises(CommandSanitizationError, match="dangerous pattern"):
            sanitize_command("group list || echo pwned")
    
    def test_pipe_injection(self):
        """Test that pipe injection is blocked."""
        with pytest.raises(CommandSanitizationError, match="dangerous pattern"):
            sanitize_command("group list | grep secret")
    
    def test_redirect_injection(self):
        """Test that redirect injection is blocked."""
        with pytest.raises(CommandSanitizationError, match="dangerous pattern"):
            sanitize_command("group list > /tmp/output")
        with pytest.raises(CommandSanitizationError, match="dangerous pattern"):
            sanitize_command("group list < /etc/passwd")
    
    def test_backtick_injection(self):
        """Test that backtick injection is blocked."""
        with pytest.raises(CommandSanitizationError, match="dangerous pattern"):
            sanitize_command("group list `whoami`")
    
    def test_subshell_injection(self):
        """Test that $() injection is blocked."""
        with pytest.raises(CommandSanitizationError, match="dangerous pattern"):
            sanitize_command("group list $(cat /etc/passwd)")
    
    def test_command_length_limit(self):
        """Test that overly long commands are rejected."""
        # Create a command longer than default limit (4096)
        long_command = "group list " + "a" * 5000
        with pytest.raises(CommandLengthError, match="exceeds maximum"):
            sanitize_command(long_command)


class TestAzureCliInput:
    """Tests for AzureCliInput schema validation."""
    
    def test_valid_input(self):
        """Test valid input is accepted."""
        input_data = AzureCliInput(
            subscription_id="12345678-1234-1234-1234-123456789abc",
            command="group list --output json",
            dry_run=False
        )
        assert input_data.subscription_id == "12345678-1234-1234-1234-123456789abc"
        assert input_data.command == "group list --output json"
        assert input_data.dry_run is False
    
    def test_invalid_subscription_rejected(self):
        """Test invalid subscription ID is rejected."""
        with pytest.raises(ValueError, match="Invalid subscription ID"):
            AzureCliInput(
                subscription_id="not-a-valid-guid",
                command="group list"
            )
    
    def test_dry_run_defaults_false(self):
        """Test dry_run defaults to False."""
        input_data = AzureCliInput(
            subscription_id="12345678-1234-1234-1234-123456789abc",
            command="group list"
        )
        assert input_data.dry_run is False


class TestAzureCliExecution:
    """Tests for azure_cli.run execution."""
    
    @pytest.mark.asyncio
    async def test_dry_run_returns_command(self):
        """Test dry run mode returns command without executing."""
        params = AzureCliInput(
            subscription_id="12345678-1234-1234-1234-123456789abc",
            command="group list --output json",
            dry_run=True
        )
        
        with patch("mcp_tools.azure.cli.build_az_command") as mock_build:
            mock_build.return_value = ["az", "--subscription", params.subscription_id, "group", "list", "--output", "json"]
            
            result = await run_azure_cli(params)
        
        assert result.exit_code == 0
        assert result.command_executed is not None
        assert "az" in result.command_executed
    
    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """Test successful command execution."""
        params = AzureCliInput(
            subscription_id="12345678-1234-1234-1234-123456789abc",
            command="group list --output json",
            dry_run=False
        )
        
        with patch("mcp_tools.azure.cli.build_az_command") as mock_build, \
             patch("asyncio.create_subprocess_exec") as mock_exec, \
             patch("asyncio.wait_for") as mock_wait:
            
            mock_build.return_value = ["az", "group", "list"]
            
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_exec.return_value = mock_process
            mock_wait.return_value = (b'[{"name": "test-rg"}]', b'')
            
            result = await run_azure_cli(params)
        
        assert result.exit_code == 0
        assert "test-rg" in result.stdout
    
    @pytest.mark.asyncio
    async def test_command_sanitization_error(self):
        """Test that dangerous commands are rejected."""
        params = AzureCliInput(
            subscription_id="12345678-1234-1234-1234-123456789abc",
            command="group list; rm -rf /",
            dry_run=False
        )
        
        result = await run_azure_cli(params)
        
        assert result.exit_code == -2
        assert "rejected" in result.stderr.lower()
        assert "dangerous" in result.stderr.lower()
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test command timeout is handled properly."""
        params = AzureCliInput(
            subscription_id="12345678-1234-1234-1234-123456789abc",
            command="group list",
            dry_run=False
        )
        
        import asyncio
        
        with patch("mcp_tools.azure.cli.build_az_command") as mock_build, \
             patch("asyncio.create_subprocess_exec") as mock_exec, \
             patch("asyncio.wait_for") as mock_wait:
            
            mock_build.return_value = ["az", "group", "list"]
            
            mock_process = AsyncMock()
            mock_process.kill = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b'', b''))
            mock_exec.return_value = mock_process
            mock_wait.side_effect = asyncio.TimeoutError()
            
            result = await run_azure_cli(params)
        
        assert result.exit_code == -1
        assert "timed out" in result.stderr.lower()

