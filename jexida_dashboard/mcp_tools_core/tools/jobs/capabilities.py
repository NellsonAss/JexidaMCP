"""Node capability discovery and provisioning tools.

Provides tools for:
- catalog_node_capabilities: Discover and store node capabilities
- provision_worker_node: Set up a new node for job execution
- register_worker_node: Add a new node to the database
"""

import logging
from typing import Optional, Dict, Any, List

from asgiref.sync import sync_to_async
from pydantic import BaseModel, Field

from .executor import WorkerSSHExecutor

logger = logging.getLogger(__name__)


# =============================================================================
# Catalog Node Capabilities Tool
# =============================================================================

class CatalogNodeCapabilitiesInput(BaseModel):
    """Input schema for catalog_node_capabilities."""

    name: str = Field(
        description="Name of the worker node to catalog"
    )


class NodeCapabilities(BaseModel):
    """Discovered capabilities of a worker node."""

    # System info
    hostname: str = Field(default="", description="System hostname")
    os_name: str = Field(default="", description="Operating system name")
    os_version: str = Field(default="", description="Operating system version")
    kernel_version: str = Field(default="", description="Kernel version")
    architecture: str = Field(default="", description="CPU architecture")

    # Hardware
    cpu_model: str = Field(default="", description="CPU model name")
    cpu_cores: int = Field(default=0, description="Number of CPU cores")
    memory_total_gb: float = Field(default=0, description="Total RAM in GB")
    disk_total_gb: float = Field(default=0, description="Total disk space in GB")
    disk_available_gb: float = Field(default=0, description="Available disk space in GB")

    # Software
    python_version: str = Field(default="", description="Python 3 version")
    docker_available: bool = Field(default=False, description="Whether Docker is installed")
    docker_version: str = Field(default="", description="Docker version if installed")
    git_available: bool = Field(default=False, description="Whether Git is installed")
    git_version: str = Field(default="", description="Git version if installed")

    # JexidaMCP setup
    job_dirs_exist: bool = Field(default=False, description="Whether job directories exist")
    jexida_user_exists: bool = Field(default=False, description="Whether jexida user exists")

    # Installed packages
    installed_packages: List[str] = Field(default_factory=list, description="Key installed packages")

    # Tags to suggest
    suggested_tags: List[str] = Field(default_factory=list, description="Suggested tags based on capabilities")


class CatalogNodeCapabilitiesOutput(BaseModel):
    """Output schema for catalog_node_capabilities."""

    success: bool = Field(description="Whether the catalog operation succeeded")
    node_name: str = Field(default="", description="Name of the cataloged node")
    capabilities: Optional[NodeCapabilities] = Field(default=None, description="Discovered capabilities")
    raw_output: str = Field(default="", description="Raw command output for debugging")
    error: str = Field(default="", description="Error message if failed")


