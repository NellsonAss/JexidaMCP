"""UniFi Network Topology Tool.

Provides the unifi_network_topology tool for building a graph representation
of the network including switch-to-AP connections, port usage, VLAN assignments,
and PoE state.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .client import UniFiClient, UniFiConnectionError, UniFiAuthError, UniFiAPIError

import logging
logger = logging.getLogger(__name__)


class PortConnection(BaseModel):
    """Port connection information."""
    port_idx: int = Field(description="Port index")
    port_name: str = Field(default="", description="Port name")
    enabled: bool = Field(description="Port enabled")
    up: bool = Field(description="Port is up/active")
    speed: int = Field(default=0, description="Port speed (Mbps)")
    full_duplex: bool = Field(default=False, description="Full duplex enabled")
    poe_enable: bool = Field(default=False, description="PoE enabled")
    poe_power: float = Field(default=0.0, description="PoE power (W)")
    portconf_id: str = Field(default="", description="Port configuration ID")
    connected_macs: List[str] = Field(default_factory=list, description="Connected device MACs")


class DeviceTopology(BaseModel):
    """Device in topology graph."""
    mac: str = Field(description="Device MAC address")
    name: str = Field(description="Device name")
    model: str = Field(description="Device model")
    device_type: str = Field(description="Device type: gateway, switch, ap, other")
    ip: str = Field(description="Device IP address")
    adopted: bool = Field(description="Device is adopted")
    ports: List[PortConnection] = Field(default_factory=list, description="Port information (switches)")
    radios: List[Dict[str, Any]] = Field(default_factory=list, description="Radio information (APs)")
    uplink: Optional[Dict[str, Any]] = Field(default=None, description="Uplink connection info")
    connected_devices: List[str] = Field(default_factory=list, description="MACs of directly connected devices")


class NetworkTopology(BaseModel):
    """Network topology graph."""
    devices: List[DeviceTopology] = Field(default_factory=list, description="All devices in topology")
    connections: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Device-to-device connections"
    )
    loops_detected: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Detected network loops"
    )


class UniFiNetworkTopologyInput(BaseModel):
    """Input schema for unifi_network_topology tool."""
    
    site_id: Optional[str] = Field(
        default=None,
        description="UniFi site ID (defaults to configured site)"
    )
    include_ports: bool = Field(
        default=True,
        description="Include detailed port information"
    )


class UniFiNetworkTopologyOutput(BaseModel):
    """Output schema for unifi_network_topology tool."""
    
    success: bool = Field(description="Whether the operation succeeded")
    topology: Optional[NetworkTopology] = None
    device_count: int = Field(default=0, description="Number of devices")
    connection_count: int = Field(default=0, description="Number of connections")
    error: str = Field(default="", description="Error message if failed")


async def unifi_network_topology(
    params: UniFiNetworkTopologyInput
) -> UniFiNetworkTopologyOutput:
    """Build a graph representation of the UniFi network.
    
    Returns:
        - Switch → AP connections
        - Port used for each connection
        - VLAN on each port
        - PoE state
        - Loop detection
        
    Args:
        params: Input parameters
        
    Returns:
        Network topology graph
    """
    logger.info("unifi_network_topology called")
    
    try:
        async with UniFiClient(site=params.site_id) as client:
            # Get detailed device information
            devices_data = await client.get_all_device_details()
            
            # Build device topology objects
            devices = []
            device_macs = {}  # MAC -> device index mapping
            
            for idx, dev_data in enumerate(devices_data):
                device_macs[dev_data.get("mac", "")] = idx
                
                ports = []
                if params.include_ports and "ports" in dev_data:
                    for port in dev_data["ports"]:
                        ports.append(PortConnection(
                            port_idx=port.get("port_idx", 0),
                            port_name=port.get("name", ""),
                            enabled=port.get("enable", True),
                            up=port.get("up", False),
                            speed=port.get("speed", 0),
                            full_duplex=port.get("full_duplex", False),
                            poe_enable=port.get("poe_enable", False),
                            poe_power=port.get("poe_power", 0),
                            portconf_id=port.get("portconf_id", ""),
                            connected_macs=[m.get("mac", "") for m in port.get("mac_table", [])],
                        ))
                
                devices.append(DeviceTopology(
                    mac=dev_data.get("mac", ""),
                    name=dev_data.get("name", ""),
                    model=dev_data.get("model", ""),
                    device_type=dev_data.get("type", "other"),
                    ip=dev_data.get("ip", ""),
                    adopted=dev_data.get("adopted", False),
                    ports=ports,
                    radios=dev_data.get("radios", []),
                    uplink=dev_data.get("uplink"),
                ))
            
            # Build connections from uplink and port information
            connections = []
            for device in devices:
                # Uplink connections
                if device.uplink:
                    uplink_mac = device.uplink.get("uplink_mac", "")
                    if uplink_mac in device_macs:
                        connections.append({
                            "from_device": device.mac,
                            "from_name": device.name,
                            "to_device": uplink_mac,
                            "to_name": devices[device_macs[uplink_mac]].name,
                            "type": "uplink",
                            "port": device.uplink.get("uplink_remote_port", 0),
                            "speed": device.uplink.get("speed", 0),
                        })
                
                # Port connections (from mac_table)
                for port in device.ports:
                    for mac in port.connected_macs:
                        if mac in device_macs:
                            connections.append({
                                "from_device": device.mac,
                                "from_name": device.name,
                                "to_device": mac,
                                "to_name": devices[device_macs[mac]].name,
                                "type": "port",
                                "port_idx": port.port_idx,
                                "port_name": port.port_name,
                                "poe_enabled": port.poe_enable,
                                "poe_power": port.poe_power,
                            })
                            # Track connected devices
                            if mac not in device.connected_devices:
                                device.connected_devices.append(mac)
            
            # Simple loop detection: check for cycles in connections
            loops_detected = []
            # This is a simplified check - full loop detection would require graph traversal
            connection_map = {}
            for conn in connections:
                key = tuple(sorted([conn["from_device"], conn["to_device"]]))
                if key in connection_map:
                    loops_detected.append({
                        "devices": [conn["from_device"], conn["to_device"]],
                        "type": "duplicate_connection",
                    })
                connection_map[key] = conn
            
            topology = NetworkTopology(
                devices=devices,
                connections=connections,
                loops_detected=loops_detected,
            )
            
            logger.info(f"Topology built: {len(devices)} devices, {len(connections)} connections")
            
            return UniFiNetworkTopologyOutput(
                success=True,
                topology=topology,
                device_count=len(devices),
                connection_count=len(connections),
            )
            
    except UniFiConnectionError as e:
        logger.error(f"Connection error: {e}")
        return UniFiNetworkTopologyOutput(success=False, error=f"Connection error: {e}")
    except UniFiAuthError as e:
        logger.error(f"Auth error: {e}")
        return UniFiNetworkTopologyOutput(success=False, error=f"Authentication error: {e}")
    except UniFiAPIError as e:
        logger.error(f"API error: {e}")
        return UniFiNetworkTopologyOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return UniFiNetworkTopologyOutput(success=False, error=f"Unexpected error: {e}")

