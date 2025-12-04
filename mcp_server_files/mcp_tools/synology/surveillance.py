"""Synology Surveillance Station tools.

Provides MCP tools for managing cameras in Surveillance Station.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from logging_config import get_logger, ToolInvocationLogger
from tool_registry import tool

from .client import (
    SynologyClient,
    SynologyConnectionError,
    SynologyAuthError,
    SynologyAPIError,
    SynologyCamera,
)

logger = get_logger(__name__)


# -----------------------------------------------------------------------------
# Input/Output Schemas
# -----------------------------------------------------------------------------

class CameraInfoOutput(BaseModel):
    """Camera information."""
    id: int = Field(description="Camera ID")
    name: str = Field(description="Camera name")
    enabled: bool = Field(description="Whether camera is enabled")
    status: str = Field(description="Camera status")
    ip_address: str = Field(description="Camera IP address")
    model: str = Field(description="Camera model")


class SynologyListCamerasInput(BaseModel):
    """Input schema for synology_list_cameras tool."""
    pass  # No parameters needed


class SynologyListCamerasOutput(BaseModel):
    """Output schema for synology_list_cameras tool."""
    success: bool = Field(description="Whether the operation succeeded")
    cameras: List[CameraInfoOutput] = Field(
        default_factory=list,
        description="List of cameras"
    )
    camera_count: int = Field(default=0, description="Number of cameras")
    error: str = Field(default="", description="Error message if failed")


class SynologyGetCameraInfoInput(BaseModel):
    """Input schema for synology_get_camera_info tool."""
    camera_id: int = Field(description="Camera ID")


class SynologyGetCameraInfoOutput(BaseModel):
    """Output schema for synology_get_camera_info tool."""
    success: bool = Field(description="Whether the operation succeeded")
    camera: Optional[CameraInfoOutput] = Field(
        default=None,
        description="Camera information"
    )
    error: str = Field(default="", description="Error message if failed")


class SynologyEnableCameraInput(BaseModel):
    """Input schema for synology_enable_camera tool."""
    camera_id: int = Field(description="Camera ID")
    enabled: bool = Field(default=True, description="Enable (true) or disable (false) the camera")


class SynologyEnableCameraOutput(BaseModel):
    """Output schema for synology_enable_camera tool."""
    success: bool = Field(description="Whether the operation succeeded")
    error: str = Field(default="", description="Error message if failed")


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def _camera_to_output(cam: SynologyCamera) -> CameraInfoOutput:
    """Convert SynologyCamera to CameraInfoOutput."""
    return CameraInfoOutput(
        id=cam.id,
        name=cam.name,
        enabled=cam.enabled,
        status=cam.status,
        ip_address=cam.ip_address,
        model=cam.model,
    )


# -----------------------------------------------------------------------------
# Tool Implementations
# -----------------------------------------------------------------------------

@tool(
    name="synology_list_cameras",
    description="List all cameras in Synology Surveillance Station",
    input_schema=SynologyListCamerasInput,
    output_schema=SynologyListCamerasOutput,
    tags=["synology", "surveillance", "cameras"]
)
async def synology_list_cameras(params: SynologyListCamerasInput) -> SynologyListCamerasOutput:
    """List all cameras in Surveillance Station."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_list_cameras")
    
    try:
        async with SynologyClient() as client:
            cameras = await client.list_cameras()
            
            camera_list = [_camera_to_output(c) for c in cameras]
            
            invocation_logger.success(camera_count=len(camera_list))
            
            return SynologyListCamerasOutput(
                success=True,
                cameras=camera_list,
                camera_count=len(camera_list),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyListCamerasOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyListCamerasOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyListCamerasOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyListCamerasOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_get_camera_info",
    description="Get information about a specific camera in Synology Surveillance Station",
    input_schema=SynologyGetCameraInfoInput,
    output_schema=SynologyGetCameraInfoOutput,
    tags=["synology", "surveillance", "cameras"]
)
async def synology_get_camera_info(params: SynologyGetCameraInfoInput) -> SynologyGetCameraInfoOutput:
    """Get information about a specific camera."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_get_camera_info", camera_id=params.camera_id)
    
    try:
        async with SynologyClient() as client:
            camera = await client.get_camera_info(params.camera_id)
            
            invocation_logger.success()
            
            return SynologyGetCameraInfoOutput(
                success=True,
                camera=_camera_to_output(camera),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyGetCameraInfoOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyGetCameraInfoOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyGetCameraInfoOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyGetCameraInfoOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_enable_camera",
    description="Enable or disable a camera in Synology Surveillance Station",
    input_schema=SynologyEnableCameraInput,
    output_schema=SynologyEnableCameraOutput,
    tags=["synology", "surveillance", "cameras"]
)
async def synology_enable_camera(params: SynologyEnableCameraInput) -> SynologyEnableCameraOutput:
    """Enable or disable a camera."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_enable_camera", camera_id=params.camera_id, enabled=params.enabled)
    
    try:
        async with SynologyClient() as client:
            await client.enable_camera(params.camera_id, params.enabled)
            
            invocation_logger.success()
            
            return SynologyEnableCameraOutput(success=True)
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyEnableCameraOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyEnableCameraOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyEnableCameraOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyEnableCameraOutput(success=False, error=f"Unexpected error: {e}")