def parse_capabilities(output: str) -> NodeCapabilities:
    """Parse capability discovery output into structured data."""
    caps = NodeCapabilities()
    lines = output.strip().split("\n")
    suggested_tags = ["worker"]

    for line in lines:
        line = line.strip()

        # Hostname
        if line.startswith("HOSTNAME:"):
            caps.hostname = line.split(":", 1)[1].strip()

        # OS info
        elif line.startswith("OS_NAME:"):
            caps.os_name = line.split(":", 1)[1].strip()
            if "ubuntu" in caps.os_name.lower():
                suggested_tags.append("ubuntu")
            elif "debian" in caps.os_name.lower():
                suggested_tags.append("debian")
            elif "centos" in caps.os_name.lower() or "rhel" in caps.os_name.lower():
                suggested_tags.append("rhel")

        elif line.startswith("OS_VERSION:"):
            caps.os_version = line.split(":", 1)[1].strip()

        elif line.startswith("KERNEL:"):
            caps.kernel_version = line.split(":", 1)[1].strip()

        elif line.startswith("ARCH:"):
            caps.architecture = line.split(":", 1)[1].strip()
            if "arm" in caps.architecture.lower() or "aarch" in caps.architecture.lower():
                suggested_tags.append("arm")

        # CPU info
        elif line.startswith("CPU_MODEL:"):
            caps.cpu_model = line.split(":", 1)[1].strip()

        elif line.startswith("CPU_CORES:"):
            try:
                caps.cpu_cores = int(line.split(":", 1)[1].strip())
                if caps.cpu_cores >= 8:
                    suggested_tags.append("high-cpu")
            except ValueError:
                pass

        # Memory
        elif line.startswith("MEMORY_GB:"):
            try:
                caps.memory_total_gb = float(line.split(":", 1)[1].strip())
                if caps.memory_total_gb >= 16:
                    suggested_tags.append("high-memory")
            except ValueError:
                pass

        # Disk
        elif line.startswith("DISK_TOTAL_GB:"):
            try:
                caps.disk_total_gb = float(line.split(":", 1)[1].strip())
            except ValueError:
                pass

        elif line.startswith("DISK_AVAIL_GB:"):
            try:
                caps.disk_available_gb = float(line.split(":", 1)[1].strip())
                if caps.disk_available_gb >= 100:
                    suggested_tags.append("high-storage")
            except ValueError:
                pass

        # Python
        elif line.startswith("PYTHON_VERSION:"):
            caps.python_version = line.split(":", 1)[1].strip()
            if caps.python_version:
                suggested_tags.append("python3")

        # Docker
        elif line.startswith("DOCKER_VERSION:"):
            version = line.split(":", 1)[1].strip()
            if version and version != "not_installed":
                caps.docker_available = True
                caps.docker_version = version
                suggested_tags.append("docker")

        # Git
        elif line.startswith("GIT_VERSION:"):
            version = line.split(":", 1)[1].strip()
            if version and version != "not_installed":
                caps.git_available = True
                caps.git_version = version

        # Job directories
        elif line.startswith("JOB_DIRS:"):
            caps.job_dirs_exist = line.split(":", 1)[1].strip() == "exist"

        # Jexida user
        elif line.startswith("JEXIDA_USER:"):
            caps.jexida_user_exists = line.split(":", 1)[1].strip() == "exists"

        # Packages
        elif line.startswith("PACKAGES:"):
            pkgs = line.split(":", 1)[1].strip()
            if pkgs:
                caps.installed_packages = [p.strip() for p in pkgs.split(",") if p.strip()]

    caps.suggested_tags = list(set(suggested_tags))
    return caps


