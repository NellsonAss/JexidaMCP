"""Command executor abstraction for local, SSH, and MCP execution."""

import subprocess
import json
from abc import ABC, abstractmethod
from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .ssh_client import SSHClient
    from .mcp_client import MCPClient


class Executor(ABC):
    """Abstract base class for command executors."""

    @abstractmethod
    def run(self, command: str) -> Tuple[int, str, str]:
        """Execute a command.

        Args:
            command: Command to execute

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        pass


class LocalExecutor(Executor):
    """Executes commands on the local machine."""

    def __init__(self, timeout: int = 300):
        """Initialize the local executor.

        Args:
            timeout: Command timeout in seconds (default: 5 minutes)
        """
        self.timeout = timeout

    def run(self, command: str) -> Tuple[int, str, str]:
        """Execute a shell command on the local machine.

        Args:
            command: Shell command to execute

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        try:
            result = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
            )
            stdout, stderr = result.communicate(timeout=self.timeout)
            return (result.returncode, stdout, stderr)
        except subprocess.TimeoutExpired:
            result.kill()
            result.communicate()
            return (124, "", "Command timed out")
        except Exception as e:
            return (1, "", f"Local execution error: {str(e)}")


class SSHExecutor(Executor):
    """Executes commands on a remote server via SSH."""

    def __init__(self, ssh_client: "SSHClient"):
        """Initialize the SSH executor.

        Args:
            ssh_client: SSHClient instance for remote execution
        """
        self.ssh_client = ssh_client

    def run(self, command: str) -> Tuple[int, str, str]:
        """Execute a shell command on the remote server via SSH.

        Args:
            command: Shell command to execute

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        stdout, stderr, exit_code = self.ssh_client.execute_command(command)
        return (exit_code, stdout, stderr)

    def open_shell(self) -> None:
        """Open an interactive SSH shell session.

        Delegates to the underlying SSHClient's open_shell method.
        This attaches to the user's TTY for an interactive session.
        """
        self.ssh_client.open_shell()


class MCPExecutor(Executor):
    """Executes tools on the Jexida MCP server."""

    def __init__(self, mcp_client: "MCPClient"):
        """Initialize the MCP executor.

        Args:
            mcp_client: MCPClient instance for API communication
        """
        self.mcp_client = mcp_client

    def run(self, command: str) -> Tuple[int, str, str]:
        """Execute a tool on the MCP server.

        The command is expected to be a JSON string containing
        'tool_name' and 'parameters'.

        Args:
            command: JSON string representing the tool call.

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        try:
            tool_call = json.loads(command)
            tool_name = tool_call.get("tool_name")
            parameters = tool_call.get("parameters", {})

            if not tool_name:
                return (1, "", "MCPExecutor error: 'tool_name' missing from JSON command.")

            result = self.mcp_client.execute_tool(tool_name, parameters)

            if result.get("success", False):
                stdout_content = json.dumps(result, indent=2, ensure_ascii=False)
                return (0, stdout_content, "")
            else:
                stderr_content = json.dumps(result, indent=2, ensure_ascii=False)
                return (1, "", stderr_content)

        except json.JSONDecodeError:
            return (1, "", "MCPExecutor error: Invalid JSON command.")
        except Exception as e:
            return (1, "", f"MCPExecutor unexpected error: {str(e)}")
