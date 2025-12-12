"""Azure Compute tools (Phase 2 - Stubs).

Provides MCP tools for:
- Creating virtual machines
- Deleting virtual machines
- Listing VMs in a resource group

NOTE: These are stub implementations. Full implementation is planned for Phase 2.
"""

import logging
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# Input/Output Schemas
# =============================================================================

class AzureComputeCreateVmInput(BaseModel):
    """Input schema for azure_compute_create_vm."""
    resource_group: str = Field(description="Resource group name")
    name: str = Field(description="VM name")
    location: str = Field(description="Azure region")
    size: str = Field(
        default="Standard_B1s",
        description="VM size (e.g., Standard_B1s, Standard_D2s_v3)"
    )
    image_reference: Dict[str, str] = Field(
        default_factory=lambda: {
            "publisher": "Canonical",
            "offer": "0001-com-ubuntu-server-jammy",
            "sku": "22_04-lts-gen2",
            "version": "latest"
        },
        description="Image reference (publisher, offer, sku, version)"
    )
    admin_username: str = Field(description="Administrator username")
    admin_password_secret_ref: Optional[str] = Field(
        default=None,
        description="Secret reference for admin password"
    )
    admin_ssh_public_key: Optional[str] = Field(
        default=None,
        description="SSH public key for Linux VMs"
    )
    vnet_name: Optional[str] = Field(default=None, description="Virtual network name")
    subnet_name: Optional[str] = Field(default=None, description="Subnet name")
    tags: Optional[Dict[str, str]] = Field(default=None, description="Tags")
    subscription_id: Optional[str] = Field(default=None, description="Subscription ID")


class AzureComputeCreateVmOutput(BaseModel):
    """Output schema for azure_compute_create_vm."""
    success: bool = Field(description="Whether creation succeeded")
    name: str = Field(default="", description="VM name")
    resource_id: str = Field(default="", description="Full resource ID")
    private_ip: str = Field(default="", description="Private IP address")
    public_ip: str = Field(default="", description="Public IP address if assigned")
    provisioning_state: str = Field(default="", description="Provisioning state")
    error: str = Field(default="", description="Error message if failed")


class AzureComputeDeleteVmInput(BaseModel):
    """Input schema for azure_compute_delete_vm."""
    resource_group: str = Field(description="Resource group name")
    name: str = Field(description="VM name")
    force: bool = Field(
        default=False,
        description="Must be True to confirm deletion"
    )
    delete_associated_resources: bool = Field(
        default=False,
        description="Also delete NICs, disks, and public IPs"
    )
    subscription_id: Optional[str] = Field(default=None, description="Subscription ID")


class AzureComputeDeleteVmOutput(BaseModel):
    """Output schema for azure_compute_delete_vm."""
    success: bool = Field(description="Whether deletion was initiated")
    name: str = Field(default="", description="VM name")
    deleted: bool = Field(default=False, description="Whether deletion was initiated")
    message: str = Field(default="", description="Status message")
    error: str = Field(default="", description="Error message if failed")


class AzureComputeListVmsInput(BaseModel):
    """Input schema for azure_compute_list_vms_in_resource_group."""
    resource_group: str = Field(description="Resource group name")
    subscription_id: Optional[str] = Field(default=None, description="Subscription ID")


class VmInfo(BaseModel):
    """Information about a virtual machine."""
    name: str = Field(description="VM name")
    resource_id: str = Field(default="", description="Full resource ID")
    location: str = Field(default="", description="Azure region")
    size: str = Field(default="", description="VM size")
    provisioning_state: str = Field(default="", description="Provisioning state")
    power_state: str = Field(default="", description="Power state (running, stopped, etc.)")
    os_type: str = Field(default="", description="OS type (Linux, Windows)")


class AzureComputeListVmsOutput(BaseModel):
    """Output schema for azure_compute_list_vms_in_resource_group."""
    success: bool = Field(description="Whether the request succeeded")
    vms: List[VmInfo] = Field(default_factory=list, description="List of VMs")
    count: int = Field(default=0, description="Number of VMs")
    resource_group: str = Field(default="", description="Resource group queried")
    error: str = Field(default="", description="Error message if failed")


# =============================================================================
# Stub Tool Implementations
# =============================================================================

async def azure_compute_create_vm(
    params: AzureComputeCreateVmInput
) -> AzureComputeCreateVmOutput:
    """Create an Azure Virtual Machine.
    
    NOTE: This is a stub implementation. Full implementation planned for Phase 2.
    
    Args:
        params: VM configuration
        
    Returns:
        Created VM details
        
    Raises:
        NotImplementedError: This is a stub
    """
    logger.warning("azure_compute_create_vm is a stub - not yet implemented")
    raise NotImplementedError(
        "azure_compute_create_vm is planned for Phase 2. "
        "Use azure_cli_run for VM operations in the meantime."
    )


async def azure_compute_delete_vm(
    params: AzureComputeDeleteVmInput
) -> AzureComputeDeleteVmOutput:
    """Delete an Azure Virtual Machine.
    
    NOTE: This is a stub implementation. Full implementation planned for Phase 2.
    
    Args:
        params: VM deletion parameters
        
    Returns:
        Deletion result
        
    Raises:
        NotImplementedError: This is a stub
    """
    logger.warning("azure_compute_delete_vm is a stub - not yet implemented")
    raise NotImplementedError(
        "azure_compute_delete_vm is planned for Phase 2. "
        "Use azure_cli_run for VM operations in the meantime."
    )


async def azure_compute_list_vms_in_resource_group(
    params: AzureComputeListVmsInput
) -> AzureComputeListVmsOutput:
    """List VMs in a resource group.
    
    NOTE: This is a stub implementation. Full implementation planned for Phase 2.
    
    Args:
        params: Resource group to list VMs in
        
    Returns:
        List of VMs
        
    Raises:
        NotImplementedError: This is a stub
    """
    logger.warning("azure_compute_list_vms_in_resource_group is a stub - not yet implemented")
    raise NotImplementedError(
        "azure_compute_list_vms_in_resource_group is planned for Phase 2. "
        "Use azure_cli_run for VM operations in the meantime."
    )

