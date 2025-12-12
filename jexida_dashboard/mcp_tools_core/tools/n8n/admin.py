"""n8n SSH-based administration tools.

Provides MCP tools for:
- Restarting the n8n Docker stack
- Creating backups
- Restoring from backups
"""

import logging
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .client import N8nConfig

logger = logging.getLogger(__name__)


def get_ssh_executor():
    """Get the SSH executor for worker nodes."""
    from ..jobs.executor import WorkerSSHExecutor
    return WorkerSSHExecutor(timeout=300)


def get_n8n_worker_node():
    """Get the worker node running n8n."""
    from mcp_tools_core.models import WorkerNode
    
    config = N8nConfig.from_settings()
    
    # Try to find the node by host
    try:
        return WorkerNode.objects.get(host=config.ssh_host)
    except WorkerNode.DoesNotExist:
        # Create a temporary node object for SSH execution
        class TempNode:
            def __init__(self, host, user, ssh_port=22):
                self.host = host
                self.user = user
                self.ssh_port = ssh_port
                self.name = f"n8n-node-{host}"
        
        return TempNode(config.ssh_host, config.ssh_user)


# =============================================================================
# Restart Stack Tool
# =============================================================================

class N8nRestartStackInput(BaseModel):
    """Input schema for n8n_restart_stack."""
    
    force: bool = Field(
        default=False,
        description="Force restart even if n8n appears unhealthy"
    )


class N8nRestartStackOutput(BaseModel):
    """Output schema for n8n_restart_stack."""
    
    success: bool = Field(description="Whether the restart succeeded")
    stdout: str = Field(default="", description="Command output")
    stderr: str = Field(default="", description="Error output")
    error: str = Field(default="", description="Error message if failed")


async def n8n_restart_stack(params: N8nRestartStackInput) -> N8nRestartStackOutput:
    """Restart the n8n Docker stack.
    
    Executes `docker compose restart` on the n8n host via SSH.
    
    Args:
        params: Restart options
        
    Returns:
        Restart result
    """
    logger.info("Restarting n8n stack")
    
    try:
        executor = get_ssh_executor()
        node = get_n8n_worker_node()
        
        command = "cd /opt/n8n && docker compose restart"
        result = executor.run_command(node, command)
        
        if result.success:
            logger.info("n8n stack restarted successfully")
            return N8nRestartStackOutput(
                success=True,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        else:
            logger.error(f"n8n restart failed: {result.stderr}")
            return N8nRestartStackOutput(
                success=False,
                stdout=result.stdout,
                stderr=result.stderr,
                error=f"Command failed with exit code {result.exit_code}",
            )
    except Exception as e:
        logger.error(f"Failed to restart n8n stack: {e}")
        return N8nRestartStackOutput(
            success=False,
            error=str(e),
        )


# =============================================================================
# Backup Tool
# =============================================================================

class N8nBackupInput(BaseModel):
    """Input schema for n8n_backup."""
    
    backup_name: Optional[str] = Field(
        default=None,
        description="Custom backup name (defaults to timestamp)"
    )


class N8nBackupOutput(BaseModel):
    """Output schema for n8n_backup."""
    
    success: bool = Field(description="Whether the backup succeeded")
    backup_file: str = Field(default="", description="Path to backup file")
    size_bytes: int = Field(default=0, description="Backup file size")
    stdout: str = Field(default="", description="Command output")
    error: str = Field(default="", description="Error message if failed")


async def n8n_backup(params: N8nBackupInput) -> N8nBackupOutput:
    """Create a backup of n8n data.
    
    Creates a tarball of /opt/n8n/data and stores it in /opt/n8n/backups/.
    
    Args:
        params: Backup options
        
    Returns:
        Backup result with file path
    """
    logger.info("Creating n8n backup")
    
    try:
        executor = get_ssh_executor()
        node = get_n8n_worker_node()
        
        # Generate backup filename
        if params.backup_name:
            backup_name = params.backup_name
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"n8n_backup_{timestamp}"
        
        backup_file = f"/opt/n8n/backups/{backup_name}.tar.gz"
        
        # Create backup command
        command = f"""
cd /opt/n8n
mkdir -p backups
tar -czf "{backup_file}" -C /opt/n8n data
ls -la "{backup_file}"
"""
        
        result = executor.run_command(node, command.strip())
        
        if result.success:
            # Parse file size from ls output
            size_bytes = 0
            for line in result.stdout.strip().split("\n"):
                if backup_name in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        try:
                            size_bytes = int(parts[4])
                        except ValueError:
                            pass
                    break
            
            logger.info(f"n8n backup created: {backup_file}")
            return N8nBackupOutput(
                success=True,
                backup_file=backup_file,
                size_bytes=size_bytes,
                stdout=result.stdout,
            )
        else:
            logger.error(f"n8n backup failed: {result.stderr}")
            return N8nBackupOutput(
                success=False,
                stdout=result.stdout,
                error=f"Backup failed: {result.stderr}",
            )
    except Exception as e:
        logger.error(f"Failed to create n8n backup: {e}")
        return N8nBackupOutput(
            success=False,
            error=str(e),
        )


# =============================================================================
# Restore Backup Tool
# =============================================================================

class N8nRestoreBackupInput(BaseModel):
    """Input schema for n8n_restore_backup."""
    
    backup_file: str = Field(
        description="Path to backup file (e.g., /opt/n8n/backups/n8n_backup_20241210.tar.gz)"
    )
    stop_n8n: bool = Field(
        default=True,
        description="Stop n8n before restoring (recommended)"
    )


class N8nRestoreBackupOutput(BaseModel):
    """Output schema for n8n_restore_backup."""
    
    success: bool = Field(description="Whether the restore succeeded")
    stdout: str = Field(default="", description="Command output")
    error: str = Field(default="", description="Error message if failed")


async def n8n_restore_backup(params: N8nRestoreBackupInput) -> N8nRestoreBackupOutput:
    """Restore n8n data from a backup.
    
    Restores data from a tarball backup file. Optionally stops n8n first.
    
    Args:
        params: Backup file path and options
        
    Returns:
        Restore result
    """
    logger.info(f"Restoring n8n from backup: {params.backup_file}")
    
    try:
        executor = get_ssh_executor()
        node = get_n8n_worker_node()
        
        # Build restore command
        commands = []
        
        if params.stop_n8n:
            commands.append("cd /opt/n8n && docker compose down")
        
        commands.extend([
            f'test -f "{params.backup_file}" || (echo "Backup file not found" && exit 1)',
            "rm -rf /opt/n8n/data.old",
            "mv /opt/n8n/data /opt/n8n/data.old",
            f'tar -xzf "{params.backup_file}" -C /opt/n8n',
        ])
        
        if params.stop_n8n:
            commands.append("cd /opt/n8n && docker compose up -d")
        
        command = " && ".join(commands)
        result = executor.run_command(node, command)
        
        if result.success:
            logger.info("n8n restore completed successfully")
            return N8nRestoreBackupOutput(
                success=True,
                stdout=result.stdout,
            )
        else:
            logger.error(f"n8n restore failed: {result.stderr}")
            return N8nRestoreBackupOutput(
                success=False,
                stdout=result.stdout,
                error=f"Restore failed: {result.stderr}",
            )
    except Exception as e:
        logger.error(f"Failed to restore n8n backup: {e}")
        return N8nRestoreBackupOutput(
            success=False,
            error=str(e),
        )

