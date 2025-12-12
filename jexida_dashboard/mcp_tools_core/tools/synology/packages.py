"""Synology package management tools.

Provides MCP tools for managing DSM packages on Synology NAS.
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
    SynologyPackage,
)

logger = get_logger(__name__)


# -----------------------------------------------------------------------------
# Input/Output Schemas
# -----------------------------------------------------------------------------

class PackageInfoOutput(BaseModel):
    """DSM package information."""
    id: str = Field(description="Package ID")
    name: str = Field(description="Package display name")
    version: str = Field(description="Package version")
    status: str = Field(description="Status: running or stopped")
    description: str = Field(description="Package description")


class SynologyListPackagesInput(BaseModel):
    """Input schema for synology_list_packages tool."""
    installed_only: bool = Field(
        default=True,
        description="Only return installed packages"
    )


class SynologyListPackagesOutput(BaseModel):
    """Output schema for synology_list_packages tool."""
    success: bool = Field(description="Whether the operation succeeded")
    packages: List[PackageInfoOutput] = Field(
        default_factory=list,
        description="List of packages"
    )
    package_count: int = Field(default=0, description="Number of packages")
    error: str = Field(default="", description="Error message if failed")


class SynologyInstallPackageInput(BaseModel):
    """Input schema for synology_install_package tool."""
    package_name: str = Field(description="Package ID/name to install")


class SynologyInstallPackageOutput(BaseModel):
    """Output schema for synology_install_package tool."""
    success: bool = Field(description="Whether the operation succeeded")
    package_name: str = Field(default="", description="Installed package name")
    error: str = Field(default="", description="Error message if failed")


class SynologyUninstallPackageInput(BaseModel):
    """Input schema for synology_uninstall_package tool."""
    package_name: str = Field(description="Package ID/name to uninstall")


class SynologyUninstallPackageOutput(BaseModel):
    """Output schema for synology_uninstall_package tool."""
    success: bool = Field(description="Whether the operation succeeded")
    error: str = Field(default="", description="Error message if failed")


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def _package_to_output(pkg: SynologyPackage) -> PackageInfoOutput:
    """Convert SynologyPackage to PackageInfoOutput."""
    return PackageInfoOutput(
        id=pkg.id,
        name=pkg.name,
        version=pkg.version,
        status=pkg.status,
        description=pkg.description,
    )


# -----------------------------------------------------------------------------
# Tool Implementations
# -----------------------------------------------------------------------------

@tool(
    name="synology_list_packages",
    description="List DSM packages on Synology NAS",
    input_schema=SynologyListPackagesInput,
    output_schema=SynologyListPackagesOutput,
    tags=["synology", "packages", "admin"]
)
async def synology_list_packages(params: SynologyListPackagesInput) -> SynologyListPackagesOutput:
    """List DSM packages."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_list_packages", installed_only=params.installed_only)
    
    try:
        async with SynologyClient() as client:
            packages = await client.list_packages(installed_only=params.installed_only)
            
            package_list = [_package_to_output(p) for p in packages]
            
            invocation_logger.success(package_count=len(package_list))
            
            return SynologyListPackagesOutput(
                success=True,
                packages=package_list,
                package_count=len(package_list),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyListPackagesOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyListPackagesOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyListPackagesOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyListPackagesOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_install_package",
    description="Install a DSM package on Synology NAS",
    input_schema=SynologyInstallPackageInput,
    output_schema=SynologyInstallPackageOutput,
    tags=["synology", "packages", "admin"]
)
async def synology_install_package(params: SynologyInstallPackageInput) -> SynologyInstallPackageOutput:
    """Install a DSM package."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_install_package", package_name=params.package_name)
    
    try:
        async with SynologyClient() as client:
            await client.install_package(params.package_name)
            
            invocation_logger.success()
            
            return SynologyInstallPackageOutput(
                success=True,
                package_name=params.package_name,
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyInstallPackageOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyInstallPackageOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyInstallPackageOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyInstallPackageOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_uninstall_package",
    description="Uninstall a DSM package from Synology NAS",
    input_schema=SynologyUninstallPackageInput,
    output_schema=SynologyUninstallPackageOutput,
    tags=["synology", "packages", "admin"]
)
async def synology_uninstall_package(params: SynologyUninstallPackageInput) -> SynologyUninstallPackageOutput:
    """Uninstall a DSM package."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_uninstall_package", package_name=params.package_name)
    
    try:
        async with SynologyClient() as client:
            await client.uninstall_package(params.package_name)
            
            invocation_logger.success()
            
            return SynologyUninstallPackageOutput(success=True)
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyUninstallPackageOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyUninstallPackageOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyUninstallPackageOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyUninstallPackageOutput(success=False, error=f"Unexpected error: {e}")