async def catalog_node_capabilities(params: CatalogNodeCapabilitiesInput) -> CatalogNodeCapabilitiesOutput:
    """Discover and catalog a worker node's capabilities.

    Connects to the node via SSH and gathers comprehensive system information
    including hardware specs, installed software, and configuration.

    The discovered capabilities are stored in the node's record for future
    reference and job routing decisions.

    Args:
        params: Node name to catalog

    Returns:
        Discovered capabilities
    """
    logger.info(f"Cataloging capabilities for node: {params.name}")

    try:
        from mcp_tools_core.models import WorkerNode, Fact
        from django.utils import timezone

        @sync_to_async
        def get_node():
            try:
                return WorkerNode.objects.get(name=params.name)
            except WorkerNode.DoesNotExist:
                return None

        @sync_to_async
        def save_capabilities(node, caps: NodeCapabilities):
            """Save capabilities to the Fact store."""
            key = f"nodes.{node.name}.capabilities"
            Fact.objects.update_or_create(
                key=key,
                defaults={
                    "value": caps.model_dump(),
                    "source": "catalog_node_capabilities",
                }
            )
            # Update last_seen
            node.last_seen = timezone.now()
            node.save(update_fields=["last_seen"])

        node = await get_node()

        if node is None:
            return CatalogNodeCapabilitiesOutput(
                success=False,
                error=f"Worker node '{params.name}' not found"
            )

        # Run capability discovery command
        executor = WorkerSSHExecutor(timeout=60)

        discovery_command = '''
echo "HOSTNAME:$(hostname)"
echo "OS_NAME:$(cat /etc/os-release 2>/dev/null | grep "^NAME=" | cut -d'"' -f2 || echo "unknown")"
echo "OS_VERSION:$(cat /etc/os-release 2>/dev/null | grep "^VERSION_ID=" | cut -d'"' -f2 || echo "unknown")"
echo "KERNEL:$(uname -r)"
echo "ARCH:$(uname -m)"
echo "CPU_MODEL:$(cat /proc/cpuinfo 2>/dev/null | grep "model name" | head -1 | cut -d':' -f2 | xargs || echo "unknown")"
echo "CPU_CORES:$(nproc 2>/dev/null || echo 0)"
echo "MEMORY_GB:$(free -g 2>/dev/null | grep Mem | awk '{print $2}' || echo 0)"
echo "DISK_TOTAL_GB:$(df -BG / 2>/dev/null | tail -1 | awk '{gsub("G",""); print $2}' || echo 0)"
echo "DISK_AVAIL_GB:$(df -BG / 2>/dev/null | tail -1 | awk '{gsub("G",""); print $4}' || echo 0)"
echo "PYTHON_VERSION:$(python3 --version 2>/dev/null | cut -d' ' -f2 || echo "")"
echo "DOCKER_VERSION:$(docker --version 2>/dev/null | cut -d' ' -f3 | tr -d ',' || echo "not_installed")"
echo "GIT_VERSION:$(git --version 2>/dev/null | cut -d' ' -f3 || echo "not_installed")"
if [ -d /opt/jexida-jobs ] && [ -d /var/log/jexida-jobs ]; then echo "JOB_DIRS:exist"; else echo "JOB_DIRS:missing"; fi
if id jexida >/dev/null 2>&1; then echo "JEXIDA_USER:exists"; else echo "JEXIDA_USER:missing"; fi
echo "PACKAGES:$(dpkg -l 2>/dev/null | grep -E "^ii.*(curl|wget|rsync|screen|tmux|htop|vim|nano)" | awk '{print $2}' | tr '\n' ',' || echo "")"
'''

        result = executor.run_command(node, discovery_command.strip())

        if not result.success:
            return CatalogNodeCapabilitiesOutput(
                success=False,
                node_name=params.name,
                raw_output=result.stderr,
                error=f"Failed to connect: {result.stderr}"
            )

        # Parse capabilities
        capabilities = parse_capabilities(result.stdout)

        # Save to Fact store
        await save_capabilities(node, capabilities)

        return CatalogNodeCapabilitiesOutput(
            success=True,
            node_name=params.name,
            capabilities=capabilities,
            raw_output=result.stdout,
        )

    except Exception as e:
        logger.error(f"Failed to catalog node capabilities: {e}")
        return CatalogNodeCapabilitiesOutput(
            success=False,
            node_name=params.name,
            error=str(e)
        )


# =============================================================================
# Register Worker Node Tool
# =============================================================================

class RegisterWorkerNodeInput(BaseModel):
    """Input schema for register_worker_node."""

    name: str = Field(description="Unique name for the node (e.g., 'JexidaDroid2')")
    host: str = Field(description="Hostname or IP address")
    user: str = Field(default="jexida", description="SSH username")
    ssh_port: int = Field(default=22, description="SSH port")
    tags: str = Field(default="ubuntu,worker", description="Comma-separated tags")
    is_active: bool = Field(default=True, description="Whether node is active")


class RegisterWorkerNodeOutput(BaseModel):
    """Output schema for register_worker_node."""

    success: bool = Field(description="Whether the registration succeeded")
    created: bool = Field(default=False, description="True if new node, False if updated")
    node_name: str = Field(default="", description="Name of the registered node")
    error: str = Field(default="", description="Error message if failed")


async def register_worker_node(params: RegisterWorkerNodeInput) -> RegisterWorkerNodeOutput:
    """Register a new worker node in the database.

    Creates or updates a worker node record. The node must be set up
    with SSH access before it can be used for job execution.

    Args:
        params: Node registration details

    Returns:
        Registration result
    """
    logger.info(f"Registering worker node: {params.name} ({params.host})")

    try:
        from mcp_tools_core.models import WorkerNode

        @sync_to_async
        def create_or_update():
            node, created = WorkerNode.objects.update_or_create(
                name=params.name,
                defaults={
                    "host": params.host,
                    "user": params.user,
                    "ssh_port": params.ssh_port,
                    "tags": params.tags,
                    "is_active": params.is_active,
                }
            )
            return node, created

        node, created = await create_or_update()

        action = "Created" if created else "Updated"
        logger.info(f"{action} worker node: {node.name} ({node.host})")

        return RegisterWorkerNodeOutput(
            success=True,
            created=created,
            node_name=node.name,
        )

    except Exception as e:
        logger.error(f"Failed to register worker node: {e}")
        return RegisterWorkerNodeOutput(
            success=False,
            error=str(e)
        )


