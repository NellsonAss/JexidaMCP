"""Synology Docker/Container Manager tools.

Provides MCP tools for managing Docker containers on Synology NAS.
"""

from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field

from logging_config import get_logger, ToolInvocationLogger
from tool_registry import tool

from .client import (
    SynologyClient,
    SynologyConnectionError,
    SynologyAuthError,
    SynologyAPIError,
)

logger = get_logger(__name__)


# -----------------------------------------------------------------------------
# Input/Output Schemas
# -----------------------------------------------------------------------------

class DockerContainerOutput(BaseModel):
    """Docker container information."""
    id: str = Field(description="Container ID")
    name: str = Field(description="Container name")
    image: str = Field(description="Image name")
    status: str = Field(description="Container status")
    state: str = Field(description="Container state")
    created: int = Field(description="Creation timestamp")


class DockerImageOutput(BaseModel):
    """Docker image information."""
    id: str = Field(description="Image ID")
    repository: str = Field(description="Repository name")
    tag: str = Field(description="Image tag")
    size: int = Field(description="Image size in bytes")
    created: int = Field(description="Creation timestamp")


class SynologyListDockerContainersInput(BaseModel):
    """Input schema for synology_list_docker_containers tool."""
    pass


class SynologyListDockerContainersOutput(BaseModel):
    """Output schema for synology_list_docker_containers tool."""
    success: bool = Field(description="Whether the operation succeeded")
    containers: List[DockerContainerOutput] = Field(
        default_factory=list,
        description="List of containers"
    )
    container_count: int = Field(default=0, description="Number of containers")
    error: str = Field(default="", description="Error message if failed")


class SynologyGetDockerContainerInfoInput(BaseModel):
    """Input schema for synology_get_docker_container_info tool."""
    container_id: str = Field(description="Container ID")


class SynologyGetDockerContainerInfoOutput(BaseModel):
    """Output schema for synology_get_docker_container_info tool."""
    success: bool = Field(description="Whether the operation succeeded")
    container: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Container details"
    )
    error: str = Field(default="", description="Error message if failed")


class SynologyStartDockerContainerInput(BaseModel):
    """Input schema for synology_start_docker_container tool."""
    container_id: str = Field(description="Container ID to start")


class SynologyStartDockerContainerOutput(BaseModel):
    """Output schema for synology_start_docker_container tool."""
    success: bool = Field(description="Whether the operation succeeded")
    error: str = Field(default="", description="Error message if failed")


class SynologyStopDockerContainerInput(BaseModel):
    """Input schema for synology_stop_docker_container tool."""
    container_id: str = Field(description="Container ID to stop")


class SynologyStopDockerContainerOutput(BaseModel):
    """Output schema for synology_stop_docker_container tool."""
    success: bool = Field(description="Whether the operation succeeded")
    error: str = Field(default="", description="Error message if failed")


class SynologyRestartDockerContainerInput(BaseModel):
    """Input schema for synology_restart_docker_container tool."""
    container_id: str = Field(description="Container ID to restart")


class SynologyRestartDockerContainerOutput(BaseModel):
    """Output schema for synology_restart_docker_container tool."""
    success: bool = Field(description="Whether the operation succeeded")
    error: str = Field(default="", description="Error message if failed")


class SynologyListDockerImagesInput(BaseModel):
    """Input schema for synology_list_docker_images tool."""
    pass


class SynologyListDockerImagesOutput(BaseModel):
    """Output schema for synology_list_docker_images tool."""
    success: bool = Field(description="Whether the operation succeeded")
    images: List[DockerImageOutput] = Field(
        default_factory=list,
        description="List of images"
    )
    image_count: int = Field(default=0, description="Number of images")
    error: str = Field(default="", description="Error message if failed")


# -----------------------------------------------------------------------------
# Tool Implementations
# -----------------------------------------------------------------------------

