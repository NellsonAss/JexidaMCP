"""SSH executor for running commands on worker nodes.

This module provides the WorkerSSHExecutor class that handles SSH-based
command execution on remote worker nodes from the MCP server.
"""

import base64
import logging
import subprocess
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp_tools_core.models import WorkerNode

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of executing a command on a worker node."""

    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int

    @property
    def success(self) -> bool:
        """Check if the command succeeded (exit code 0)."""
        return self.exit_code == 0


class WorkerSSHExecutor:
    """Execute commands on worker nodes via SSH.

    This executor uses subprocess to run SSH commands from the MCP server
    to remote worker nodes. Commands are base64-encoded to avoid shell
    interpretation issues.
    """

    def __init__(self, timeout: int = 300):
        """Initialize the executor.

        Args:
            timeout: Command timeout in seconds (default: 5 minutes)
        """
        self.timeout = timeout

    def run_command(self, node: "WorkerNode", command: str) -> ExecutionResult:
        """Execute a command on a worker node via SSH.

        Args:
            node: WorkerNode instance with connection details
            command: Shell command to execute

        Returns:
            ExecutionResult with stdout, stderr, exit_code, and duration
        """
        start_time = time.perf_counter()

        # Build connection string
        connection_string = f"{node.user}@{node.host}"

        # Base64 encode the command to avoid shell interpretation issues
        # This is the same pattern used in jexida_cli/ssh_client.py
        command_bytes = command.encode("utf-8")
        command_b64 = base64.b64encode(command_bytes).decode("ascii")
        wrapped_command = f"echo {command_b64} | base64 -d | sh"

        # Build SSH command with port if non-standard
        # Use keys from /opt/jexida-mcp/.ssh/ since the service has ProtectHome=true
        ssh_key_path = "/opt/jexida-mcp/.ssh/id_ed25519"
        known_hosts_path = "/opt/jexida-mcp/.ssh/known_hosts"
        
        ssh_args = ["ssh"]
        if node.ssh_port != 22:
            ssh_args.extend(["-p", str(node.ssh_port)])
        ssh_args.extend([
            "-i", ssh_key_path,
            "-o", f"UserKnownHostsFile={known_hosts_path}",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ConnectTimeout=10",
            "-o", "BatchMode=yes",
            connection_string,
            wrapped_command,
        ])

        logger.info(f"Executing on {node.name} ({connection_string}): {command[:100]}...")

        try:
            result = subprocess.run(
                ssh_args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
            )

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            logger.info(
                f"Command on {node.name} completed with exit code {result.returncode} "
                f"in {duration_ms}ms"
            )

            return ExecutionResult(
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                duration_ms=duration_ms,
            )

        except subprocess.TimeoutExpired:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"Command on {node.name} timed out after {self.timeout}s")
            return ExecutionResult(
                stdout="",
                stderr=f"Command timed out after {self.timeout} seconds",
                exit_code=124,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"SSH error on {node.name}: {e}")
            return ExecutionResult(
                stdout="",
                stderr=f"SSH error: {str(e)}",
                exit_code=1,
                duration_ms=duration_ms,
            )

    def check_connectivity(self, node: "WorkerNode") -> ExecutionResult:
        """Check if a worker node is reachable via SSH.

        Runs a simple 'echo' command to verify connectivity and measure latency.

        Args:
            node: WorkerNode instance to check

        Returns:
            ExecutionResult from the connectivity check
        """
        return self.run_command(node, "echo 'pong' && hostname && uname -a")

    def get_node_info(self, node: "WorkerNode") -> ExecutionResult:
        """Get detailed information about a worker node.

        Args:
            node: WorkerNode instance

        Returns:
            ExecutionResult with system information
        """
        info_command = """
echo "=== System Info ==="
hostname
uname -a
echo ""
echo "=== Python Version ==="
python3 --version 2>/dev/null || echo "Python3 not found"
echo ""
echo "=== Disk Space ==="
df -h / 2>/dev/null | tail -1
echo ""
echo "=== Memory ==="
free -h 2>/dev/null | grep Mem || echo "free command not available"
echo ""
echo "=== Job Directories ==="
ls -la /opt/jexida-jobs 2>/dev/null || echo "/opt/jexida-jobs does not exist"
ls -la /var/log/jexida-jobs 2>/dev/null || echo "/var/log/jexida-jobs does not exist"
"""
        return self.run_command(node, info_command.strip())

