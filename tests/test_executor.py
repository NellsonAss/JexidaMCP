"""Tests for the executor module."""

import unittest
from unittest.mock import MagicMock, patch

from jexida_cli.executor import LocalExecutor, SSHExecutor


class TestLocalExecutor(unittest.TestCase):
    """Tests for LocalExecutor class."""

    def test_run_successful_command(self):
        """Test running a successful command."""
        executor = LocalExecutor()
        exit_code, stdout, stderr = executor.run("echo hello")
        
        self.assertEqual(exit_code, 0)
        self.assertIn("hello", stdout)
        self.assertEqual(stderr, "")

    def test_run_command_with_nonzero_exit(self):
        """Test running a command that fails."""
        executor = LocalExecutor()
        # Use a command that will fail
        exit_code, stdout, stderr = executor.run("exit 1")
        
        self.assertNotEqual(exit_code, 0)

    def test_run_command_with_stderr(self):
        """Test running a command that writes to stderr."""
        executor = LocalExecutor()
        # Redirect to stderr
        exit_code, stdout, stderr = executor.run("echo error 1>&2")
        
        self.assertEqual(exit_code, 0)
        self.assertIn("error", stderr)

    @patch('jexida_cli.executor.subprocess.Popen')
    def test_run_timeout(self, mock_popen):
        """Test command timeout handling."""
        import subprocess
        
        mock_process = MagicMock()
        # First call to communicate raises TimeoutExpired
        # Second call (after kill) returns successfully
        mock_process.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd="test", timeout=1),
            ("", "")  # After kill, communicate returns
        ]
        mock_process.kill = MagicMock()
        mock_popen.return_value = mock_process
        
        executor = LocalExecutor(timeout=1)
        exit_code, stdout, stderr = executor.run("sleep 10")
        
        self.assertEqual(exit_code, 124)
        self.assertIn("timed out", stderr)
        mock_process.kill.assert_called_once()

    @patch('jexida_cli.executor.subprocess.Popen')
    def test_run_exception(self, mock_popen):
        """Test handling of unexpected exceptions."""
        mock_popen.side_effect = OSError("Test error")
        
        executor = LocalExecutor()
        exit_code, stdout, stderr = executor.run("test")
        
        self.assertEqual(exit_code, 1)
        self.assertIn("error", stderr.lower())


class TestSSHExecutor(unittest.TestCase):
    """Tests for SSHExecutor class."""

    def test_run_delegates_to_ssh_client(self):
        """Test that run() delegates to SSHClient.execute_command()."""
        mock_ssh = MagicMock()
        mock_ssh.execute_command.return_value = ("output", "error", 0)
        
        executor = SSHExecutor(mock_ssh)
        exit_code, stdout, stderr = executor.run("ls -la")
        
        mock_ssh.execute_command.assert_called_once_with("ls -la")
        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout, "output")
        self.assertEqual(stderr, "error")

    def test_run_returns_correct_order(self):
        """Test that run() returns (exit_code, stdout, stderr) in correct order."""
        mock_ssh = MagicMock()
        # SSHClient.execute_command returns (stdout, stderr, exit_code)
        mock_ssh.execute_command.return_value = ("stdout_val", "stderr_val", 42)
        
        executor = SSHExecutor(mock_ssh)
        exit_code, stdout, stderr = executor.run("test")
        
        # SSHExecutor.run should return (exit_code, stdout, stderr)
        self.assertEqual(exit_code, 42)
        self.assertEqual(stdout, "stdout_val")
        self.assertEqual(stderr, "stderr_val")

    def test_open_shell_delegates_to_ssh_client(self):
        """Test that open_shell() delegates to SSHClient.open_shell()."""
        mock_ssh = MagicMock()
        
        executor = SSHExecutor(mock_ssh)
        executor.open_shell()
        
        mock_ssh.open_shell.assert_called_once()


if __name__ == "__main__":
    unittest.main()

