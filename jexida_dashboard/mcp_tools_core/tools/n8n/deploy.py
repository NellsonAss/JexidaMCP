"""n8n deployment tool.

Deploys n8n to a worker node by uploading and executing the setup script.
"""

import logging
import secrets
import subprocess
import tempfile
import os
from typing import Optional

from pydantic import BaseModel, Field

from .client import N8nConfig

logger = logging.getLogger(__name__)


def get_setup_script_path() -> str:
    """Get the path to the setup script.
    
    Checks multiple locations for the setup script.
    """
    # Check relative to this file (when deployed)
    possible_paths = [
        "/opt/jexida-mcp/scripts/setup_n8n_node.sh",
        os.path.join(os.path.dirname(__file__), "../../../../../scripts/setup_n8n_node.sh"),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return os.path.abspath(path)
    
    raise FileNotFoundError("setup_n8n_node.sh not found")


def generate_encryption_key() -> str:
    """Generate a 32-byte hex encryption key."""
    return secrets.token_hex(32)


# =============================================================================
# Deploy Stack Tool
# =============================================================================

class N8nDeployStackInput(BaseModel):
    """Input schema for n8n_deploy_stack."""
    
    node_name: str = Field(
        description="Name of the worker node to deploy to (must be registered)"
    )
    n8n_user: str = Field(
        default="admin",
        description="Username for n8n web UI basic auth"
    )
    n8n_password: str = Field(
        description="Password for n8n web UI basic auth"
    )
    encryption_key: str = Field(
        default="auto",
        description="32-byte hex encryption key, or 'auto' to generate"
    )
    force_reinstall: bool = Field(
        default=False,
        description="Force reinstall even if n8n is already running"
    )


class N8nDeployStackOutput(BaseModel):
    """Output schema for n8n_deploy_stack."""
    
    success: bool = Field(description="Whether deployment succeeded")
    node_name: str = Field(default="", description="Target node name")
    node_host: str = Field(default="", description="Target node host")
    n8n_url: str = Field(default="", description="URL to access n8n")
    encryption_key: str = Field(default="", description="Encryption key used (save this!)")
    stdout: str = Field(default="", description="Deployment output")
    error: str = Field(default="", description="Error message if failed")


async def n8n_deploy_stack(params: N8nDeployStackInput) -> N8nDeployStackOutput:
    """Deploy n8n to a worker node.
    
    Uploads the setup script and executes it with the provided credentials.
    The encryption key is critical - save it for future reference!
    
    Args:
        params: Deployment configuration
        
    Returns:
        Deployment result with access URL
    """
    logger.info(f"Deploying n8n to node: {params.node_name}")
    
    try:
        from mcp_tools_core.models import WorkerNode
        from asgiref.sync import sync_to_async
        
        @sync_to_async
        def get_node():
            try:
                return WorkerNode.objects.get(name=params.node_name)
            except WorkerNode.DoesNotExist:
                return None
        
        node = await get_node()
        
        if node is None:
            return N8nDeployStackOutput(
                success=False,
                error=f"Worker node '{params.node_name}' not found",
            )
        
        # Generate encryption key if auto
        if params.encryption_key.lower() == "auto":
            encryption_key = generate_encryption_key()
            logger.info("Generated encryption key")
        else:
            encryption_key = params.encryption_key
        
        # Get the setup script
        try:
            script_path = get_setup_script_path()
        except FileNotFoundError:
            return N8nDeployStackOutput(
                success=False,
                error="Setup script not found on MCP server",
            )
        
        # Upload script via SCP
        connection_string = f"{node.user}@{node.host}"
        remote_script = "/tmp/setup_n8n_node.sh"
        
        # Use the MCP server's SSH key
        ssh_key_path = "/opt/jexida-mcp/.ssh/id_ed25519"
        known_hosts_path = "/opt/jexida-mcp/.ssh/known_hosts"
        
        scp_command = [
            "scp",
            "-i", ssh_key_path,
            "-o", f"UserKnownHostsFile={known_hosts_path}",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "BatchMode=yes",
            script_path,
            f"{connection_string}:{remote_script}",
        ]
        
        logger.info(f"Uploading setup script to {connection_string}")
        scp_result = subprocess.run(
            scp_command,
            capture_output=True,
            text=True,
            timeout=60,
        )
        
        if scp_result.returncode != 0:
            return N8nDeployStackOutput(
                success=False,
                node_name=params.node_name,
                node_host=node.host,
                error=f"Failed to upload script: {scp_result.stderr}",
            )
        
        # Execute the script
        ssh_command = [
            "ssh",
            "-i", ssh_key_path,
            "-o", f"UserKnownHostsFile={known_hosts_path}",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "BatchMode=yes",
            connection_string,
            f"chmod +x {remote_script} && {remote_script} '{params.n8n_user}' '{params.n8n_password}' '{encryption_key}'",
        ]
        
        logger.info(f"Executing setup script on {node.host}")
        ssh_result = subprocess.run(
            ssh_command,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout for Docker install
        )
        
        # Clean up remote script
        subprocess.run(
            ["ssh", "-i", ssh_key_path, "-o", f"UserKnownHostsFile={known_hosts_path}", 
             "-o", "BatchMode=yes", connection_string, f"rm -f {remote_script}"],
            capture_output=True,
            timeout=30,
        )
        
        if ssh_result.returncode != 0:
            return N8nDeployStackOutput(
                success=False,
                node_name=params.node_name,
                node_host=node.host,
                stdout=ssh_result.stdout,
                error=f"Deployment failed: {ssh_result.stderr}",
            )
        
        n8n_url = f"http://{node.host}:5678"
        
        logger.info(f"n8n deployed successfully at {n8n_url}")
        return N8nDeployStackOutput(
            success=True,
            node_name=params.node_name,
            node_host=node.host,
            n8n_url=n8n_url,
            encryption_key=encryption_key,
            stdout=ssh_result.stdout,
        )
        
    except subprocess.TimeoutExpired:
        return N8nDeployStackOutput(
            success=False,
            node_name=params.node_name,
            error="Deployment timed out",
        )
    except Exception as e:
        logger.error(f"Failed to deploy n8n: {e}")
        return N8nDeployStackOutput(
            success=False,
            node_name=params.node_name,
            error=str(e),
        )

