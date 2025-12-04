"""Synology Security tools.

Provides MCP tools for managing security settings on Synology NAS.
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

class FirewallRuleOutput(BaseModel):
    """Firewall rule information."""
    name: str = Field(description="Rule name")
    action: str = Field(description="Action (allow/deny)")
    protocol: str = Field(description="Protocol")
    ports: str = Field(description="Ports")
    source_ip: str = Field(description="Source IP")
    enabled: bool = Field(description="Whether rule is enabled")


class BlockedIpOutput(BaseModel):
    """Blocked IP information."""
    ip: str = Field(description="IP address")
    block_time: int = Field(description="Block timestamp")
    expire_time: int = Field(description="Expiration timestamp")


class SynologyGetSecuritySettingsInput(BaseModel):
    """Input schema for synology_get_security_settings tool."""
    pass


class SynologyGetSecuritySettingsOutput(BaseModel):
    """Output schema for synology_get_security_settings tool."""
    success: bool = Field(description="Whether the operation succeeded")
    logout_timer: int = Field(default=0, description="Auto logout timer (minutes)")
    trust_ip_check: bool = Field(default=False, description="Trust IP check enabled")
    http_compression: bool = Field(default=False, description="HTTP compression enabled")
    cross_origin_request: bool = Field(default=False, description="Cross-origin requests enabled")
    error: str = Field(default="", description="Error message if failed")


class SynologyListFirewallRulesInput(BaseModel):
    """Input schema for synology_list_firewall_rules tool."""
    pass


class SynologyListFirewallRulesOutput(BaseModel):
    """Output schema for synology_list_firewall_rules tool."""
    success: bool = Field(description="Whether the operation succeeded")
    rules: List[FirewallRuleOutput] = Field(
        default_factory=list,
        description="List of firewall rules"
    )
    rule_count: int = Field(default=0, description="Number of rules")
    error: str = Field(default="", description="Error message if failed")


class SynologyGetAutoblockSettingsInput(BaseModel):
    """Input schema for synology_get_autoblock_settings tool."""
    pass


class SynologyGetAutoblockSettingsOutput(BaseModel):
    """Output schema for synology_get_autoblock_settings tool."""
    success: bool = Field(description="Whether the operation succeeded")
    enabled: bool = Field(default=False, description="Auto-block enabled")
    attempts: int = Field(default=0, description="Login attempts before block")
    within_minutes: int = Field(default=0, description="Time window for attempts")
    expire_days: int = Field(default=0, description="Block expiration days")
    blocked_count: int = Field(default=0, description="Number of blocked IPs")
    error: str = Field(default="", description="Error message if failed")


class SynologyListBlockedIpsInput(BaseModel):
    """Input schema for synology_list_blocked_ips tool."""
    pass


class SynologyListBlockedIpsOutput(BaseModel):
    """Output schema for synology_list_blocked_ips tool."""
    success: bool = Field(description="Whether the operation succeeded")
    blocked_ips: List[BlockedIpOutput] = Field(
        default_factory=list,
        description="List of blocked IPs"
    )
    blocked_count: int = Field(default=0, description="Number of blocked IPs")
    error: str = Field(default="", description="Error message if failed")


class SynologyRunSecurityScanInput(BaseModel):
    """Input schema for synology_run_security_scan tool."""
    pass


class SynologyRunSecurityScanOutput(BaseModel):
    """Output schema for synology_run_security_scan tool."""
    success: bool = Field(description="Whether the operation succeeded")
    task_id: str = Field(default="", description="Security scan task ID")
    status: str = Field(default="", description="Scan status")
    error: str = Field(default="", description="Error message if failed")


# -----------------------------------------------------------------------------
# Tool Implementations
# -----------------------------------------------------------------------------

@tool(
    name="synology_get_security_settings",
    description="Get security settings from Synology NAS",
    input_schema=SynologyGetSecuritySettingsInput,
    output_schema=SynologyGetSecuritySettingsOutput,
    tags=["synology", "security", "settings"]
)
async def synology_get_security_settings(params: SynologyGetSecuritySettingsInput) -> SynologyGetSecuritySettingsOutput:
    """Get security settings."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_get_security_settings")
    
    try:
        async with SynologyClient() as client:
            settings = await client.get_security_settings()
            
            invocation_logger.success()
            
            return SynologyGetSecuritySettingsOutput(
                success=True,
                logout_timer=settings.get("logout_timer", 0),
                trust_ip_check=settings.get("trust_ip_check", False),
                http_compression=settings.get("http_compression", False),
                cross_origin_request=settings.get("cross_origin_request", False),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyGetSecuritySettingsOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyGetSecuritySettingsOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyGetSecuritySettingsOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyGetSecuritySettingsOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_list_firewall_rules",
    description="List firewall rules on Synology NAS",
    input_schema=SynologyListFirewallRulesInput,
    output_schema=SynologyListFirewallRulesOutput,
    tags=["synology", "security", "firewall"]
)
async def synology_list_firewall_rules(params: SynologyListFirewallRulesInput) -> SynologyListFirewallRulesOutput:
    """List firewall rules."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_list_firewall_rules")
    
    try:
        async with SynologyClient() as client:
            rules = await client.list_firewall_rules()
            
            rule_list = [
                FirewallRuleOutput(
                    name=r.get("name", ""),
                    action=r.get("action", ""),
                    protocol=r.get("protocol", ""),
                    ports=r.get("ports", ""),
                    source_ip=r.get("source_ip", ""),
                    enabled=r.get("enabled", False),
                )
                for r in rules
            ]
            
            invocation_logger.success(rule_count=len(rule_list))
            
            return SynologyListFirewallRulesOutput(
                success=True,
                rules=rule_list,
                rule_count=len(rule_list),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyListFirewallRulesOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyListFirewallRulesOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyListFirewallRulesOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyListFirewallRulesOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_get_autoblock_settings",
    description="Get auto-block settings from Synology NAS",
    input_schema=SynologyGetAutoblockSettingsInput,
    output_schema=SynologyGetAutoblockSettingsOutput,
    tags=["synology", "security", "autoblock"]
)
async def synology_get_autoblock_settings(params: SynologyGetAutoblockSettingsInput) -> SynologyGetAutoblockSettingsOutput:
    """Get auto-block settings."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_get_autoblock_settings")
    
    try:
        async with SynologyClient() as client:
            settings = await client.get_autoblock_settings()
            
            invocation_logger.success()
            
            return SynologyGetAutoblockSettingsOutput(
                success=True,
                enabled=settings.get("enabled", False),
                attempts=settings.get("attempts", 0),
                within_minutes=settings.get("within_minutes", 0),
                expire_days=settings.get("expire_days", 0),
                blocked_count=settings.get("blocked_count", 0),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyGetAutoblockSettingsOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyGetAutoblockSettingsOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyGetAutoblockSettingsOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyGetAutoblockSettingsOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_list_blocked_ips",
    description="List blocked IP addresses on Synology NAS",
    input_schema=SynologyListBlockedIpsInput,
    output_schema=SynologyListBlockedIpsOutput,
    tags=["synology", "security", "autoblock"]
)
async def synology_list_blocked_ips(params: SynologyListBlockedIpsInput) -> SynologyListBlockedIpsOutput:
    """List blocked IP addresses."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_list_blocked_ips")
    
    try:
        async with SynologyClient() as client:
            blocked = await client.list_blocked_ips()
            
            blocked_list = [
                BlockedIpOutput(
                    ip=b.get("ip", ""),
                    block_time=b.get("block_time", 0),
                    expire_time=b.get("expire_time", 0),
                )
                for b in blocked
            ]
            
            invocation_logger.success(blocked_count=len(blocked_list))
            
            return SynologyListBlockedIpsOutput(
                success=True,
                blocked_ips=blocked_list,
                blocked_count=len(blocked_list),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyListBlockedIpsOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyListBlockedIpsOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyListBlockedIpsOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyListBlockedIpsOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_run_security_scan",
    description="Run a security advisor scan on Synology NAS",
    input_schema=SynologyRunSecurityScanInput,
    output_schema=SynologyRunSecurityScanOutput,
    tags=["synology", "security", "scan"]
)
async def synology_run_security_scan(params: SynologyRunSecurityScanInput) -> SynologyRunSecurityScanOutput:
    """Run security advisor scan."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_run_security_scan")
    
    try:
        async with SynologyClient() as client:
            result = await client.run_security_scan()
            
            invocation_logger.success()
            
            return SynologyRunSecurityScanOutput(
                success=True,
                task_id=result.get("task_id", ""),
                status=result.get("status", "started"),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyRunSecurityScanOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyRunSecurityScanOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyRunSecurityScanOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyRunSecurityScanOutput(success=False, error=f"Unexpected error: {e}")

