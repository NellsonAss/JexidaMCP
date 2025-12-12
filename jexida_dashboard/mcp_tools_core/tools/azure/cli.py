"""Azure CLI tool implementation.

Provides the azure_cli_run tool for executing Azure CLI commands safely.
"""

import asyncio
import logging
import subprocess
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from .utils import (
    AZURE_CLI_TIMEOUT,
    CommandLengthError,
    CommandSanitizationError,
    build_az_command,
    sanitize_command,
    validate_subscription_id,
)

logger = logging.getLogger(__name__)


class AzureCliInput(BaseModel):
    """Input schema for azure_cli_run tool."""

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
    """Output schema for azure_cli_run tool."""

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


async def azure_cli_run(params: AzureCliInput) -> AzureCliOutput:
    """Execute an Azure CLI command.

    Args:
        params: Validated input parameters

    Returns:
        Command execution result
    """
    logger.info(
        f"azure_cli_run called: subscription_id={params.subscription_id}, dry_run={params.dry_run}"
    )

    try:
        # Sanitize command
        sanitized_command = sanitize_command(params.command)

        # Build full command
        cmd_args = build_az_command(sanitized_command, params.subscription_id)
        command_str = " ".join(cmd_args)

        # Dry run mode - return command without executing
        if params.dry_run:
            logger.info("Dry run mode - returning command without execution")
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
                timeout=AZURE_CLI_TIMEOUT
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            logger.error(f"Command timed out after {AZURE_CLI_TIMEOUT} seconds")
            return AzureCliOutput(
                stdout="",
                stderr=f"Command timed out after {AZURE_CLI_TIMEOUT} seconds",
                exit_code=-1,
                command_executed=command_str
            )

        exit_code = process.returncode
        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")

        if exit_code == 0:
            logger.info(f"Command succeeded with exit code {exit_code}")
        else:
            logger.warning(f"Command failed with exit code {exit_code}")

        return AzureCliOutput(
            stdout=stdout_str,
            stderr=stderr_str,
            exit_code=exit_code,
            command_executed=command_str
        )

    except CommandSanitizationError as e:
        logger.error(f"Command sanitization failed: {e}")
        return AzureCliOutput(
            stdout="",
            stderr=f"Command rejected: {str(e)}",
            exit_code=-2
        )
    except CommandLengthError as e:
        logger.error(f"Command too long: {e}")
        return AzureCliOutput(
            stdout="",
            stderr=f"Command rejected: {str(e)}",
            exit_code=-3
        )
    except FileNotFoundError as e:
        logger.error(f"Azure CLI not found: {e}")
        return AzureCliOutput(
            stdout="",
            stderr=str(e),
            exit_code=-4
        )
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return AzureCliOutput(
            stdout="",
            stderr=f"Unexpected error: {str(e)}",
            exit_code=-99
        )

