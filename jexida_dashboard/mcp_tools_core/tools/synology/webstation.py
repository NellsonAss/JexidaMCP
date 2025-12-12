"""Synology Web Station tools.

Provides MCP tools for managing Web Station on Synology NAS.
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

class WebServiceOutput(BaseModel):
    """Web service/virtual host information."""
    id: str = Field(description="Service ID")
    service_id: str = Field(description="Service identifier")
    fqdn: str = Field(description="Fully qualified domain name")
    root: str = Field(description="Document root path")
    backend: str = Field(description="Backend server (nginx/apache)")
    php: str = Field(description="PHP profile")
    status: str = Field(description="Service status")
    https: bool = Field(description="HTTPS enabled")
    http_port: int = Field(description="HTTP port")
    https_port: int = Field(description="HTTPS port")


class SynologyListWebServicesInput(BaseModel):
    """Input schema for synology_list_web_services tool."""
    pass


class SynologyListWebServicesOutput(BaseModel):
    """Output schema for synology_list_web_services tool."""
    success: bool = Field(description="Whether the operation succeeded")
    services: List[WebServiceOutput] = Field(
        default_factory=list,
        description="List of web services"
    )
    service_count: int = Field(default=0, description="Number of services")
    error: str = Field(default="", description="Error message if failed")


class PhpProfileOutput(BaseModel):
    """PHP profile information."""
    id: str = Field(description="Profile ID")
    display_name: str = Field(description="Display name")
    version: str = Field(description="PHP version")
    enable: bool = Field(description="Whether profile is enabled")


class SynologyListPhpProfilesInput(BaseModel):
    """Input schema for synology_list_php_profiles tool."""
    pass


class SynologyListPhpProfilesOutput(BaseModel):
    """Output schema for synology_list_php_profiles tool."""
    success: bool = Field(description="Whether the operation succeeded")
    profiles: List[PhpProfileOutput] = Field(
        default_factory=list,
        description="List of PHP profiles"
    )
    profile_count: int = Field(default=0, description="Number of profiles")
    error: str = Field(default="", description="Error message if failed")


class SynologyGetWebstationStatusInput(BaseModel):
    """Input schema for synology_get_webstation_status tool."""
    pass


class SynologyGetWebstationStatusOutput(BaseModel):
    """Output schema for synology_get_webstation_status tool."""
    success: bool = Field(description="Whether the operation succeeded")
    nginx_status: str = Field(default="", description="Nginx status")
    apache_status: str = Field(default="", description="Apache status")
    php_status: str = Field(default="", description="PHP status")
    error: str = Field(default="", description="Error message if failed")


# -----------------------------------------------------------------------------
# Tool Implementations
# -----------------------------------------------------------------------------

@tool(
    name="synology_list_web_services",
    description="List all web services/virtual hosts in Synology Web Station",
    input_schema=SynologyListWebServicesInput,
    output_schema=SynologyListWebServicesOutput,
    tags=["synology", "webstation", "web"]
)
async def synology_list_web_services(params: SynologyListWebServicesInput) -> SynologyListWebServicesOutput:
    """List all web services."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_list_web_services")
    
    try:
        async with SynologyClient() as client:
            services = await client.list_web_services()
            
            service_list = [
                WebServiceOutput(
                    id=s.get("id", ""),
                    service_id=s.get("service_id", ""),
                    fqdn=s.get("fqdn", ""),
                    root=s.get("root", ""),
                    backend=s.get("backend", ""),
                    php=s.get("php", ""),
                    status=s.get("status", ""),
                    https=s.get("https", False),
                    http_port=s.get("http_port", 80),
                    https_port=s.get("https_port", 443),
                )
                for s in services
            ]
            
            invocation_logger.success(service_count=len(service_list))
            
            return SynologyListWebServicesOutput(
                success=True,
                services=service_list,
                service_count=len(service_list),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyListWebServicesOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyListWebServicesOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyListWebServicesOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyListWebServicesOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_list_php_profiles",
    description="List PHP profiles available in Synology Web Station",
    input_schema=SynologyListPhpProfilesInput,
    output_schema=SynologyListPhpProfilesOutput,
    tags=["synology", "webstation", "php"]
)
async def synology_list_php_profiles(params: SynologyListPhpProfilesInput) -> SynologyListPhpProfilesOutput:
    """List PHP profiles."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_list_php_profiles")
    
    try:
        async with SynologyClient() as client:
            profiles = await client.list_php_profiles()
            
            profile_list = [
                PhpProfileOutput(
                    id=p.get("id", ""),
                    display_name=p.get("display_name", ""),
                    version=p.get("version", ""),
                    enable=p.get("enable", False),
                )
                for p in profiles
            ]
            
            invocation_logger.success(profile_count=len(profile_list))
            
            return SynologyListPhpProfilesOutput(
                success=True,
                profiles=profile_list,
                profile_count=len(profile_list),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyListPhpProfilesOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyListPhpProfilesOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyListPhpProfilesOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyListPhpProfilesOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_get_webstation_status",
    description="Get Web Station status and configuration",
    input_schema=SynologyGetWebstationStatusInput,
    output_schema=SynologyGetWebstationStatusOutput,
    tags=["synology", "webstation", "status"]
)
async def synology_get_webstation_status(params: SynologyGetWebstationStatusInput) -> SynologyGetWebstationStatusOutput:
    """Get Web Station status."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_get_webstation_status")
    
    try:
        async with SynologyClient() as client:
            status = await client.get_webstation_status()
            
            invocation_logger.success()
            
            return SynologyGetWebstationStatusOutput(
                success=True,
                nginx_status=status.get("nginx_status", ""),
                apache_status=status.get("apache_status", ""),
                php_status=status.get("php_status", ""),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyGetWebstationStatusOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyGetWebstationStatusOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyGetWebstationStatusOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyGetWebstationStatusOutput(success=False, error=f"Unexpected error: {e}")