@tool(
    name="synology_list_docker_containers",
    description="List Docker containers on Synology NAS",
    input_schema=SynologyListDockerContainersInput,
    output_schema=SynologyListDockerContainersOutput,
    tags=["synology", "docker", "containers"]
)
async def synology_list_docker_containers(params: SynologyListDockerContainersInput) -> SynologyListDockerContainersOutput:
    """List Docker containers."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_list_docker_containers")
    
    try:
        async with SynologyClient() as client:
            containers = await client.list_docker_containers()
            
            container_list = [
                DockerContainerOutput(
                    id=c.get("id", ""),
                    name=c.get("name", ""),
                    image=c.get("image", ""),
                    status=c.get("status", ""),
                    state=c.get("state", ""),
                    created=c.get("created", 0),
                )
                for c in containers
            ]
            
            invocation_logger.success(container_count=len(container_list))
            
            return SynologyListDockerContainersOutput(
                success=True,
                containers=container_list,
                container_count=len(container_list),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyListDockerContainersOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyListDockerContainersOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyListDockerContainersOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyListDockerContainersOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_get_docker_container_info",
    description="Get detailed information about a Docker container",
    input_schema=SynologyGetDockerContainerInfoInput,
    output_schema=SynologyGetDockerContainerInfoOutput,
    tags=["synology", "docker", "containers"]
)
async def synology_get_docker_container_info(params: SynologyGetDockerContainerInfoInput) -> SynologyGetDockerContainerInfoOutput:
    """Get Docker container details."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_get_docker_container_info", container_id=params.container_id)
    
    try:
        async with SynologyClient() as client:
            container = await client.get_docker_container_info(params.container_id)
            
            invocation_logger.success()
            
            return SynologyGetDockerContainerInfoOutput(
                success=True,
                container=container,
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyGetDockerContainerInfoOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyGetDockerContainerInfoOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyGetDockerContainerInfoOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyGetDockerContainerInfoOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_start_docker_container",
    description="Start a Docker container on Synology NAS",
    input_schema=SynologyStartDockerContainerInput,
    output_schema=SynologyStartDockerContainerOutput,
    tags=["synology", "docker", "containers"]
)
async def synology_start_docker_container(params: SynologyStartDockerContainerInput) -> SynologyStartDockerContainerOutput:
    """Start a Docker container."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_start_docker_container", container_id=params.container_id)
    
    try:
        async with SynologyClient() as client:
            await client.start_docker_container(params.container_id)
            
            invocation_logger.success()
            
            return SynologyStartDockerContainerOutput(success=True)
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyStartDockerContainerOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyStartDockerContainerOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyStartDockerContainerOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyStartDockerContainerOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_stop_docker_container",
    description="Stop a Docker container on Synology NAS",
    input_schema=SynologyStopDockerContainerInput,
    output_schema=SynologyStopDockerContainerOutput,
    tags=["synology", "docker", "containers"]
)
async def synology_stop_docker_container(params: SynologyStopDockerContainerInput) -> SynologyStopDockerContainerOutput:
    """Stop a Docker container."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_stop_docker_container", container_id=params.container_id)
    
    try:
        async with SynologyClient() as client:
            await client.stop_docker_container(params.container_id)
            
            invocation_logger.success()
            
            return SynologyStopDockerContainerOutput(success=True)
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyStopDockerContainerOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyStopDockerContainerOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyStopDockerContainerOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyStopDockerContainerOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_restart_docker_container",
    description="Restart a Docker container on Synology NAS",
    input_schema=SynologyRestartDockerContainerInput,
    output_schema=SynologyRestartDockerContainerOutput,
    tags=["synology", "docker", "containers"]
)
async def synology_restart_docker_container(params: SynologyRestartDockerContainerInput) -> SynologyRestartDockerContainerOutput:
    """Restart a Docker container."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_restart_docker_container", container_id=params.container_id)
    
    try:
        async with SynologyClient() as client:
            await client.restart_docker_container(params.container_id)
            
            invocation_logger.success()
            
            return SynologyRestartDockerContainerOutput(success=True)
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyRestartDockerContainerOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyRestartDockerContainerOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyRestartDockerContainerOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyRestartDockerContainerOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_list_docker_images",
    description="List Docker images on Synology NAS",
    input_schema=SynologyListDockerImagesInput,
    output_schema=SynologyListDockerImagesOutput,
    tags=["synology", "docker", "images"]
)
async def synology_list_docker_images(params: SynologyListDockerImagesInput) -> SynologyListDockerImagesOutput:
    """List Docker images."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_list_docker_images")
    
    try:
        async with SynologyClient() as client:
            images = await client.list_docker_images()
            
            image_list = [
                DockerImageOutput(
                    id=img.get("id", ""),
                    repository=img.get("repository", ""),
                    tag=img.get("tag", ""),
                    size=img.get("size", 0),
                    created=img.get("created", 0),
                )
                for img in images
            ]
            
            invocation_logger.success(image_count=len(image_list))
            
            return SynologyListDockerImagesOutput(
                success=True,
                images=image_list,
                image_count=len(image_list),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyListDockerImagesOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyListDockerImagesOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyListDockerImagesOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyListDockerImagesOutput(success=False, error=f"Unexpected error: {e}")

