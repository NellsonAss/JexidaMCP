"""Synology Virtual Machine Manager tools.

Provides MCP tools for managing virtual machines on Synology NAS.
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

class VirtualMachineOutput(BaseModel):
    """Virtual machine information."""
    guest_id: str = Field(description="VM ID")
    guest_name: str = Field(description="VM name")
    status: str = Field(description="VM status")
    vcpu_num: int = Field(description="Number of vCPUs")
    vram_size: int = Field(description="RAM size in MB")
    autorun: int = Field(description="Auto-start priority")


class SynologyListVirtualMachinesInput(BaseModel):
    """Input schema for synology_list_virtual_machines tool."""
    pass


class SynologyListVirtualMachinesOutput(BaseModel):
    """Output schema for synology_list_virtual_machines tool."""
    success: bool = Field(description="Whether the operation succeeded")
    vms: List[VirtualMachineOutput] = Field(
        default_factory=list,
        description="List of virtual machines"
    )
    vm_count: int = Field(default=0, description="Number of VMs")
    error: str = Field(default="", description="Error message if failed")


class SynologyGetVmInfoInput(BaseModel):
    """Input schema for synology_get_vm_info tool."""
    guest_id: str = Field(description="VM ID")


class SynologyGetVmInfoOutput(BaseModel):
    """Output schema for synology_get_vm_info tool."""
    success: bool = Field(description="Whether the operation succeeded")
    vm: Optional[Dict[str, Any]] = Field(
        default=None,
        description="VM details"
    )
    error: str = Field(default="", description="Error message if failed")


class SynologyStartVmInput(BaseModel):
    """Input schema for synology_start_vm tool."""
    guest_id: str = Field(description="VM ID to start")


class SynologyStartVmOutput(BaseModel):
    """Output schema for synology_start_vm tool."""
    success: bool = Field(description="Whether the operation succeeded")
    error: str = Field(default="", description="Error message if failed")


class SynologyStopVmInput(BaseModel):
    """Input schema for synology_stop_vm tool."""
    guest_id: str = Field(description="VM ID to stop")
    force: bool = Field(default=False, description="Force power off instead of graceful shutdown")


class SynologyStopVmOutput(BaseModel):
    """Output schema for synology_stop_vm tool."""
    success: bool = Field(description="Whether the operation succeeded")
    error: str = Field(default="", description="Error message if failed")


# -----------------------------------------------------------------------------
# Tool Implementations
# -----------------------------------------------------------------------------

@tool(
    name="synology_list_virtual_machines",
    description="List virtual machines in Synology Virtual Machine Manager",
    input_schema=SynologyListVirtualMachinesInput,
    output_schema=SynologyListVirtualMachinesOutput,
    tags=["synology", "vmm", "virtualization"]
)
async def synology_list_virtual_machines(params: SynologyListVirtualMachinesInput) -> SynologyListVirtualMachinesOutput:
    """List virtual machines."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_list_virtual_machines")
    
    try:
        async with SynologyClient() as client:
            vms = await client.list_virtual_machines()
            
            vm_list = [
                VirtualMachineOutput(
                    guest_id=vm.get("guest_id", ""),
                    guest_name=vm.get("guest_name", ""),
                    status=vm.get("status", ""),
                    vcpu_num=vm.get("vcpu_num", 0),
                    vram_size=vm.get("vram_size", 0),
                    autorun=vm.get("autorun", 0),
                )
                for vm in vms
            ]
            
            invocation_logger.success(vm_count=len(vm_list))
            
            return SynologyListVirtualMachinesOutput(
                success=True,
                vms=vm_list,
                vm_count=len(vm_list),
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyListVirtualMachinesOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyListVirtualMachinesOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyListVirtualMachinesOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyListVirtualMachinesOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_get_vm_info",
    description="Get detailed information about a virtual machine",
    input_schema=SynologyGetVmInfoInput,
    output_schema=SynologyGetVmInfoOutput,
    tags=["synology", "vmm", "virtualization"]
)
async def synology_get_vm_info(params: SynologyGetVmInfoInput) -> SynologyGetVmInfoOutput:
    """Get VM details."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_get_vm_info", guest_id=params.guest_id)
    
    try:
        async with SynologyClient() as client:
            vm = await client.get_vm_info(params.guest_id)
            
            invocation_logger.success()
            
            return SynologyGetVmInfoOutput(
                success=True,
                vm=vm,
            )
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyGetVmInfoOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyGetVmInfoOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyGetVmInfoOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyGetVmInfoOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_start_vm",
    description="Start a virtual machine in Synology Virtual Machine Manager",
    input_schema=SynologyStartVmInput,
    output_schema=SynologyStartVmOutput,
    tags=["synology", "vmm", "virtualization"]
)
async def synology_start_vm(params: SynologyStartVmInput) -> SynologyStartVmOutput:
    """Start a virtual machine."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_start_vm", guest_id=params.guest_id)
    
    try:
        async with SynologyClient() as client:
            await client.start_vm(params.guest_id)
            
            invocation_logger.success()
            
            return SynologyStartVmOutput(success=True)
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyStartVmOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyStartVmOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyStartVmOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyStartVmOutput(success=False, error=f"Unexpected error: {e}")


@tool(
    name="synology_stop_vm",
    description="Stop a virtual machine in Synology Virtual Machine Manager",
    input_schema=SynologyStopVmInput,
    output_schema=SynologyStopVmOutput,
    tags=["synology", "vmm", "virtualization"]
)
async def synology_stop_vm(params: SynologyStopVmInput) -> SynologyStopVmOutput:
    """Stop a virtual machine."""
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start("synology_stop_vm", guest_id=params.guest_id, force=params.force)
    
    try:
        async with SynologyClient() as client:
            await client.stop_vm(params.guest_id, params.force)
            
            invocation_logger.success()
            
            return SynologyStopVmOutput(success=True)
            
    except SynologyConnectionError as e:
        invocation_logger.failure(str(e))
        return SynologyStopVmOutput(success=False, error=f"Connection error: {e}")
    except SynologyAuthError as e:
        invocation_logger.failure(str(e))
        return SynologyStopVmOutput(success=False, error=f"Authentication error: {e}")
    except SynologyAPIError as e:
        invocation_logger.failure(str(e))
        return SynologyStopVmOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return SynologyStopVmOutput(success=False, error=f"Unexpected error: {e}")

