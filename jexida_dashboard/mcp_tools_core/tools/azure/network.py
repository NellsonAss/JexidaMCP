"""Azure Network tools (Phase 2 - Stubs).

Provides MCP tools for:
- Creating virtual networks
- Creating subnets
- Attaching NSGs
- Creating public IPs
- Creating load balancers

NOTE: These are stub implementations. Full implementation is planned for Phase 2.
"""

import logging
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# Input/Output Schemas
# =============================================================================

class AzureNetworkCreateVnetInput(BaseModel):
    """Input schema for azure_network_create_vnet."""
    resource_group: str = Field(description="Resource group name")
    name: str = Field(description="Virtual network name")
    location: str = Field(description="Azure region")
    address_prefixes: List[str] = Field(
        default_factory=lambda: ["10.0.0.0/16"],
        description="Address prefixes for the VNet (CIDR notation)"
    )
    dns_servers: Optional[List[str]] = Field(
        default=None,
        description="Custom DNS servers"
    )
    tags: Optional[Dict[str, str]] = Field(default=None, description="Tags")
    subscription_id: Optional[str] = Field(default=None, description="Subscription ID")


class AzureNetworkCreateVnetOutput(BaseModel):
    """Output schema for azure_network_create_vnet."""
    success: bool = Field(description="Whether creation succeeded")
    name: str = Field(default="", description="VNet name")
    resource_id: str = Field(default="", description="Full resource ID")
    address_space: List[str] = Field(default_factory=list, description="Address space")
    error: str = Field(default="", description="Error message if failed")


class AzureNetworkCreateSubnetInput(BaseModel):
    """Input schema for azure_network_create_subnet."""
    resource_group: str = Field(description="Resource group name")
    vnet_name: str = Field(description="Virtual network name")
    name: str = Field(description="Subnet name")
    address_prefix: str = Field(description="Subnet address prefix (CIDR notation)")
    nsg_id: Optional[str] = Field(default=None, description="Network Security Group ID")
    subscription_id: Optional[str] = Field(default=None, description="Subscription ID")


class AzureNetworkCreateSubnetOutput(BaseModel):
    """Output schema for azure_network_create_subnet."""
    success: bool = Field(description="Whether creation succeeded")
    name: str = Field(default="", description="Subnet name")
    resource_id: str = Field(default="", description="Full resource ID")
    address_prefix: str = Field(default="", description="Address prefix")
    error: str = Field(default="", description="Error message if failed")


class AzureNetworkAttachNsgInput(BaseModel):
    """Input schema for azure_network_attach_nsg."""
    resource_group: str = Field(description="Resource group name")
    nsg_name: str = Field(description="Network Security Group name")
    subnet_id: Optional[str] = Field(default=None, description="Subnet ID to attach NSG to")
    nic_id: Optional[str] = Field(default=None, description="NIC ID to attach NSG to")
    subscription_id: Optional[str] = Field(default=None, description="Subscription ID")


class AzureNetworkAttachNsgOutput(BaseModel):
    """Output schema for azure_network_attach_nsg."""
    success: bool = Field(description="Whether attachment succeeded")
    nsg_name: str = Field(default="", description="NSG name")
    attached_to: str = Field(default="", description="Resource NSG was attached to")
    error: str = Field(default="", description="Error message if failed")


class AzureNetworkCreatePublicIpInput(BaseModel):
    """Input schema for azure_network_create_public_ip."""
    resource_group: str = Field(description="Resource group name")
    name: str = Field(description="Public IP name")
    location: str = Field(description="Azure region")
    sku: str = Field(default="Standard", description="SKU: Basic or Standard")
    allocation_method: str = Field(
        default="Static",
        description="Allocation method: Static or Dynamic"
    )
    tags: Optional[Dict[str, str]] = Field(default=None, description="Tags")
    subscription_id: Optional[str] = Field(default=None, description="Subscription ID")


class AzureNetworkCreatePublicIpOutput(BaseModel):
    """Output schema for azure_network_create_public_ip."""
    success: bool = Field(description="Whether creation succeeded")
    name: str = Field(default="", description="Public IP name")
    resource_id: str = Field(default="", description="Full resource ID")
    ip_address: str = Field(default="", description="Allocated IP address")
    error: str = Field(default="", description="Error message if failed")


