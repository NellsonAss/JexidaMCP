"""Shared utilities for Azure tools.

Provides:
- Command sanitization to prevent shell injection
- Azure CLI path detection
- Common validation functions
"""

import re
import shutil
from typing import List, Tuple

from config import get_settings


# Dangerous shell patterns that could lead to command injection
DANGEROUS_PATTERNS = [
    r";",           # Command separator
    r"&&",          # AND operator
    r"\|\|",        # OR operator
    r"\|",          # Pipe
    r">",           # Output redirection
    r"<",           # Input redirection
    r"`",           # Backtick command substitution
    r"\$\(",        # $() command substitution
    r"\$\{",        # ${} variable expansion (complex)
    r"\n",          # Newline
    r"\r",          # Carriage return
]

# Compile patterns for efficiency
DANGEROUS_REGEX = re.compile("|".join(DANGEROUS_PATTERNS))


class CommandSanitizationError(Exception):
    """Raised when a command contains dangerous patterns."""
    pass


class CommandLengthError(Exception):
    """Raised when a command exceeds maximum length."""
    pass


def sanitize_command(command: str) -> str:
    """Sanitize an Azure CLI command to prevent shell injection.
    
    Args:
        command: The command string (everything after 'az')
        
    Returns:
        Sanitized command string
        
    Raises:
        CommandSanitizationError: If dangerous patterns detected
        CommandLengthError: If command exceeds maximum length
    """
    settings = get_settings()
    
    # Check length
    if len(command) > settings.azure_command_max_length:
        raise CommandLengthError(
            f"Command length ({len(command)}) exceeds maximum ({settings.azure_command_max_length})"
        )
    
    # Check for dangerous patterns
    if DANGEROUS_REGEX.search(command):
        # Find which pattern matched for better error message
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, command):
                readable_pattern = pattern.replace("\\", "")
                raise CommandSanitizationError(
                    f"Command contains dangerous pattern: '{readable_pattern}'"
                )
    
    # Strip leading/trailing whitespace
    command = command.strip()
    
    # Ensure command doesn't start with dangerous characters
    if command.startswith("-"):
        # Allow this as it's common for az commands
        pass
    
    return command


def validate_subscription_id(subscription_id: str) -> bool:
    """Validate Azure subscription ID format.
    
    Azure subscription IDs are GUIDs in the format:
    xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    
    Args:
        subscription_id: The subscription ID to validate
        
    Returns:
        True if valid, False otherwise
    """
    guid_pattern = re.compile(
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    )
    return bool(guid_pattern.match(subscription_id))


def get_azure_cli_path() -> str:
    """Get the path to the Azure CLI binary.
    
    First checks settings, then falls back to system PATH.
    
    Returns:
        Path to Azure CLI binary
        
    Raises:
        FileNotFoundError: If Azure CLI not found
    """
    settings = get_settings()
    
    # Check configured path first
    if settings.azure_cli_path != "az":
        return settings.azure_cli_path
    
    # Try to find in PATH
    az_path = shutil.which("az")
    if az_path:
        return az_path
    
    # Common installation paths
    common_paths = [
        "/usr/bin/az",
        "/usr/local/bin/az",
        "/opt/az/bin/az",
    ]
    
    for path in common_paths:
        if shutil.which(path):
            return path
    
    raise FileNotFoundError(
        "Azure CLI (az) not found. Install it or set AZURE_CLI_PATH."
    )


def build_az_command(
    command: str,
    subscription_id: str = None
) -> List[str]:
    """Build a complete Azure CLI command as a list of arguments.
    
    Args:
        command: The command string (everything after 'az')
        subscription_id: Optional subscription ID to use
        
    Returns:
        List of command arguments suitable for subprocess
    """
    az_path = get_azure_cli_path()
    
    # Start with az path
    args = [az_path]
    
    # Add subscription if provided
    if subscription_id:
        args.extend(["--subscription", subscription_id])
    
    # Split command into arguments
    # Use shlex-like splitting but simpler since we've sanitized
    args.extend(command.split())
    
    return args


def parse_az_output(stdout: str, stderr: str, exit_code: int) -> Tuple[bool, str]:
    """Parse Azure CLI output to determine success/failure.
    
    Args:
        stdout: Standard output from command
        stderr: Standard error from command
        exit_code: Exit code from command
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    if exit_code == 0:
        return True, stdout
    
    # Check for common error patterns
    error_message = stderr or stdout
    
    if "az login" in error_message.lower():
        return False, "Azure CLI not logged in. Run 'az login' first."
    
    if "subscription" in error_message.lower() and "not found" in error_message.lower():
        return False, "Subscription not found or not accessible."
    
    return False, error_message

