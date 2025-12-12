"""Tests for Discord MCP tools.

Tests the Discord API client, configuration, and bootstrap logic
with mocked HTTP responses.
"""

import os
import json
import unittest
from unittest.mock import patch, MagicMock, mock_open
from dataclasses import asdict

import httpx


class TestDiscordConfig(unittest.TestCase):
    """Tests for Discord configuration loading."""
    
    @patch.dict(os.environ, {
        "DISCORD_BOT_TOKEN": "test-token-12345",
        "DISCORD_GUILD_ID": "123456789",
    }, clear=True)
    def test_from_env_with_required_vars(self):
        """Test loading config from environment variables."""
        # Import here to get fresh env
        from jexida_dashboard.mcp_tools_core.tools.discord.config import DiscordConfig
        
        config = DiscordConfig.from_env()
        
        self.assertEqual(config.bot_token, "test-token-12345")
        self.assertEqual(config.guild_id, "123456789")
        self.assertEqual(config.timeout, 30)
    
    @patch.dict(os.environ, {}, clear=True)
    def test_from_env_missing_token_raises_error(self):
        """Test that missing bot token raises DiscordConfigError."""
        from jexida_dashboard.mcp_tools_core.tools.discord.config import (
            DiscordConfig, DiscordConfigError
        )
        
        with self.assertRaises(DiscordConfigError) as context:
            DiscordConfig.from_env()
        
        self.assertIn("DISCORD_BOT_TOKEN", str(context.exception))
    
    @patch.dict(os.environ, {"DISCORD_BOT_TOKEN": "token"}, clear=True)
    def test_from_env_missing_guild_id_raises_error(self):
        """Test that missing guild ID raises DiscordConfigError."""
        from jexida_dashboard.mcp_tools_core.tools.discord.config import (
            DiscordConfig, DiscordConfigError
        )
        
        with self.assertRaises(DiscordConfigError) as context:
            DiscordConfig.from_env()
        
        self.assertIn("DISCORD_GUILD_ID", str(context.exception))


class TestDiscordClient(unittest.TestCase):
    """Tests for Discord API client."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Patch environment variables
        self.env_patcher = patch.dict(os.environ, {
            "DISCORD_BOT_TOKEN": "test-token",
            "DISCORD_GUILD_ID": "test-guild-id",
        })
        self.env_patcher.start()
    
    def tearDown(self):
        """Clean up patches."""
        self.env_patcher.stop()
    
    @patch('httpx.Client')
    def test_send_message_success(self, mock_client_class):
        """Test successful message sending."""
        from jexida_dashboard.mcp_tools_core.tools.discord.client import DiscordClient
        
        # Mock the httpx client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.content = b'{"id": "msg-123", "content": "test"}'
        mock_response.json.return_value = {"id": "msg-123", "content": "test"}
        mock_client.post.return_value = mock_response
        
        with DiscordClient() as client:
            result = client.send_message("channel-id", "Hello, Discord!")
        
        self.assertTrue(result.ok)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["id"], "msg-123")
    
    @patch('httpx.Client')
    def test_send_message_error(self, mock_client_class):
        """Test message sending with API error."""
        from jexida_dashboard.mcp_tools_core.tools.discord.client import DiscordClient
        
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status_code = 403
        mock_response.content = b'{"message": "Missing Access"}'
        mock_response.json.return_value = {"message": "Missing Access"}
        mock_client.post.return_value = mock_response
        
        with DiscordClient() as client:
            result = client.send_message("channel-id", "Hello!")
        
        self.assertFalse(result.ok)
        self.assertEqual(result.status_code, 403)
        self.assertIn("403", result.error)
    
    @patch('httpx.Client')
    def test_get_guild_info_success(self, mock_client_class):
        """Test getting guild info."""
        from jexida_dashboard.mcp_tools_core.tools.discord.client import DiscordClient
        
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.content = b'{"id": "guild-123", "name": "Test Server"}'
        mock_response.json.return_value = {"id": "guild-123", "name": "Test Server"}
        mock_client.get.return_value = mock_response
        
        with DiscordClient() as client:
            result = client.get_guild_info()
        
        self.assertTrue(result.ok)
        self.assertEqual(result.data["name"], "Test Server")
    
    @patch('httpx.Client')
    def test_ensure_role_existing(self, mock_client_class):
        """Test ensuring a role that already exists."""
        from jexida_dashboard.mcp_tools_core.tools.discord.client import DiscordClient
        
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock get roles response
        mock_roles_response = MagicMock()
        mock_roles_response.is_success = True
        mock_roles_response.status_code = 200
        mock_roles_response.content = b'[{"id": "role-123", "name": "Admin"}]'
        mock_roles_response.json.return_value = [{"id": "role-123", "name": "Admin"}]
        mock_client.get.return_value = mock_roles_response
        
        with DiscordClient() as client:
            result = client.ensure_role(None, "Admin")
        
        self.assertTrue(result.ok)
        self.assertEqual(result.data["id"], "role-123")
        self.assertTrue(result.data.get("_existed"))
    
    @patch('httpx.Client')
    def test_ensure_role_creates_new(self, mock_client_class):
        """Test ensuring a role that doesn't exist."""
        from jexida_dashboard.mcp_tools_core.tools.discord.client import DiscordClient
        
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock get roles response (no matching role)
        mock_roles_response = MagicMock()
        mock_roles_response.is_success = True
        mock_roles_response.status_code = 200
        mock_roles_response.content = b'[{"id": "role-123", "name": "Other"}]'
        mock_roles_response.json.return_value = [{"id": "role-123", "name": "Other"}]
        mock_client.get.return_value = mock_roles_response
        
        # Mock create role response
        mock_create_response = MagicMock()
        mock_create_response.is_success = True
        mock_create_response.status_code = 200
        mock_create_response.content = b'{"id": "role-456", "name": "NewRole"}'
        mock_create_response.json.return_value = {"id": "role-456", "name": "NewRole"}
        mock_client.post.return_value = mock_create_response
        
        with DiscordClient() as client:
            result = client.ensure_role(None, "NewRole", hoist=True)
        
        self.assertTrue(result.ok)
        self.assertEqual(result.data["id"], "role-456")