class AzureNetworkCreateLoadBalancerInput(BaseModel):
    """Input schema for azure_network_create_basic_load_balancer."""
    resource_group: str = Field(description="Resource group name")
    name: str = Field(description="Load balancer name")
    location: str = Field(description="Azure region")
    sku: str = Field(default="Standard", description="SKU: Basic or Standard")
    frontend_ip_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Frontend IP configuration"
    )
    subscription_id: Optional[str] = Field(default=None, description="Subscription ID")


class AzureNetworkCreateLoadBalancerOutput(BaseModel):
    """Output schema for azure_network_create_basic_load_balancer."""
    success: bool = Field(description="Whether creation succeeded")
    name: str = Field(default="", description="Load balancer name")
    resource_id: str = Field(default="", description="Full resource ID")
    error: str = Field(default="", description="Error message if failed")


# =============================================================================
# Stub Tool Implementations
# =============================================================================

async def azure_network_create_vnet(
    params: AzureNetworkCreateVnetInput
) -> AzureNetworkCreateVnetOutput:
    """Create an Azure Virtual Network.
    
    NOTE: This is a stub implementation. Full implementation planned for Phase 2.
    
    Args:
        params: VNet configuration
        
    Returns:
        Created VNet details
        
    Raises:
        NotImplementedError: This is a stub
    """
    logger.warning("azure_network_create_vnet is a stub - not yet implemented")
    raise NotImplementedError(
        "azure_network_create_vnet is planned for Phase 2. "
        "Use azure_cli_run for network operations in the meantime."
    )


async def azure_network_create_subnet(
    params: AzureNetworkCreateSubnetInput
) -> AzureNetworkCreateSubnetOutput:
    """Create a subnet in a Virtual Network.
    
    NOTE: This is a stub implementation. Full implementation planned for Phase 2.
    
    Args:
        params: Subnet configuration
        
    Returns:
        Created subnet details
        
    Raises:
        NotImplementedError: This is a stub
    """
    logger.warning("azure_network_create_subnet is a stub - not yet implemented")
    raise NotImplementedError(
        "azure_network_create_subnet is planned for Phase 2. "
        "Use azure_cli_run for network operations in the meantime."
    )


async def azure_network_attach_nsg(
    params: AzureNetworkAttachNsgInput
) -> AzureNetworkAttachNsgOutput:
    """Attach a Network Security Group to a subnet or NIC.
    
    NOTE: This is a stub implementation. Full implementation planned for Phase 2.
    
    Args:
        params: NSG attachment configuration
        
    Returns:
        Attachment result
        
    Raises:
        NotImplementedError: This is a stub
    """
    logger.warning("azure_network_attach_nsg is a stub - not yet implemented")
    raise NotImplementedError(
        "azure_network_attach_nsg is planned for Phase 2. "
        "Use azure_cli_run for network operations in the meantime."
    )


async def azure_network_create_public_ip(
    params: AzureNetworkCreatePublicIpInput
) -> AzureNetworkCreatePublicIpOutput:
    """Create a public IP address.
    
    NOTE: This is a stub implementation. Full implementation planned for Phase 2.
    
    Args:
        params: Public IP configuration
        
    Returns:
        Created public IP details
        
    Raises:
        NotImplementedError: This is a stub
    """
    logger.warning("azure_network_create_public_ip is a stub - not yet implemented")
    raise NotImplementedError(
        "azure_network_create_public_ip is planned for Phase 2. "
        "Use azure_cli_run for network operations in the meantime."
    )


async def azure_network_create_basic_load_balancer(
    params: AzureNetworkCreateLoadBalancerInput
) -> AzureNetworkCreateLoadBalancerOutput:
    """Create a basic load balancer.
    
    NOTE: This is a stub implementation. Full implementation planned for Phase 2.
    
    Args:
        params: Load balancer configuration
        
    Returns:
        Created load balancer details
        
    Raises:
        NotImplementedError: This is a stub
    """
    logger.warning("azure_network_create_basic_load_balancer is a stub - not yet implemented")
    raise NotImplementedError(
        "azure_network_create_basic_load_balancer is planned for Phase 2. "
        "Use azure_cli_run for network operations in the meantime."
    )

