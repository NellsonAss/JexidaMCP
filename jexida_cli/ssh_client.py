"""SSH client wrapper for executing commands on remote server."""

import subprocess
import base64
from typing import Tuple


class SSHClient:
    """Handles SSH connections and command execution."""

    def __init__(self, host: str, user: str):
        """
        Initialize SSH client.

        Args:
            host: Remote host address
            user: SSH username
        """
        self.host = host
        self.user = user
        self.connection_string = f"{user}@{host}"

    @staticmethod
    def _escape_command(command: str) -> str:
        """
        Escape a command for safe execution within single quotes.
        
        Args:
            command: Command to escape
            
        Returns:
            Properly escaped command string (ready to be wrapped in single quotes)
        """
        # Escape single quotes by ending the string, adding escaped quote, and restarting
        # This handles: ' -> '\''
        # The result should be wrapped in single quotes by the caller
        escaped = command.replace("'", "'\\''")
        return escaped

    def execute_command(self, command: str) -> Tuple[str, str, int]:
        """
        Execute a command on the remote server via SSH.

        Args:
            command: Shell command to execute

        Returns:
            Tuple of (stdout, stderr, exit_code)
        """
        # Use base64 encoding to avoid all shell interpretation issues
        # This prevents bash history expansion, special character issues, etc.
        # Decode on remote side: echo <base64> | base64 -d | sh
        command_bytes = command.encode('utf-8')
        command_b64 = base64.b64encode(command_bytes).decode('ascii')
        wrapped_command = f"echo {command_b64} | base64 -d | sh"
        
        ssh_command = [
            "ssh",
            self.connection_string,
            wrapped_command,
        ]

        try:
            result = subprocess.run(
                ssh_command,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',  # Replace invalid UTF-8 sequences
                timeout=300,  # 5 minute timeout
            )
            return (
                result.stdout,
                result.stderr,
                result.returncode,
            )
        except subprocess.TimeoutExpired:
            return ("", "Command timed out after 5 minutes", 124)
        except Exception as e:
            return ("", f"SSH error: {str(e)}", 1)

    def execute_ollama(self, prompt: str, model: str) -> str:
        """
        Execute Ollama with a prompt via SSH.

        Args:
            prompt: The prompt to send to Ollama
            model: The Ollama model name (e.g., "phi3")

        Returns:
            Raw text response from Ollama
        """
        # Pass prompt via stdin to avoid escaping issues
        # SSH command: pipe stdin to ollama
        ssh_command = [
            "ssh",
            self.connection_string,
            f"ollama run {model}",
        ]

        try:
            result = subprocess.run(
                ssh_command,
                input=prompt,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',  # Replace invalid UTF-8 sequences
                timeout=300,  # 5 minute timeout
            )

            if result.returncode != 0:
                return f"[Error: Ollama execution failed]\nExit code: {result.returncode}\n{result.stderr}"

            return result.stdout
        except subprocess.TimeoutExpired:
            return "[Error: Ollama execution timed out after 5 minutes]"
        except Exception as e:
            return f"[Error: Ollama execution failed: {str(e)}]"

    def open_interactive_shell(self) -> None:
        """
        Open an interactive SSH shell session.

        Blocks until the user exits the SSH session.
        """
        ssh_command = ["ssh", self.connection_string]

        try:
            # Run SSH interactively (no capture_output)
            subprocess.run(ssh_command, check=False)
        except KeyboardInterrupt:
            print("\n[SSH session interrupted]")
        except Exception as e:
            print(f"[Error opening SSH session: {e}]")

    def open_shell(self) -> None:
        """
        Open an interactive SSH shell session attached to the user's TTY.

        Uses subprocess.call() for direct TTY attachment.
        Blocks until the user exits the SSH session.
        """
        ssh_command = ["ssh", self.connection_string]

        try:
            # Use subprocess.call for direct TTY attachment
            subprocess.call(ssh_command)
        except KeyboardInterrupt:
            print("\n[SSH session interrupted]")
        except Exception as e:
            print(f"[Error opening SSH session: {e}]")

