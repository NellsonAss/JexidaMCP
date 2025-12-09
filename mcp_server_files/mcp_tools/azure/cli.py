"""Azure CLI tool implementation.

Provides the azure_cli.run tool for executing Azure CLI commands safely.
"""

import asyncio
import subprocess
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from config import get_settings
from logging_config import get_logger, ToolInvocationLogger
from tool_registry import tool

from .utils import (
    CommandLengthError,
    CommandSanitizationError,
    build_az_command,
    sanitize_command,
    validate_subscription_id,
)

logger = get_logger(__name__)


class AzureCliInput(BaseModel):
    """Input schema for azure_cli.run tool."""
    
    subscription_id: str = Field(
        description="Azure subscription ID (GUID format)"
    )
    command: str = Field(
        description="Azure CLI command (everything after 'az', e.g., 'group list --output json')"
    )
    dry_run: bool = Field(
        default=False,
        description="If true, return the command that would be executed without running it"
    )
    
    @field_validator("subscription_id")
    @classmethod
    def validate_subscription(cls, v: str) -> str:
        """Validate subscription ID format."""
        if not validate_subscription_id(v):
            raise ValueError(
                "Invalid subscription ID format. Expected GUID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            )
        return v


class AzureCliOutput(BaseModel):
    """Output schema for azure_cli.run tool."""
    
    stdout: str = Field(
        description="Standard output from the command"
    )
    stderr: str = Field(
        description="Standard error from the command"
    )
    exit_code: int = Field(
        description="Exit code from the command (0 = success)"
    )
    command_executed: Optional[str] = Field(
        default=None,
        description="The full command that was executed (for dry_run mode)"
    )


@tool(
    name="azure_cli.run",
    description="Execute an Azure CLI command safely with subscription context",
    input_schema=AzureCliInput,
    output_schema=AzureCliOutput,
    tags=["azure", "cli"]
)
async def run_azure_cli(params: AzureCliInput) -> AzureCliOutput:
    """Execute an Azure CLI command.
    
    Args:
        params: Validated input parameters
        
    Returns:
        Command execution result
    """
    settings = get_settings()
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start(
        "azure_cli.run",
        subscription_id=params.subscription_id,
        dry_run=params.dry_run
    )
    
    try:
        # Sanitize command
        sanitized_command = sanitize_command(params.command)
        
        # Build full command
        cmd_args = build_az_command(sanitized_command, params.subscription_id)
        command_str = " ".join(cmd_args)
        
        # Dry run mode - return command without executing
        if params.dry_run:
            invocation_logger.success(exit_code=0, dry_run=True)
            return AzureCliOutput(
                stdout="",
                stderr="",
                exit_code=0,
                command_executed=command_str
            )
        
        # Execute command
        process = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=settings.azure_cli_timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            invocation_logger.failure("Command timed out", exit_code=-1)
            return AzureCliOutput(
                stdout="",
                stderr=f"Command timed out after {settings.azure_cli_timeout} seconds",
                exit_code=-1,
                command_executed=command_str
            )
        
        exit_code = process.returncode
        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")
        
        if exit_code == 0:
            invocation_logger.success(exit_code=exit_code)
        else:
            invocation_logger.failure(
                "Command failed",
                exit_code=exit_code
            )
        
        return AzureCliOutput(
            stdout=stdout_str,
            stderr=stderr_str,
            exit_code=exit_code,
            command_executed=command_str
        )
        
    except CommandSanitizationError as e:
        invocation_logger.failure(str(e))
        return AzureCliOutput(
            stdout="",
            stderr=f"Command rejected: {str(e)}",
            exit_code=-2
        )
    except CommandLengthError as e:
        invocation_logger.failure(str(e))
        return AzureCliOutput(
            stdout="",
            stderr=f"Command rejected: {str(e)}",
            exit_code=-3
        )
    except FileNotFoundError as e:
        invocation_logger.failure(str(e))
        return AzureCliOutput(
            stdout="",
            stderr=str(e),
            exit_code=-4
        )
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {str(e)}")
        return AzureCliOutput(
            stdout="",
            stderr=f"Unexpected error: {str(e)}",
            exit_code=-99
        )

