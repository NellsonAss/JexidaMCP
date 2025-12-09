"""Tests for the agent module, focusing on parse_response."""

import unittest
from unittest.mock import MagicMock

from jexida_cli.agent import Agent


class TestAgentParseResponse(unittest.TestCase):
    """Tests for Agent._parse_response method."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_ssh = MagicMock()
        self.mock_ssh.connection_string = "test@host"
        self.agent = Agent(self.mock_ssh, "test-model")

    def test_parse_shell_command_with_target_ssh(self):
        """Test parsing a shell command with SSH target."""
        response = '{"type": "shell", "target": "ssh", "command": "ls -la", "reason": "List files"}'
        
        response_type, data = self.agent._parse_response(response)
        
        self.assertEqual(response_type, "shell")
        self.assertEqual(data["command"], "ls -la")
        self.assertEqual(data["target"], "ssh")
        self.assertEqual(data["reason"], "List files")

    def test_parse_shell_command_with_target_local(self):
        """Test parsing a shell command with local target."""
        response = '{"type": "shell", "target": "local", "command": "git status", "reason": "Check git"}'
        
        response_type, data = self.agent._parse_response(response)
        
        self.assertEqual(response_type, "shell")
        self.assertEqual(data["command"], "git status")
        self.assertEqual(data["target"], "local")

    def test_parse_shell_command_without_target_defaults_missing(self):
        """Test parsing a shell command without target (target should be absent in parsed data)."""
        response = '{"type": "shell", "command": "echo hello", "reason": "Test"}'
        
        response_type, data = self.agent._parse_response(response)
        
        self.assertEqual(response_type, "shell")
        self.assertEqual(data["command"], "echo hello")
        # Target is not in the response, so it won't be in data
        # The main.py code defaults it to "ssh" when accessing
        self.assertNotIn("target", data)

    def test_parse_answer_response(self):
        """Test parsing an answer response."""
        response = '{"type": "answer", "text": "This is the answer."}'
        
        response_type, data = self.agent._parse_response(response)
        
        self.assertEqual(response_type, "answer")
        self.assertEqual(data["text"], "This is the answer.")

    def test_parse_read_file_response(self):
        """Test parsing a read_file response."""
        response = '{"type": "read_file", "path": "test.py", "reason": "Need to examine"}'
        
        response_type, data = self.agent._parse_response(response)
        
        self.assertEqual(response_type, "read_file")
        self.assertEqual(data["path"], "test.py")
        self.assertEqual(data["reason"], "Need to examine")

    def test_parse_json_with_surrounding_text(self):
        """Test parsing JSON embedded in surrounding text."""
        response = 'Here is my response:\n{"type": "shell", "command": "pwd", "reason": "Show directory"}\nDone!'
        
        response_type, data = self.agent._parse_response(response)
        
        self.assertEqual(response_type, "shell")
        self.assertEqual(data["command"], "pwd")

    def test_parse_plain_text_fallback(self):
        """Test that plain text falls back to plain type."""
        response = "This is just plain text without any JSON."
        
        response_type, data = self.agent._parse_response(response)
        
        self.assertEqual(response_type, "plain")
        self.assertIn("text", data)
        self.assertEqual(data["text"], response)

    def test_parse_invalid_json_fallback(self):
        """Test that invalid JSON falls back to plain type."""
        response = '{"type": "shell", "command": "test" invalid json}'
        
        response_type, data = self.agent._parse_response(response)
        
        self.assertEqual(response_type, "plain")

    def test_parse_json_without_type_fallback(self):
        """Test that JSON without type field falls back to plain."""
        response = '{"command": "ls", "reason": "test"}'
        
        response_type, data = self.agent._parse_response(response)
        
        self.assertEqual(response_type, "plain")


class TestAgentAddToolResult(unittest.TestCase):
    """Tests for Agent.add_tool_result method."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_ssh = MagicMock()
        self.mock_ssh.connection_string = "test@host"
        self.agent = Agent(self.mock_ssh, "test-model")

    def test_add_tool_result_ssh_target(self):
        """Test adding tool result with SSH target."""
        self.agent.add_tool_result("ls", 0, "file1\nfile2", "", target="ssh")
        
        self.assertEqual(len(self.agent.conversation_history), 1)
        result = self.agent.conversation_history[0]
        self.assertEqual(result["role"], "tool")
        self.assertIn("remote", result["content"])
        self.assertIn("ls", result["content"])
        self.assertIn("Exit code: 0", result["content"])

    def test_add_tool_result_local_target(self):
        """Test adding tool result with local target."""
        self.agent.add_tool_result("git status", 0, "On branch main", "", target="local")
        
        self.assertEqual(len(self.agent.conversation_history), 1)
        result = self.agent.conversation_history[0]
        self.assertEqual(result["role"], "tool")
        self.assertIn("local", result["content"])
        self.assertIn("git status", result["content"])

    def test_add_tool_result_default_target(self):
        """Test adding tool result with default target (ssh)."""
        self.agent.add_tool_result("pwd", 0, "/home/user", "")
        
        result = self.agent.conversation_history[0]
        self.assertIn("remote", result["content"])

    def test_add_tool_result_with_error(self):
        """Test adding tool result with stderr."""
        self.agent.add_tool_result("invalid_cmd", 1, "", "command not found", target="local")
        
        result = self.agent.conversation_history[0]
        self.assertIn("Error:", result["content"])
        self.assertIn("command not found", result["content"])
        self.assertIn("Exit code: 1", result["content"])


if __name__ == "__main__":
    unittest.main()








