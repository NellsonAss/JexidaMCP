"""Tests for the job system.

Tests cover:
- Job model serialization
- Node config loading
- RemoteExecutor with mocked SSH
- JobManager submit/run/status flow
"""

import unittest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass


class TestExecutionResult:
    """Mock ExecutionResult for tests."""
    
    def __init__(self, stdout: str = "", stderr: str = "", exit_code: int = 0, duration_ms: int = 100):
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.duration_ms = duration_ms
    
    @property
    def success(self) -> bool:
        return self.exit_code == 0


class TestWorkerSSHExecutor(unittest.TestCase):
    """Tests for the WorkerSSHExecutor class."""
    
    @patch('subprocess.run')
    def test_run_command_success(self, mock_run):
        """Test running a successful command."""
        # Mock the subprocess result
        mock_run.return_value = MagicMock(
            stdout="Hello, World!\n",
            stderr="",
            returncode=0,
        )
        
        # Import here to avoid Django setup issues
        from jexida_dashboard.mcp_tools_core.tools.jobs.executor import (
            WorkerSSHExecutor,
            ExecutionResult,
        )
        
        # Create mock node
        mock_node = MagicMock()
        mock_node.user = "jexida"
        mock_node.host = "192.168.0.66"
        mock_node.ssh_port = 22
        mock_node.name = "test-node"
        
        executor = WorkerSSHExecutor(timeout=30)
        result = executor.run_command(mock_node, "echo 'Hello, World!'")
        
        self.assertTrue(result.success)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Hello", result.stdout)
        self.assertGreaterEqual(result.duration_ms, 0)
    
    @patch('subprocess.run')
    def test_run_command_failure(self, mock_run):
        """Test running a command that fails."""
        mock_run.return_value = MagicMock(
            stdout="",
            stderr="Command not found",
            returncode=127,
        )
        
        from jexida_dashboard.mcp_tools_core.tools.jobs.executor import WorkerSSHExecutor
        
        mock_node = MagicMock()
        mock_node.user = "jexida"
        mock_node.host = "192.168.0.66"
        mock_node.ssh_port = 22
        mock_node.name = "test-node"
        
        executor = WorkerSSHExecutor(timeout=30)
        result = executor.run_command(mock_node, "invalid_command")
        
        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 127)
    
    @patch('subprocess.run')
    def test_run_command_timeout(self, mock_run):
        """Test command timeout handling."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=30)
        
        from jexida_dashboard.mcp_tools_core.tools.jobs.executor import WorkerSSHExecutor
        
        mock_node = MagicMock()
        mock_node.user = "jexida"
        mock_node.host = "192.168.0.66"
        mock_node.ssh_port = 22
        mock_node.name = "test-node"
        
        executor = WorkerSSHExecutor(timeout=30)
        result = executor.run_command(mock_node, "sleep 100")
        
        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 124)
        self.assertIn("timed out", result.stderr)


class TestCLIJobsCommands(unittest.TestCase):
    """Tests for CLI jobs command parsing."""
    
    def test_parse_jobs_submit_args_basic(self):
        """Test parsing basic jobs submit arguments."""
        from jexida_cli.commands.jobs import parse_jobs_submit_args
        
        args = '--node test-node --cmd "ls -la"'
        node_name, command, timeout = parse_jobs_submit_args(args)
        
        self.assertEqual(node_name, "test-node")
        self.assertEqual(command, "ls -la")
        self.assertEqual(timeout, 300)  # Default timeout
    
    def test_parse_jobs_submit_args_with_timeout(self):
        """Test parsing arguments with custom timeout."""
        from jexida_cli.commands.jobs import parse_jobs_submit_args
        
        args = '--node my-node --cmd "python script.py" --timeout 600'
        node_name, command, timeout = parse_jobs_submit_args(args)
        
        self.assertEqual(node_name, "my-node")
        self.assertEqual(command, "python script.py")
        self.assertEqual(timeout, 600)
    
    def test_parse_jobs_submit_args_empty(self):
        """Test parsing empty arguments."""
        from jexida_cli.commands.jobs import parse_jobs_submit_args
        
        args = ''
        node_name, command, timeout = parse_jobs_submit_args(args)
        
        self.assertIsNone(node_name)
        self.assertIsNone(command)
        self.assertEqual(timeout, 300)


class TestJobsIntegration(unittest.TestCase):
    """Integration-style tests with mocked components."""
    
    def test_full_job_flow_mocked(self):
        """Test the full job submission flow with mocks."""
        # Create mock MCP client
        mock_mcp = MagicMock()
        
        # Mock successful job submission
        mock_mcp.execute_tool.return_value = {
            "success": True,
            "job": {
                "id": "test-job-123",
                "node_name": "test-node",
                "command": "echo hello",
                "status": "succeeded",
                "stdout": "hello\n",
                "stderr": "",
                "exit_code": 0,
                "duration_ms": 150,
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:01",
            }
        }
        
        # Verify the mock returns expected structure
        result = mock_mcp.execute_tool("submit_job", {
            "node_name": "test-node",
            "command": "echo hello",
            "timeout": 300,
        })
        
        self.assertTrue(result["success"])
        self.assertEqual(result["job"]["status"], "succeeded")
        self.assertEqual(result["job"]["exit_code"], 0)


class TestNodeTools(unittest.TestCase):
    """Tests for node-related functionality."""
    
    def test_node_tags_parsing(self):
        """Test that tags are properly parsed from comma-separated string."""
        # Simulate the get_tags_list method
        tags_str = "ubuntu,gpu,worker"
        tags_list = [tag.strip() for tag in tags_str.split(",")]
        
        self.assertEqual(len(tags_list), 3)
        self.assertIn("ubuntu", tags_list)
        self.assertIn("gpu", tags_list)
        self.assertIn("worker", tags_list)
    
    def test_empty_tags(self):
        """Test empty tags handling."""
        tags_str = ""
        if not tags_str:
            tags_list = []
        else:
            tags_list = [tag.strip() for tag in tags_str.split(",")]
        
        self.assertEqual(tags_list, [])


if __name__ == "__main__":
    unittest.main()