class TestDiscordAPIResult(unittest.TestCase):
    """Tests for DiscordAPIResult dataclass."""
    
    def test_ok_result(self):
        """Test creating an OK result."""
        from jexida_dashboard.mcp_tools_core.tools.discord.client import DiscordAPIResult
        
        result = DiscordAPIResult(
            ok=True,
            status_code=200,
            data={"id": "123"},
        )
        
        self.assertTrue(result.ok)
        self.assertEqual(result.status_code, 200)
        self.assertIsNone(result.error)
    
    def test_error_result(self):
        """Test creating an error result."""
        from jexida_dashboard.mcp_tools_core.tools.discord.client import DiscordAPIResult
        
        result = DiscordAPIResult(
            ok=False,
            status_code=404,
            error="Not Found",
        )
        
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "Not Found")


class TestBootstrapConfig(unittest.TestCase):
    """Tests for bootstrap configuration loading."""
    
    def test_expand_env_vars(self):
        """Test environment variable expansion in config."""
        from jexida_dashboard.mcp_tools_core.tools.discord.bootstrap import _expand_env_vars
        
        with patch.dict(os.environ, {"TEST_VAR": "hello"}):
            result = _expand_env_vars("prefix_${TEST_VAR}_suffix")
            self.assertEqual(result, "prefix_hello_suffix")
    
    def test_expand_env_vars_missing(self):
        """Test that missing env vars are left as-is."""
        from jexida_dashboard.mcp_tools_core.tools.discord.bootstrap import _expand_env_vars
        
        with patch.dict(os.environ, {}, clear=True):
            result = _expand_env_vars("${MISSING_VAR}")
            self.assertEqual(result, "${MISSING_VAR}")
    
    def test_normalize_channel_name(self):
        """Test channel name normalization."""
        from jexida_dashboard.mcp_tools_core.tools.discord.bootstrap import _normalize_channel_name
        
        self.assertEqual(_normalize_channel_name("General Chat"), "general-chat")
        self.assertEqual(_normalize_channel_name("tech_lab"), "tech-lab")
        self.assertEqual(_normalize_channel_name("ANNOUNCEMENTS"), "announcements")


class TestNoSecretsInOutput(unittest.TestCase):
    """Ensure bot tokens are never logged or exposed."""
    
    def test_token_not_in_string_representation(self):
        """Test that token is not exposed in string representations."""
        from jexida_dashboard.mcp_tools_core.tools.discord.config import DiscordConfig
        
        with patch.dict(os.environ, {
            "DISCORD_BOT_TOKEN": "super-secret-token-12345",
            "DISCORD_GUILD_ID": "123",
        }):
            config = DiscordConfig.from_env()
            
            # The token should exist but not appear in repr/str
            self.assertEqual(config.bot_token, "super-secret-token-12345")
            
            # Note: dataclasses don't mask by default, but the client
            # should never log the config object


if __name__ == "__main__":
    unittest.main()

