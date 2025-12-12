"""Network scanning tool using nmap.

Provides the network_scan_local tool for discovering devices and open ports
on local network subnets.
"""

import asyncio
import re
import subprocess
import xml.etree.ElementTree as ET
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from config import get_settings
from logging_config import get_logger, ToolInvocationLogger
from tool_registry import tool

logger = get_logger(__name__)


class NmapError(Exception):
    """Error running nmap scan."""
    pass


class NmapValidationError(Exception):
    """Input validation error for nmap parameters."""
    pass


# Regex patterns for input validation
CIDR_PATTERN = re.compile(
    r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
    r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)"
    r"(?:/(?:3[0-2]|[12]?[0-9]))?$"
)

PORT_RANGE_PATTERN = re.compile(r"^[\d,\-]+$")

# Allowed port presets
PORT_PRESETS = {
    "top-100": "--top-ports 100",
    "top-1000": "--top-ports 1000",
    "common": "-p 21,22,23,25,53,80,110,139,143,443,445,993,995,3306,3389,5432,8080",
}


def validate_subnet(subnet: str) -> bool:
    """Validate a subnet string is safe and properly formatted.
    
    Args:
        subnet: CIDR notation subnet (e.g., 192.168.1.0/24)
        
    Returns:
        True if valid, False otherwise
    """
    if not subnet:
        return False
    
    # Check for shell metacharacters
    dangerous_chars = [";", "&", "|", ">", "<", "`", "$", "(", ")", "{", "}", "[", "]", "\\", "'", '"', "\n", "\r"]
    if any(c in subnet for c in dangerous_chars):
        return False
    
    return bool(CIDR_PATTERN.match(subnet))


def validate_ports(ports: str) -> bool:
    """Validate a port specification is safe.
    
    Args:
        ports: Port specification (e.g., "1-1024" or "22,80,443")
        
    Returns:
        True if valid, False otherwise
    """
    if not ports:
        return True  # Empty is OK, we'll use defaults
    
    # Check for presets
    if ports.lower() in PORT_PRESETS:
        return True
    
    # Check for shell metacharacters
    dangerous_chars = [";", "&", "|", ">", "<", "`", "$", "(", ")", "{", "}", "[", "]", "\\", "'", '"', "\n", "\r", " "]
    if any(c in ports for c in dangerous_chars):
        return False
    
    return bool(PORT_RANGE_PATTERN.match(ports))


# -------------------------------------------------------------------------
# Input/Output Models
# -------------------------------------------------------------------------

class NetworkScanInput(BaseModel):
    """Input schema for network_scan_local tool."""
    
    subnets: List[str] = Field(
        description="List of subnets to scan in CIDR notation (e.g., ['192.168.1.0/24'])"
    )
    ports: Optional[str] = Field(
        default="top-100",
        description="Port specification: 'top-100', 'top-1000', 'common', or port range like '1-1024' or '22,80,443'"
    )
    
    @field_validator("subnets")
    @classmethod
    def validate_subnets(cls, v: List[str]) -> List[str]:
        """Validate all subnets."""
        if not v:
            raise ValueError("At least one subnet is required")
        if len(v) > 10:
            raise ValueError("Maximum 10 subnets per scan")
        
        for subnet in v:
            if not validate_subnet(subnet):
                raise ValueError(f"Invalid or unsafe subnet: {subnet}")
        
        return v
    
    @field_validator("ports")
    @classmethod
    def validate_ports_field(cls, v: Optional[str]) -> Optional[str]:
        """Validate port specification."""
        if v and not validate_ports(v):
            raise ValueError(f"Invalid or unsafe port specification: {v}")
        return v


class PortInfo(BaseModel):
    """Information about an open port."""
    
    port: int = Field(description="Port number")
    protocol: str = Field(description="Protocol (tcp/udp)")
    state: str = Field(description="Port state (open, filtered, closed)")
    service: str = Field(description="Service name if detected")
    version: str = Field(default="", description="Service version if detected")


class HostInfo(BaseModel):
    """Information about a discovered host."""
    
    ip: str = Field(description="IP address")
    mac: str = Field(default="", description="MAC address if available")
    hostname: str = Field(default="", description="Hostname if resolved")
    vendor: str = Field(default="", description="Hardware vendor from MAC lookup")
    state: str = Field(description="Host state (up/down)")
    ports: List[PortInfo] = Field(default_factory=list, description="Open ports")


class NetworkScanOutput(BaseModel):
    """Output schema for network_scan_local tool."""
    
    success: bool = Field(description="Whether the scan completed successfully")
    hosts: List[HostInfo] = Field(default_factory=list, description="Discovered hosts")
    hosts_up: int = Field(default=0, description="Number of hosts found up")
    hosts_total: int = Field(default=0, description="Total hosts scanned")
    scan_duration_seconds: float = Field(default=0, description="Scan duration")
    command_executed: str = Field(default="", description="Nmap command that was run")
    error: str = Field(default="", description="Error message if failed")