# =============================================================================
# Provision Worker Node Tool
# =============================================================================

class ProvisionWorkerNodeInput(BaseModel):
    """Input schema for provision_worker_node."""

    name: str = Field(description="Name of the node to provision")
    create_user: bool = Field(default=True, description="Create jexida user if missing")
    install_python: bool = Field(default=True, description="Install Python 3 if missing")
    create_job_dirs: bool = Field(default=True, description="Create job directories")
    dry_run: bool = Field(default=True, description="Only show what would be done")


class ProvisionWorkerNodeOutput(BaseModel):
    """Output schema for provision_worker_node."""

    success: bool = Field(description="Whether provisioning succeeded")
    node_name: str = Field(default="", description="Name of the provisioned node")
    steps_executed: List[str] = Field(default_factory=list, description="Steps that were executed")
    steps_skipped: List[str] = Field(default_factory=list, description="Steps that were skipped")
    output: str = Field(default="", description="Command output")
    error: str = Field(default="", description="Error message if failed")


async def provision_worker_node(params: ProvisionWorkerNodeInput) -> ProvisionWorkerNodeOutput:
    """Provision a worker node for job execution.

    Sets up the node with required configuration:
    - Creates jexida user (if create_user=True)
    - Installs Python 3 (if install_python=True)
    - Creates job directories (if create_job_dirs=True)

    Note: This requires existing SSH access to the node. For initial setup,
    use the setup instructions from get_node_setup_instructions.

    Args:
        params: Provisioning options

    Returns:
        Provisioning result
    """
    logger.info(f"Provisioning worker node: {params.name} (dry_run={params.dry_run})")

    try:
        from mcp_tools_core.models import WorkerNode, Fact

        @sync_to_async
        def get_node():
            try:
                return WorkerNode.objects.get(name=params.name)
            except WorkerNode.DoesNotExist:
                return None

        @sync_to_async
        def get_capabilities(node_name: str) -> Optional[Dict[str, Any]]:
            try:
                fact = Fact.objects.get(key=f"nodes.{node_name}.capabilities")
                return fact.value
            except Fact.DoesNotExist:
                return None

        node = await get_node()

        if node is None:
            return ProvisionWorkerNodeOutput(
                success=False,
                error=f"Worker node '{params.name}' not found. Register it first."
            )

        # Get current capabilities to determine what needs setup
        caps = await get_capabilities(params.name)

        steps_executed = []
        steps_skipped = []
        commands = []

        # Check and build provisioning commands
        if params.create_user:
            if caps and caps.get("jexida_user_exists"):
                steps_skipped.append("Create jexida user (already exists)")
            else:
                commands.append("sudo adduser jexida --disabled-password --gecos 'Jexida MCP Worker' 2>/dev/null || echo 'User may already exist'")
                commands.append("sudo usermod -aG sudo jexida 2>/dev/null || true")
                steps_executed.append("Create jexida user")

        if params.install_python:
            if caps and caps.get("python_version"):
                steps_skipped.append(f"Install Python 3 (already installed: {caps.get('python_version')})")
            else:
                commands.append("sudo apt-get update -qq")
                commands.append("sudo apt-get install -y -qq python3 python3-pip python3-venv")
                steps_executed.append("Install Python 3")

        if params.create_job_dirs:
            if caps and caps.get("job_dirs_exist"):
                steps_skipped.append("Create job directories (already exist)")
            else:
                commands.append("sudo mkdir -p /opt/jexida-jobs /var/log/jexida-jobs")
                commands.append("sudo chown jexida:jexida /opt/jexida-jobs /var/log/jexida-jobs 2>/dev/null || true")
                steps_executed.append("Create job directories")

        if not commands:
            return ProvisionWorkerNodeOutput(
                success=True,
                node_name=params.name,
                steps_executed=[],
                steps_skipped=steps_skipped,
                output="Node is already fully provisioned",
            )

        if params.dry_run:
            return ProvisionWorkerNodeOutput(
                success=True,
                node_name=params.name,
                steps_executed=[f"[DRY RUN] {s}" for s in steps_executed],
                steps_skipped=steps_skipped,
                output="Commands that would be run:\n" + "\n".join(commands),
            )

        # Execute provisioning
        executor = WorkerSSHExecutor(timeout=300)
        full_command = " && ".join(commands)

        result = executor.run_command(node, full_command)

        if not result.success:
            return ProvisionWorkerNodeOutput(
                success=False,
                node_name=params.name,
                steps_executed=steps_executed,
                steps_skipped=steps_skipped,
                output=result.stdout,
                error=f"Provisioning failed: {result.stderr}",
            )

        return ProvisionWorkerNodeOutput(
            success=True,
            node_name=params.name,
            steps_executed=steps_executed,
            steps_skipped=steps_skipped,
            output=result.stdout,
        )

    except Exception as e:
        logger.error(f"Failed to provision worker node: {e}")
        return ProvisionWorkerNodeOutput(
            success=False,
            node_name=params.name,
            error=str(e)
        )


