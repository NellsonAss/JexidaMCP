"""UniFi SSH Device Tools.

Provides SSH-based tools for UniFi devices:
- ssh_unifi_device_run: Run arbitrary SSH commands on UniFi devices
- ssh_unifi_device_info: Run predefined safe diagnostic commands
- ssh_unifi_device_adopt: Force device adoption via SSH
"""

import subprocess
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

import logging
logger = logging.getLogger(__name__)


class SSHUnifiDeviceRunInput(BaseModel):
    """Input schema for ssh_unifi_device_run tool."""
    
    host: str = Field(description="Device IP address or hostname")
    cmd: str = Field(description="SSH command to execute")
    username: str = Field(default="root", description="SSH username")
    timeout: int = Field(default=30, description="Command timeout in seconds")


class SSHUnifiDeviceRunOutput(BaseModel):
    """Output schema for ssh_unifi_device_run tool."""
    
    success: bool = Field(description="Whether command succeeded")
    exit_code: int = Field(default=0, description="Command exit code")
    stdout: str = Field(default="", description="Command stdout")
    stderr: str = Field(default="", description="Command stderr")
    error: str = Field(default="", description="Error message if failed")


async def ssh_unifi_device_run(params: SSHUnifiDeviceRunInput) -> SSHUnifiDeviceRunOutput:
    """Run an SSH command on a UniFi device.
    
    Used for troubleshooting, firmware checks, and deep metrics gathering.
    
    Args:
        params: SSH command parameters
        
    Returns:
        Command execution result
    """
    logger.info(f"ssh_unifi_device_run called: {params.host} - {params.cmd}")
    
    try:
        # Use subprocess to run SSH command
        # Note: In production, you'd want to use paramiko or asyncssh for better control
        ssh_cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=10",
            f"{params.username}@{params.host}",
            params.cmd,
        ]
        
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=params.timeout,
        )
        
        return SSHUnifiDeviceRunOutput(
            success=result.returncode == 0,
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
        
    except subprocess.TimeoutExpired:
        return SSHUnifiDeviceRunOutput(
            success=False,
            exit_code=-1,
            error=f"Command timed out after {params.timeout} seconds",
        )
    except Exception as e:
        return SSHUnifiDeviceRunOutput(
            success=False,
            exit_code=-1,
            error=f"SSH execution failed: {e}",
        )


class SSHUnifiDeviceInfoInput(BaseModel):
    """Input schema for ssh_unifi_device_info tool."""
    
    host: str = Field(description="Device IP address or hostname")
    username: str = Field(default="root", description="SSH username")


class DeviceInfo(BaseModel):
    """Device diagnostic information."""
    cpu_usage: str = Field(default="", description="CPU usage")
    memory_usage: str = Field(default="", description="Memory usage")
    disk_usage: str = Field(default="", description="Disk usage")
    radio_status: str = Field(default="", description="Radio status (APs)")
    poe_power: str = Field(default="", description="PoE power status (switches)")
    firmware: str = Field(default="", description="Firmware version")
    uptime: str = Field(default="", description="System uptime")


class SSHUnifiDeviceInfoOutput(BaseModel):
    """Output schema for ssh_unifi_device_info tool."""
    
    success: bool = Field(description="Whether info collection succeeded")
    host: str = Field(default="", description="Device host")
    info: Optional[DeviceInfo] = None
    error: str = Field(default="", description="Error message if failed")


async def ssh_unifi_device_info(params: SSHUnifiDeviceInfoInput) -> SSHUnifiDeviceInfoOutput:
    """Run predefined safe diagnostic commands on a UniFi device.
    
    Collects:
    - CPU usage
    - Memory usage
    - Radio status (APs)
    - PoE power (switches)
    - Firmware version
    - Uptime
    
    Args:
        params: Device info parameters
        
    Returns:
        Device diagnostic information
    """
    logger.info(f"ssh_unifi_device_info called: {params.host}")
    
    try:
        # Run diagnostic commands
        commands = {
            "cpu": "top -bn1 | grep 'Cpu(s)' | awk '{print $2}'",
            "memory": "free -h | grep Mem | awk '{print $3\"/\"$2}'",
            "disk": "df -h / | tail -1 | awk '{print $5}'",
            "firmware": "cat /etc/version",
            "uptime": "uptime",
        }
        
        results = {}
        for key, cmd in commands.items():
            result = await ssh_unifi_device_run(SSHUnifiDeviceRunInput(
                host=params.host,
                cmd=cmd,
                username=params.username,
            ))
            if result.success:
                results[key] = result.stdout.strip()
            else:
                results[key] = "N/A"
        
        # Try to get radio status (for APs)
        radio_result = await ssh_unifi_device_run(SSHUnifiDeviceRunInput(
            host=params.host,
            cmd="iwconfig 2>/dev/null | grep -E 'wlan|radio' || echo 'N/A'",
            username=params.username,
        ))
        radio_status = radio_result.stdout.strip() if radio_result.success else "N/A"
        
        # Try to get PoE status (for switches)
        poe_result = await ssh_unifi_device_run(SSHUnifiDeviceRunInput(
            host=params.host,
            cmd="cat /proc/power 2>/dev/null || echo 'N/A'",
            username=params.username,
        ))
        poe_power = poe_result.stdout.strip() if poe_result.success else "N/A"
        
        info = DeviceInfo(
            cpu_usage=results.get("cpu", "N/A"),
            memory_usage=results.get("memory", "N/A"),
            disk_usage=results.get("disk", "N/A"),
            radio_status=radio_status,
            poe_power=poe_power,
            firmware=results.get("firmware", "N/A"),
            uptime=results.get("uptime", "N/A"),
        )
        
        return SSHUnifiDeviceInfoOutput(
            success=True,
            host=params.host,
            info=info,
        )
        
    except Exception as e:
        return SSHUnifiDeviceInfoOutput(
            success=False,
            host=params.host,
            error=f"Failed to collect device info: {e}",
        )


class SSHUnifiDeviceAdoptInput(BaseModel):
    """Input schema for ssh_unifi_device_adopt tool."""
    
    host: str = Field(description="Device IP address or hostname")
    controller_url: str = Field(description="Controller URL (e.g., 'http://192.168.1.1:8080')")
    username: str = Field(default="root", description="SSH username")


class SSHUnifiDeviceAdoptOutput(BaseModel):
    """Output schema for ssh_unifi_device_adopt tool."""
    
    success: bool = Field(description="Whether adoption command succeeded")
    host: str = Field(default="", description="Device host")
    message: str = Field(default="", description="Status message")
    error: str = Field(default="", description="Error message if failed")


async def ssh_unifi_device_adopt(params: SSHUnifiDeviceAdoptInput) -> SSHUnifiDeviceAdoptOutput:
    """Force device adoption via SSH.
    
    Runs: set-inform http://<controller>/inform
    
    Used for adoption issues when devices won't adopt through the UI.
    
    Args:
        params: Adoption parameters
        
    Returns:
        Adoption result
    """
    logger.info(f"ssh_unifi_device_adopt called: {params.host} -> {params.controller_url}")
    
    try:
        inform_url = f"{params.controller_url}/inform"
        cmd = f"set-inform {inform_url}"
        
        result = await ssh_unifi_device_run(SSHUnifiDeviceRunInput(
            host=params.host,
            cmd=cmd,
            username=params.username,
        ))
        
        if result.success:
            return SSHUnifiDeviceAdoptOutput(
                success=True,
                host=params.host,
                message=f"Adoption command sent. Device should appear in controller shortly.",
            )
        else:
            return SSHUnifiDeviceAdoptOutput(
                success=False,
                host=params.host,
                error=f"Adoption command failed: {result.stderr}",
            )
            
    except Exception as e:
        return SSHUnifiDeviceAdoptOutput(
            success=False,
            host=params.host,
            error=f"Failed to run adoption command: {e}",
        )