def parse_nmap_xml(xml_output: str) -> NetworkScanOutput:
    """Parse nmap XML output into structured result.
    
    Args:
        xml_output: Raw XML output from nmap -oX
        
    Returns:
        Parsed scan results
    """
    try:
        root = ET.fromstring(xml_output)
    except ET.ParseError as e:
        raise NmapError(f"Failed to parse nmap XML output: {e}")
    
    hosts = []
    
    # Parse run stats
    runstats = root.find("runstats")
    scan_duration = 0.0
    hosts_up = 0
    hosts_total = 0
    
    if runstats is not None:
        finished = runstats.find("finished")
        if finished is not None:
            scan_duration = float(finished.get("elapsed", 0))
        
        hosts_stat = runstats.find("hosts")
        if hosts_stat is not None:
            hosts_up = int(hosts_stat.get("up", 0))
            hosts_total = int(hosts_stat.get("total", 0))
    
    # Parse each host
    for host_elem in root.findall("host"):
        # Get state
        status = host_elem.find("status")
        state = status.get("state", "unknown") if status is not None else "unknown"
        
        if state != "up":
            continue
        
        # Get IP address
        ip = ""
        mac = ""
        vendor = ""
        
        for addr in host_elem.findall("address"):
            addr_type = addr.get("addrtype", "")
            if addr_type == "ipv4":
                ip = addr.get("addr", "")
            elif addr_type == "mac":
                mac = addr.get("addr", "")
                vendor = addr.get("vendor", "")
        
        if not ip:
            continue
        
        # Get hostname
        hostname = ""
        hostnames = host_elem.find("hostnames")
        if hostnames is not None:
            hostname_elem = hostnames.find("hostname")
            if hostname_elem is not None:
                hostname = hostname_elem.get("name", "")
        
        # Get ports
        ports = []
        ports_elem = host_elem.find("ports")
        if ports_elem is not None:
            for port_elem in ports_elem.findall("port"):
                port_num = int(port_elem.get("portid", 0))
                protocol = port_elem.get("protocol", "tcp")
                
                state_elem = port_elem.find("state")
                port_state = state_elem.get("state", "unknown") if state_elem is not None else "unknown"
                
                service_elem = port_elem.find("service")
                service_name = ""
                service_version = ""
                if service_elem is not None:
                    service_name = service_elem.get("name", "")
                    product = service_elem.get("product", "")
                    version = service_elem.get("version", "")
                    service_version = f"{product} {version}".strip()
                
                ports.append(PortInfo(
                    port=port_num,
                    protocol=protocol,
                    state=port_state,
                    service=service_name,
                    version=service_version,
                ))
        
        hosts.append(HostInfo(
            ip=ip,
            mac=mac,
            hostname=hostname,
            vendor=vendor,
            state=state,
            ports=ports,
        ))
    
    return NetworkScanOutput(
        success=True,
        hosts=hosts,
        hosts_up=hosts_up,
        hosts_total=hosts_total,
        scan_duration_seconds=scan_duration,
    )


@tool(
    name="network_scan_local",
    description="Run a local network scan using nmap to discover devices and open ports",
    input_schema=NetworkScanInput,
    output_schema=NetworkScanOutput,
    tags=["network", "security", "scan"]
)
async def network_scan_local(params: NetworkScanInput) -> NetworkScanOutput:
    """Run a network scan using nmap.
    
    Args:
        params: Scan parameters including subnets and port specification
        
    Returns:
        Scan results with discovered hosts and open ports
    """
    settings = get_settings()
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start(
        "network_scan_local",
        subnet_count=len(params.subnets),
        ports=params.ports,
    )
    
    try:
        # Build nmap command
        cmd = [settings.nmap_path]
        
        # Output as XML to stdout
        cmd.extend(["-oX", "-"])
        
        # Add port specification
        if params.ports:
            ports_lower = params.ports.lower()
            if ports_lower in PORT_PRESETS:
                cmd.extend(PORT_PRESETS[ports_lower].split())
            else:
                cmd.extend(["-p", params.ports])
        else:
            cmd.extend(["--top-ports", "100"])
        
        # Add reasonable scan options
        cmd.extend([
            "-sV",           # Version detection
            "--version-light",  # Light version detection (faster)
            "-T4",           # Aggressive timing
            "-n",            # No DNS resolution (faster)
            "--open",        # Only show open ports
        ])
        
        # Add subnets
        cmd.extend(params.subnets)
        
        command_str = " ".join(cmd)
        logger.info(f"Running nmap scan: {command_str}")
        
        # Execute nmap
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=settings.nmap_timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            invocation_logger.failure("Scan timed out")
            return NetworkScanOutput(
                success=False,
                error=f"Scan timed out after {settings.nmap_timeout} seconds",
                command_executed=command_str,
            )
        
        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")
        
        if process.returncode != 0:
            invocation_logger.failure(f"nmap exited with code {process.returncode}")
            return NetworkScanOutput(
                success=False,
                error=f"nmap failed: {stderr_str}",
                command_executed=command_str,
            )
        
        # Parse XML output
        result = parse_nmap_xml(stdout_str)
        result.command_executed = command_str
        
        invocation_logger.success(
            hosts_up=result.hosts_up,
            hosts_total=result.hosts_total,
            duration=result.scan_duration_seconds,
        )
        
        return result
        
    except FileNotFoundError:
        invocation_logger.failure("nmap not found")
        return NetworkScanOutput(
            success=False,
            error=f"nmap not found at '{settings.nmap_path}'. Please install nmap.",
        )
    except NmapError as e:
        invocation_logger.failure(str(e))
        return NetworkScanOutput(
            success=False,
            error=str(e),
        )
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return NetworkScanOutput(
            success=False,
            error=f"Unexpected error: {e}",
        )