# =============================================================================
# Get Node Setup Instructions Tool
# =============================================================================

class GetNodeSetupInstructionsInput(BaseModel):
    """Input schema for get_node_setup_instructions."""

    host: str = Field(description="IP address or hostname of the new node")
    node_name: str = Field(default="", description="Name to use for the node (auto-generated if empty)")


class GetNodeSetupInstructionsOutput(BaseModel):
    """Output schema for get_node_setup_instructions."""

    success: bool = Field(description="Whether instructions were generated")
    node_name: str = Field(default="", description="Suggested node name")
    ssh_public_key: str = Field(default="", description="MCP server's SSH public key")
    setup_commands: str = Field(default="", description="Commands to run on the new node")
    error: str = Field(default="", description="Error message if failed")


async def get_node_setup_instructions(params: GetNodeSetupInstructionsInput) -> GetNodeSetupInstructionsOutput:
    """Get setup instructions for a new worker node.

    Generates the commands needed to prepare a new server as a worker node,
    including the MCP server's SSH public key.

    Run these commands on the new node to enable SSH access.

    Args:
        params: Node host and optional name

    Returns:
        Setup instructions
    """
    logger.info(f"Generating setup instructions for node: {params.host}")

    try:
        import subprocess
        from mcp_tools_core.models import WorkerNode

        # Get MCP server's public key
        try:
            result = subprocess.run(
                ["cat", "/opt/jexida-mcp/.ssh/id_ed25519.pub"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            ssh_public_key = result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            ssh_public_key = ""

        # Generate node name if not provided
        if params.node_name:
            node_name = params.node_name
        else:
            # Auto-generate based on existing count
            @sync_to_async
            def count_nodes():
                return WorkerNode.objects.count()

            count = await count_nodes()
            node_name = f"JexidaDroid{count + 1}"

        setup_commands = f'''# Run these commands on {params.host} to set up the worker node

# 1. Create the jexida user
sudo adduser jexida --disabled-password --gecos "Jexida MCP Worker"
sudo usermod -aG sudo jexida  # Optional: for privileged commands

# 2. Set up SSH key authentication
sudo mkdir -p /home/jexida/.ssh
sudo chmod 700 /home/jexida/.ssh
echo "{ssh_public_key}" | sudo tee /home/jexida/.ssh/authorized_keys
sudo chmod 600 /home/jexida/.ssh/authorized_keys
sudo chown -R jexida:jexida /home/jexida/.ssh

# 3. Install Python 3 (if not already installed)
sudo apt update
sudo apt install -y python3 python3-pip python3-venv

# 4. Create job directories
sudo mkdir -p /opt/jexida-jobs
sudo mkdir -p /var/log/jexida-jobs
sudo chown jexida:jexida /opt/jexida-jobs
sudo chown jexida:jexida /var/log/jexida-jobs

# Done! Now register this node using the register_worker_node tool with:
#   name: {node_name}
#   host: {params.host}
'''

        return GetNodeSetupInstructionsOutput(
            success=True,
            node_name=node_name,
            ssh_public_key=ssh_public_key,
            setup_commands=setup_commands,
        )

    except Exception as e:
        logger.error(f"Failed to generate setup instructions: {e}")
        return GetNodeSetupInstructionsOutput(
            success=False,
            error=str(e)
        )

