"""HTTP Health Probe tool implementation.

Provides the monitor.http_health_probe tool for checking endpoint health.
"""

import time
from typing import Literal, Optional
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field, field_validator

from config import get_settings
from logging_config import get_logger, ToolInvocationLogger
from tool_registry import tool

logger = get_logger(__name__)


class HttpHealthProbeInput(BaseModel):
    """Input schema for monitor.http_health_probe tool."""
    
    url: str = Field(
        description="URL to probe (must be http or https)"
    )
    method: str = Field(
        default="GET",
        description="HTTP method to use"
    )
    expected_status: int = Field(
        default=200,
        description="Expected HTTP status code for healthy response"
    )
    timeout_seconds: Optional[int] = Field(
        default=None,
        description="Request timeout in seconds (uses default if not specified)"
    )
    
    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format."""
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must use http or https scheme")
        if not parsed.netloc:
            raise ValueError("URL must have a valid host")
        return v
    
    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        """Validate HTTP method."""
        allowed_methods = ["GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS"]
        v_upper = v.upper()
        if v_upper not in allowed_methods:
            raise ValueError(f"Method must be one of: {', '.join(allowed_methods)}")
        return v_upper
    
    @field_validator("expected_status")
    @classmethod
    def validate_status(cls, v: int) -> int:
        """Validate expected status code."""
        if not (100 <= v <= 599):
            raise ValueError("Expected status must be between 100 and 599")
        return v


class HttpHealthProbeOutput(BaseModel):
    """Output schema for monitor.http_health_probe tool."""
    
    status: Literal["healthy", "unhealthy"] = Field(
        description="Health status based on response"
    )
    http_status: Optional[int] = Field(
        description="HTTP status code received (null if connection failed)"
    )
    response_time_ms: int = Field(
        description="Response time in milliseconds"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if probe failed"
    )


@tool(
    name="monitor.http_health_probe",
    description="Perform HTTP health check on a URL endpoint",
    input_schema=HttpHealthProbeInput,
    output_schema=HttpHealthProbeOutput,
    tags=["monitoring", "health", "http"]
)
async def http_health_probe(params: HttpHealthProbeInput) -> HttpHealthProbeOutput:
    """Perform HTTP health probe on a URL.
    
    Args:
        params: Validated input parameters
        
    Returns:
        Health probe result
    """
    settings = get_settings()
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start(
        "monitor.http_health_probe",
        url=params.url,
        method=params.method,
        expected_status=params.expected_status
    )
    
    # Determine timeout
    timeout = params.timeout_seconds
    if timeout is None:
        timeout = settings.http_probe_default_timeout
    else:
        # Cap at maximum
        timeout = min(timeout, settings.http_probe_max_timeout)
    
    start_time = time.perf_counter()
    
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,  # Don't follow redirects by default
        ) as client:
            response = await client.request(
                method=params.method,
                url=params.url,
            )
        
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        
        # Determine health status
        is_healthy = response.status_code == params.expected_status
        status = "healthy" if is_healthy else "unhealthy"
        
        if is_healthy:
            invocation_logger.success(
                http_status=response.status_code,
                response_time_ms=elapsed_ms
            )
        else:
            invocation_logger.failure(
                f"Unexpected status: {response.status_code}",
                http_status=response.status_code,
                response_time_ms=elapsed_ms
            )
        
        return HttpHealthProbeOutput(
            status=status,
            http_status=response.status_code,
            response_time_ms=elapsed_ms,
            error=None if is_healthy else f"Expected status {params.expected_status}, got {response.status_code}"
        )
        
    except httpx.TimeoutException:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        error_msg = f"Request timed out after {timeout} seconds"
        invocation_logger.failure(error_msg, response_time_ms=elapsed_ms)
        
        return HttpHealthProbeOutput(
            status="unhealthy",
            http_status=None,
            response_time_ms=elapsed_ms,
            error=error_msg
        )
        
    except httpx.ConnectError as e:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        error_msg = f"Connection failed: {str(e)}"
        invocation_logger.failure(error_msg, response_time_ms=elapsed_ms)
        
        return HttpHealthProbeOutput(
            status="unhealthy",
            http_status=None,
            response_time_ms=elapsed_ms,
            error=error_msg
        )
        
    except httpx.RequestError as e:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        error_msg = f"Request failed: {str(e)}"
        invocation_logger.failure(error_msg, response_time_ms=elapsed_ms)
        
        return HttpHealthProbeOutput(
            status="unhealthy",
            http_status=None,
            response_time_ms=elapsed_ms,
            error=error_msg
        )
        
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        error_msg = f"Unexpected error: {str(e)}"
        invocation_logger.failure(error_msg, response_time_ms=elapsed_ms)
        
        return HttpHealthProbeOutput(
            status="unhealthy",
            http_status=None,
            response_time_ms=elapsed_ms,
            error=error_msg
        )

