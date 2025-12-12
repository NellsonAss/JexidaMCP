"""UniFi Controller API client.

Handles authentication and API interactions with UniFi Dream Machine (UDM)
and other UniFi controllers. Uses session-based authentication.
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from config import get_settings
from logging_config import get_logger

logger = get_logger(__name__)


class UniFiAuthError(Exception):
    """Authentication failed with the UniFi controller."""
    pass


class UniFiConnectionError(Exception):
    """Failed to connect to the UniFi controller."""
    pass


class UniFiAPIError(Exception):
    """API request to UniFi controller failed."""
    
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class UniFiDevice:
    """Normalized UniFi device representation."""
    name: str
    model: str
    device_type: str  # gateway, switch, ap, other
    ip: str
    mac: str
    firmware: str
    adopted: bool
    uptime_seconds: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "model": self.model,
            "type": self.device_type,
            "ip": self.ip,
            "mac": self.mac,
            "firmware": self.firmware,
            "adopted": self.adopted,
            "uptime_seconds": self.uptime_seconds,
        }


class UniFiClient:
    """Async client for UniFi Controller API.
    
    Supports UniFi Dream Machine (UDM/UDM Pro/UDM SE) API patterns.
    Uses session-based cookie authentication.
    
    Usage:
        async with UniFiClient() as client:
            devices = await client.get_devices()
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        site: Optional[str] = None,
        verify_ssl: Optional[bool] = None,
        timeout: Optional[int] = None,
    ):
        """Initialize UniFi client.
        
        Args:
            base_url: Controller URL (defaults to config)
            username: Admin username (defaults to config)
            password: Admin password (defaults to config)
            site: Site ID (defaults to config)
            verify_ssl: Verify SSL certs (defaults to config)
            timeout: Request timeout in seconds (defaults to config)
        """
        settings = get_settings()
        
        self.base_url = (base_url or settings.unifi_controller_url or "").rstrip("/")
        self.username = username or settings.unifi_username
        self.password = password or settings.unifi_password
        self.site = site or settings.unifi_site
        self.verify_ssl = verify_ssl if verify_ssl is not None else settings.unifi_verify_ssl
        self.timeout = timeout or settings.unifi_timeout
        
        self._client: Optional[httpx.AsyncClient] = None
        self._authenticated = False
    
    async def __aenter__(self) -> "UniFiClient":
        """Async context manager entry - creates client and authenticates."""
        await self._ensure_client()
        await self._login()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - logout and close client."""
        await self._logout()
        await self._close()
    
    async def _ensure_client(self) -> None:
        """Create HTTP client if not exists."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                verify=self.verify_ssl,
                timeout=self.timeout,
                follow_redirects=True,
            )
    
    async def _close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            self._authenticated = False
    
    async def _login(self) -> None:
        """Authenticate with the UniFi controller.
        
        Uses the UDM auth endpoint: POST /api/auth/login
        
        Raises:
            UniFiAuthError: If authentication fails
            UniFiConnectionError: If connection fails
        """
        if not self.base_url:
            raise UniFiConnectionError("UniFi controller URL not configured")
        if not self.username or not self.password:
            raise UniFiAuthError("UniFi credentials not configured")
        
        await self._ensure_client()
        
        try:
            response = await self._client.post(
                "/api/auth/login",
                json={
                    "username": self.username,
                    "password": self.password,
                },
            )
            
            if response.status_code == 200:
                self._authenticated = True
                logger.info("Successfully authenticated with UniFi controller")
            elif response.status_code == 401:
                raise UniFiAuthError("Invalid UniFi credentials")
            else:
                raise UniFiAuthError(
                    f"UniFi authentication failed with status {response.status_code}"
                )
                
        except httpx.ConnectError as e:
            raise UniFiConnectionError(f"Failed to connect to UniFi controller: {e}")
        except httpx.TimeoutException as e:
            raise UniFiConnectionError(f"Connection to UniFi controller timed out: {e}")
    
    async def _logout(self) -> None:
        """Logout from the UniFi controller."""
        if self._client and self._authenticated:
            try:
                await self._client.post("/api/auth/logout")
            except Exception:
                pass  # Best effort logout
            self._authenticated = False
    
    async def _api_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an authenticated API request.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (relative to site path)
            json_data: Optional JSON body
            
        Returns:
            Response data
            
        Raises:
            UniFiAPIError: If request fails
        """
        if not self._authenticated:
            raise UniFiAPIError("Not authenticated with UniFi controller")
        
        # UDM uses /proxy/network prefix
        url = f"/proxy/network/api/s/{self.site}/{endpoint}"
        
        try:
            response = await self._client.request(
                method=method,
                url=url,
                json=json_data,
            )
            
            if response.status_code == 401:
                self._authenticated = False
                raise UniFiAuthError("Session expired")
            
            if response.status_code >= 400:
                raise UniFiAPIError(
                    f"API request failed: {response.text}",
                    status_code=response.status_code,
                )
            
            data = response.json()
            
            # UniFi API wraps responses in {"meta": {...}, "data": [...]}
            if isinstance(data, dict) and "data" in data:
                return data
            
            return {"data": data}
            
        except httpx.TimeoutException as e:
            raise UniFiAPIError(f"Request timed out: {e}")
        except httpx.RequestError as e:
            raise UniFiAPIError(f"Request failed: {e}")
    
    async def _get(self, endpoint: str) -> List[Dict[str, Any]]:
        """GET request, returns data array."""
        result = await self._api_request("GET", endpoint)
        return result.get("data", [])
    
    async def _post(
        self,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """POST request."""
        return await self._api_request("POST", endpoint, json_data)
    
    async def _put(
        self,
        endpoint: str,
        json_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """PUT request."""
        return await self._api_request("PUT", endpoint, json_data)
    
    # -------------------------------------------------------------------------
    # Device Methods
    # -------------------------------------------------------------------------
    
    async def get_devices(self) -> List[UniFiDevice]:
        """Get all adopted UniFi devices.
        
        Returns:
            List of normalized device objects
        """
        raw_devices = await self._get("stat/device")
        devices = []
        
        for dev in raw_devices:
            device_type = self._classify_device_type(dev.get("type", ""))
            
            devices.append(UniFiDevice(
                name=dev.get("name", dev.get("mac", "Unknown")),
                model=dev.get("model", "Unknown"),
                device_type=device_type,
                ip=dev.get("ip", ""),
                mac=dev.get("mac", ""),
                firmware=dev.get("version", ""),
                adopted=dev.get("adopted", False),
                uptime_seconds=dev.get("uptime", 0),
            ))
        
        return devices
    
    async def get_clients(self) -> List[Dict[str, Any]]:
        """Get all connected client devices (WiFi and wired).
        
        Returns:
            List of client devices with connection details
        """
        raw_clients = await self._get("stat/sta")
        clients = []
        
        for client in raw_clients:
            clients.append({
                "name": client.get("name") or client.get("hostname") or client.get("mac", "Unknown"),
                "hostname": client.get("hostname", ""),
                "mac": client.get("mac", ""),
                "ip": client.get("ip", ""),
                "is_wired": client.get("is_wired", False),
                "network": client.get("essid") or client.get("network", ""),
                "signal": client.get("signal", 0),
                "rssi": client.get("rssi", 0),
                "tx_bytes": client.get("tx_bytes", 0),
                "rx_bytes": client.get("rx_bytes", 0),
                "uptime_seconds": client.get("uptime", 0),
                "last_seen": client.get("last_seen", 0),
                "ap_mac": client.get("ap_mac", ""),
            })
        
        return clients
    
    @staticmethod
    def _classify_device_type(unifi_type: str) -> str:
        """Map UniFi device type to normalized type."""
        type_map = {
            "ugw": "gateway",
            "udm": "gateway",
            "usw": "switch",
            "uap": "ap",
        }
        # Check prefix matches
        for prefix, device_type in type_map.items():
            if unifi_type.lower().startswith(prefix):
                return device_type
        return "other"
    
    # -------------------------------------------------------------------------
    # WiFi / WLAN Methods
    # -------------------------------------------------------------------------
    
    async def get_wlans(self) -> List[Dict[str, Any]]:
        """Get all wireless networks (WLANs).
        
        Returns:
            List of WLAN configurations with security details
        """
        raw_wlans = await self._get("rest/wlanconf")
        wlans = []
        
        for wlan in raw_wlans:
            wlans.append({
                "_id": wlan.get("_id"),
                "name": wlan.get("name", ""),
                "ssid": wlan.get("name", ""),  # SSID is same as name in UniFi
                "enabled": wlan.get("enabled", False),
                "security": wlan.get("security", "open"),
                "wpa_mode": wlan.get("wpa_mode", ""),
                "wpa3_support": wlan.get("wpa3_support", False),
                "wpa3_transition": wlan.get("wpa3_transition", False),
                "hide_ssid": wlan.get("hide_ssid", False),
                "is_guest": wlan.get("is_guest", False),
                "vlan_enabled": wlan.get("vlan_enabled", False),
                "vlan": wlan.get("vlan", ""),
                "ap_group_ids": wlan.get("ap_group_ids", []),
                "usergroup_id": wlan.get("usergroup_id", ""),
                "l2_isolation": wlan.get("l2_isolation", False),
                "mac_filter_enabled": wlan.get("mac_filter_enabled", False),
                "mac_filter_policy": wlan.get("mac_filter_policy", "allow"),
                "pmf_mode": wlan.get("pmf_mode", "disabled"),
            })
        
        return wlans
    
    async def update_wlan(self, wlan_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update a WLAN configuration.
        
        Args:
            wlan_id: The _id of the WLAN to update
            updates: Dictionary of fields to update
            
        Returns:
            Updated WLAN data
        """
        return await self._put(f"rest/wlanconf/{wlan_id}", updates)
    
    # -------------------------------------------------------------------------
    # Network / VLAN Methods
    # -------------------------------------------------------------------------
    
    async def get_networks(self) -> List[Dict[str, Any]]:
        """Get all networks and VLANs.
        
        Returns:
            List of network configurations
        """
        raw_networks = await self._get("rest/networkconf")
        networks = []
        
        for net in raw_networks:
            networks.append({
                "_id": net.get("_id"),
                "name": net.get("name", ""),
                "purpose": net.get("purpose", ""),  # corporate, guest, wan, etc.
                "vlan_enabled": net.get("vlan_enabled", False),
                "vlan": net.get("vlan", None),
                "subnet": net.get("ip_subnet", ""),
                "dhcp_enabled": net.get("dhcpd_enabled", False),
                "dhcp_start": net.get("dhcpd_start", ""),
                "dhcp_stop": net.get("dhcpd_stop", ""),
                "dhcp_lease_time": net.get("dhcpd_leasetime", 86400),
                "domain_name": net.get("domain_name", ""),
                "igmp_snooping": net.get("igmp_snooping", False),
                "networkgroup": net.get("networkgroup", ""),
            })
        
        return networks
    
    async def update_network(self, network_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update a network configuration.
        
        Args:
            network_id: The _id of the network to update
            updates: Dictionary of fields to update
            
        Returns:
            Updated network data
        """
        return await self._put(f"rest/networkconf/{network_id}", updates)
    
    # -------------------------------------------------------------------------
    # Firewall Methods
    # -------------------------------------------------------------------------
    
    async def get_firewall_rules(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all firewall rules organized by ruleset.
        
        Returns:
            Dictionary with keys: wan_in, wan_out, wan_local, lan_in, lan_out, lan_local, guest_in, guest_out, guest_local
        """
        raw_rules = await self._get("rest/firewallrule")
        
        # Organize rules by ruleset
        rulesets: Dict[str, List[Dict[str, Any]]] = {
            "wan_in": [],
            "wan_out": [],
            "wan_local": [],
            "lan_in": [],
            "lan_out": [],
            "lan_local": [],
            "guest_in": [],
            "guest_out": [],
            "guest_local": [],
        }
        
        for rule in raw_rules:
            ruleset = rule.get("ruleset", "").lower().replace("-", "_")
            
            normalized_rule = {
                "_id": rule.get("_id"),
                "name": rule.get("name", ""),
                "enabled": rule.get("enabled", True),
                "action": rule.get("action", ""),  # accept, drop, reject
                "protocol": rule.get("protocol", "all"),
                "protocol_match_excepted": rule.get("protocol_match_excepted", False),
                "src_firewallgroup_ids": rule.get("src_firewallgroup_ids", []),
                "src_address": rule.get("src_address", ""),
                "src_mac_address": rule.get("src_mac_address", ""),
                "src_networkconf_id": rule.get("src_networkconf_id", ""),
                "src_networkconf_type": rule.get("src_networkconf_type", ""),
                "dst_firewallgroup_ids": rule.get("dst_firewallgroup_ids", []),
                "dst_address": rule.get("dst_address", ""),
                "dst_networkconf_id": rule.get("dst_networkconf_id", ""),
                "dst_networkconf_type": rule.get("dst_networkconf_type", ""),
                "dst_port": rule.get("dst_port", ""),
                "icmp_typename": rule.get("icmp_typename", ""),
                "state_established": rule.get("state_established", False),
                "state_invalid": rule.get("state_invalid", False),
                "state_new": rule.get("state_new", False),
                "state_related": rule.get("state_related", False),
                "rule_index": rule.get("rule_index", 0),
            }
            
            if ruleset in rulesets:
                rulesets[ruleset].append(normalized_rule)
            else:
                # Unknown ruleset, add to a generic bucket
                if "other" not in rulesets:
                    rulesets["other"] = []
                rulesets["other"].append(normalized_rule)
        
        # Sort rules by index within each ruleset
        for ruleset in rulesets.values():
            ruleset.sort(key=lambda r: r.get("rule_index", 0))
        
        return rulesets
    
    async def get_firewall_groups(self) -> List[Dict[str, Any]]:
        """Get all firewall groups (port groups, address groups).
        
        Returns:
            List of firewall group configurations
        """
        raw_groups = await self._get("rest/firewallgroup")
        groups = []
        
        for group in raw_groups:
            groups.append({
                "_id": group.get("_id"),
                "name": group.get("name", ""),
                "group_type": group.get("group_type", ""),  # address-group, port-group, ipv6-address-group
                "group_members": group.get("group_members", []),
            })
        
        return groups
    
    async def create_firewall_rule(self, rule_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new firewall rule.
        
        Args:
            rule_data: Firewall rule configuration
            
        Returns:
            Created rule data
        """
        return await self._post("rest/firewallrule", rule_data)
    
    async def update_firewall_rule(self, rule_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing firewall rule.
        
        Args:
            rule_id: The _id of the rule to update
            updates: Dictionary of fields to update
            
        Returns:
            Updated rule data
        """
        return await self._put(f"rest/firewallrule/{rule_id}", updates)
    
    # -------------------------------------------------------------------------
    # Settings Methods
    # -------------------------------------------------------------------------
    
    async def get_settings(self) -> Dict[str, Any]:
        """Get all controller settings.
        
        Returns:
            Dictionary of settings categories
        """
        raw_settings = await self._get("rest/setting")
        
        # Organize settings by key
        settings_dict = {}
        for setting in raw_settings:
            key = setting.get("key", "unknown")
            settings_dict[key] = setting
        
        return settings_dict
    
    async def get_mgmt_settings(self) -> Dict[str, Any]:
        """Get management/remote access settings.
        
        Returns:
            Remote access and management configuration
        """
        settings = await self.get_settings()
        mgmt = settings.get("mgmt", {})
        
        return {
            "remote_access_enabled": mgmt.get("x_ssh_enabled", False),
            "ssh_auth_password_enabled": mgmt.get("x_ssh_auth_password_enabled", False),
            "led_enabled": mgmt.get("led_enabled", True),
            "alert_enabled": mgmt.get("alert_enabled", True),
            "unifi_remote_access_enabled": mgmt.get("unifi_idp_enabled", False),
        }
    
    async def get_upnp_settings(self) -> Dict[str, Any]:
        """Get UPnP settings.
        
        Returns:
            UPnP configuration
        """
        settings = await self.get_settings()
        upnp = settings.get("usg", {})
        
        return {
            "upnp_enabled": upnp.get("upnp_enabled", False),
            "upnp_nat_pmp_enabled": upnp.get("upnp_nat_pmp_enabled", False),
            "upnp_secure_mode": upnp.get("upnp_secure_mode", False),
        }
    
    async def update_upnp_settings(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update UPnP settings.
        
        Args:
            updates: Dictionary with upnp_enabled, upnp_nat_pmp_enabled, etc.
            
        Returns:
            Updated settings
        """
        settings = await self.get_settings()
        usg = settings.get("usg", {})
        usg_id = usg.get("_id")
        
        if not usg_id:
            raise UniFiAPIError("Could not find USG settings ID")
        
        return await self._put(f"rest/setting/usg/{usg_id}", updates)
    
    async def get_threat_management_settings(self) -> Dict[str, Any]:
        """Get IDS/IPS threat management settings.
        
        Returns:
            Threat management configuration
        """
        settings = await self.get_settings()
        ips = settings.get("ips", {})
        
        return {
            "ips_enabled": ips.get("ips_enabled", False),
            "ips_mode": ips.get("ips_mode", "disabled"),  # disabled, ids, ips
            "dns_filtering_enabled": ips.get("dns_filtering", False),
            "honeypot_enabled": ips.get("honeypot_enabled", False),
            "suppression": ips.get("suppression", {}),
        }
    
    async def get_dpi_settings(self) -> Dict[str, Any]:
        """Get Deep Packet Inspection settings.
        
        Returns:
            DPI configuration
        """
        settings = await self.get_settings()
        dpi = settings.get("dpi", {})
        
        return {
            "dpi_enabled": dpi.get("enabled", False),
            "dpi_restrictions_enabled": dpi.get("restrictions_enabled", False),
        }
    
    # -------------------------------------------------------------------------
    # Backup / Restore Methods
    # -------------------------------------------------------------------------
    
    async def create_backup(self, label: str = "") -> Dict[str, Any]:
        """Create a controller backup.
        
        Args:
            label: Optional label for the backup
            
        Returns:
            Backup metadata including ID and timestamp
        """
        # UDM uses a different endpoint for backups
        # POST /api/s/{site}/cmd/backup
        result = await self._post("cmd/backup", {"cmd": "backup"})
        
        return {
            "success": True,
            "backup_id": result.get("data", [{}])[0].get("_id", ""),
            "label": label,
            "created_at": result.get("data", [{}])[0].get("time", ""),
        }
    
    async def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups.
        
        Returns:
            List of backup metadata
        """
        raw_backups = await self._get("cmd/backup")
        backups = []
        
        for backup in raw_backups:
            backups.append({
                "_id": backup.get("_id", ""),
                "name": backup.get("name", ""),
                "datetime": backup.get("datetime", ""),
                "size": backup.get("size", 0),
                "version": backup.get("version", ""),
                "format": backup.get("format", ""),
            })
        
        return backups
    
    async def restore_backup(self, backup_id: str) -> Dict[str, Any]:
        """Restore a backup.
        
        Args:
            backup_id: ID of the backup to restore
            
        Returns:
            Restoration result
        """
        result = await self._post("cmd/backup", {
            "cmd": "restore",
            "_id": backup_id,
        })
        
        return {
            "success": True,
            "message": "Backup restoration initiated",
            "backup_id": backup_id,
        }
    
    async def download_backup(self, backup_id: str) -> bytes:
        """Download a backup file.
        
        Args:
            backup_id: ID of the backup to download
            
        Returns:
            Backup file contents as bytes
        """
        url = f"/proxy/network/api/s/{self.site}/cmd/backup/{backup_id}"
        response = await self._client.get(url)
        return response.content
    
    # -------------------------------------------------------------------------
    # Topology / Port Methods
    # -------------------------------------------------------------------------
    
    async def get_port_configs(self) -> List[Dict[str, Any]]:
        """Get port configurations from all switches.
        
        Returns:
            List of port configurations including VLAN assignments
        """
        raw_ports = await self._get("rest/portconf")
        ports = []
        
        for port in raw_ports:
            ports.append({
                "_id": port.get("_id"),
                "name": port.get("name", ""),
                "poe_mode": port.get("poe_mode", ""),
                "native_networkconf_id": port.get("native_networkconf_id", ""),
                "voice_networkconf_id": port.get("voice_networkconf_id", ""),
                "port_isolation": port.get("port_isolation", False),
                "forward": port.get("forward", "all"),
                "stormctrl_enabled": port.get("stormctrl_enabled", False),
            })
        
        return ports
    
    async def get_port_forwards(self) -> List[Dict[str, Any]]:
        """Get port forward rules.
        
        Returns:
            List of port forwarding rules
        """
        raw_forwards = await self._get("rest/portforward")
        forwards = []
        
        for fwd in raw_forwards:
            forwards.append({
                "_id": fwd.get("_id"),
                "name": fwd.get("name", ""),
                "enabled": fwd.get("enabled", False),
                "src": fwd.get("src", "any"),
                "dst_port": fwd.get("dst_port", ""),
                "fwd": fwd.get("fwd", ""),
                "fwd_port": fwd.get("fwd_port", ""),
                "proto": fwd.get("proto", "tcp_udp"),
                "log": fwd.get("log", False),
            })
        
        return forwards
    
    async def get_device_details(self, mac: str) -> Dict[str, Any]:
        """Get detailed device information including port states.
        
        Args:
            mac: MAC address of the device
            
        Returns:
            Detailed device information with port states
        """
        devices = await self._get(f"stat/device/{mac}")
        if devices:
            return devices[0]
        return {}
    
    async def get_all_device_details(self) -> List[Dict[str, Any]]:
        """Get detailed information for all devices including port states.
        
        Returns:
            List of detailed device information
        """
        raw_devices = await self._get("stat/device")
        detailed_devices = []
        
        for dev in raw_devices:
            device_info = {
                "mac": dev.get("mac", ""),
                "name": dev.get("name", dev.get("mac", "Unknown")),
                "model": dev.get("model", ""),
                "type": self._classify_device_type(dev.get("type", "")),
                "ip": dev.get("ip", ""),
                "adopted": dev.get("adopted", False),
                "state": dev.get("state", 0),
                "uptime": dev.get("uptime", 0),
                "version": dev.get("version", ""),
                "upgradable": dev.get("upgradable", False),
            }
            
            # Add port information for switches
            if dev.get("type", "").startswith("usw"):
                port_table = dev.get("port_table", [])
                ports = []
                for port in port_table:
                    ports.append({
                        "port_idx": port.get("port_idx", 0),
                        "name": port.get("name", ""),
                        "enable": port.get("enable", True),
                        "up": port.get("up", False),
                        "speed": port.get("speed", 0),
                        "full_duplex": port.get("full_duplex", False),
                        "poe_enable": port.get("poe_enable", False),
                        "poe_power": port.get("poe_power", 0),
                        "portconf_id": port.get("portconf_id", ""),
                        "mac_table": port.get("mac_table", []),
                    })
                device_info["ports"] = ports
                device_info["port_count"] = len(ports)
            
            # Add radio information for APs
            if dev.get("type", "").startswith("uap"):
                radio_table = dev.get("radio_table", [])
                radios = []
                for radio in radio_table:
                    radios.append({
                        "name": radio.get("name", ""),
                        "radio": radio.get("radio", ""),
                        "channel": radio.get("channel", 0),
                        "ht": radio.get("ht", ""),
                        "tx_power_mode": radio.get("tx_power_mode", ""),
                        "tx_power": radio.get("tx_power", 0),
                        "num_sta": radio.get("num_sta", 0),
                    })
                device_info["radios"] = radios
                device_info["num_clients"] = dev.get("num_sta", 0)
            
            # Add uplink information
            uplink = dev.get("uplink", {})
            if uplink:
                device_info["uplink"] = {
                    "type": uplink.get("type", ""),
                    "uplink_mac": uplink.get("uplink_mac", ""),
                    "uplink_device_name": uplink.get("uplink_device_name", ""),
                    "uplink_remote_port": uplink.get("uplink_remote_port", 0),
                    "speed": uplink.get("speed", 0),
                    "full_duplex": uplink.get("full_duplex", False),
                }
            
            detailed_devices.append(device_info)
        
        return detailed_devices
    
    async def get_lldp_table(self) -> List[Dict[str, Any]]:
        """Get LLDP neighbor information.
        
        Returns:
            List of LLDP neighbor entries
        """
        # LLDP info is embedded in device details
        devices = await self.get_all_device_details()
        lldp_entries = []
        
        for device in devices:
            for port in device.get("ports", []):
                # Some ports have LLDP info in mac_table
                for entry in port.get("mac_table", []):
                    if entry.get("via", "") == "lldp":
                        lldp_entries.append({
                            "local_device": device.get("name", device.get("mac")),
                            "local_port": port.get("port_idx"),
                            "remote_mac": entry.get("mac", ""),
                            "remote_name": entry.get("name", ""),
                        })
        
        return lldp_entries
    
    # -------------------------------------------------------------------------
    # Monitoring / Alerts Methods
    # -------------------------------------------------------------------------
    
    async def get_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent alerts from the controller.
        
        Args:
            limit: Maximum number of alerts to return
            
        Returns:
            List of recent alerts
        """
        raw_alerts = await self._get(f"stat/alarm?limit={limit}")
        alerts = []
        
        for alert in raw_alerts:
            alerts.append({
                "_id": alert.get("_id", ""),
                "key": alert.get("key", ""),
                "msg": alert.get("msg", ""),
                "time": alert.get("time", 0),
                "datetime": alert.get("datetime", ""),
                "archived": alert.get("archived", False),
                "device_mac": alert.get("mac", ""),
                "device_name": alert.get("device_name", ""),
                "subsystem": alert.get("subsystem", ""),
            })
        
        return alerts
    
    async def get_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent events from the controller.
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            List of recent events
        """
        raw_events = await self._get(f"stat/event?_limit={limit}")
        events = []
        
        for event in raw_events:
            events.append({
                "_id": event.get("_id", ""),
                "key": event.get("key", ""),
                "msg": event.get("msg", ""),
                "time": event.get("time", 0),
                "datetime": event.get("datetime", ""),
                "subsystem": event.get("subsystem", ""),
                "site_id": event.get("site_id", ""),
                "user": event.get("user", ""),
                "ap": event.get("ap", ""),
                "guest": event.get("guest", ""),
                "network": event.get("network", ""),
            })
        
        return events
    
    async def get_ips_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get IPS/IDS threat alerts.
        
        Args:
            limit: Maximum number of alerts to return
            
        Returns:
            List of IPS threat alerts
        """
        # IPS alerts use a different stat endpoint
        raw_alerts = await self._get(f"stat/ips/event?_limit={limit}")
        alerts = []
        
        for alert in raw_alerts:
            alerts.append({
                "_id": alert.get("_id", ""),
                "timestamp": alert.get("timestamp", 0),
                "signature": alert.get("signature", ""),
                "category": alert.get("catname", alert.get("category", "")),
                "severity": alert.get("severity", ""),
                "src_ip": alert.get("src_ip", ""),
                "src_port": alert.get("src_port", 0),
                "dst_ip": alert.get("dst_ip", ""),
                "dst_port": alert.get("dst_port", 0),
                "protocol": alert.get("proto", ""),
                "app": alert.get("app", ""),
                "action": alert.get("action", ""),
                "msg": alert.get("msg", ""),
            })
        
        return alerts
    
    async def get_rogueaps(self) -> List[Dict[str, Any]]:
        """Get detected rogue APs.
        
        Returns:
            List of rogue/neighboring APs
        """
        raw_rogues = await self._get("stat/rogueap")
        rogues = []
        
        for rogue in raw_rogues:
            rogues.append({
                "_id": rogue.get("_id", ""),
                "mac": rogue.get("bssid", rogue.get("mac", "")),
                "essid": rogue.get("essid", ""),
                "channel": rogue.get("channel", 0),
                "rssi": rogue.get("rssi", 0),
                "security": rogue.get("security", ""),
                "is_rogue": rogue.get("is_rogue", False),
                "is_adhoc": rogue.get("is_adhoc", False),
                "last_seen": rogue.get("last_seen", 0),
                "report_time": rogue.get("report_time", 0),
                "oui": rogue.get("oui", ""),
                "ap_mac": rogue.get("ap_mac", ""),
                "radio": rogue.get("radio", ""),
            })
        
        return rogues
    
    async def get_known_clients(self) -> List[Dict[str, Any]]:
        """Get all known clients (including offline).
        
        Returns:
            List of all known client devices
        """
        raw_clients = await self._get("rest/user")
        clients = []
        
        for client in raw_clients:
            clients.append({
                "_id": client.get("_id", ""),
                "mac": client.get("mac", ""),
                "name": client.get("name", ""),
                "hostname": client.get("hostname", ""),
                "oui": client.get("oui", ""),
                "first_seen": client.get("first_seen", 0),
                "last_seen": client.get("last_seen", 0),
                "is_guest": client.get("is_guest", False),
                "is_wired": client.get("is_wired", False),
                "blocked": client.get("blocked", False),
                "noted": client.get("noted", False),
                "note": client.get("note", ""),
                "use_fixedip": client.get("use_fixedip", False),
                "fixed_ip": client.get("fixed_ip", ""),
            })
        
        return clients
    
    # -------------------------------------------------------------------------
    # WLAN Create/Delete Methods
    # -------------------------------------------------------------------------
    
    async def create_wlan(self, wlan_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new wireless network.
        
        Args:
            wlan_config: WLAN configuration with:
                - name: SSID name (required)
                - security: Security mode (wpapsk, wpaeap, open)
                - wpa_mode: WPA mode (wpa2, wpa3, wpa2-wpa3)
                - x_passphrase: WiFi password (if wpapsk)
                - vlan_enabled: Enable VLAN tagging
                - vlan: VLAN ID
                - is_guest: Is guest network
                - l2_isolation: Client isolation
                
        Returns:
            Created WLAN data
        """
        # Set defaults
        config = {
            "enabled": True,
            "hide_ssid": False,
            "is_guest": False,
            "security": "wpapsk",
            "wpa_mode": "wpa2",
            "wpa_enc": "ccmp",
            "l2_isolation": False,
            **wlan_config,
        }
        
        return await self._post("rest/wlanconf", config)
    
    async def delete_wlan(self, wlan_id: str) -> Dict[str, Any]:
        """Delete a wireless network.
        
        Args:
            wlan_id: ID of the WLAN to delete
            
        Returns:
            Deletion result
        """
        return await self._api_request("DELETE", f"rest/wlanconf/{wlan_id}")
    
    # -------------------------------------------------------------------------
    # Network/VLAN Create/Delete Methods
    # -------------------------------------------------------------------------
    
    async def create_network(self, network_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new network/VLAN.
        
        Args:
            network_config: Network configuration with:
                - name: Network name (required)
                - purpose: Purpose (corporate, guest, vlan-only, wan)
                - vlan_enabled: Enable VLAN
                - vlan: VLAN ID
                - ip_subnet: IP subnet (e.g., 192.168.10.0/24)
                - dhcpd_enabled: Enable DHCP
                - dhcpd_start: DHCP start IP
                - dhcpd_stop: DHCP stop IP
                
        Returns:
            Created network data
        """
        return await self._post("rest/networkconf", network_config)
    
    async def delete_network(self, network_id: str) -> Dict[str, Any]:
        """Delete a network/VLAN.
        
        Args:
            network_id: ID of the network to delete
            
        Returns:
            Deletion result
        """
        return await self._api_request("DELETE", f"rest/networkconf/{network_id}")
    
    # -------------------------------------------------------------------------
    # Firewall Methods (Extended)
    # -------------------------------------------------------------------------
    
    async def delete_firewall_rule(self, rule_id: str) -> Dict[str, Any]:
        """Delete a firewall rule.
        
        Args:
            rule_id: ID of the rule to delete
            
        Returns:
            Deletion result
        """
        return await self._api_request("DELETE", f"rest/firewallrule/{rule_id}")
    
    async def get_traffic_rules(self) -> List[Dict[str, Any]]:
        """Get traffic rules (new UniFi traffic management).
        
        Returns:
            List of traffic rules
        """
        raw_rules = await self._get("rest/trafficrule")
        rules = []
        
        for rule in raw_rules:
            rules.append({
                "_id": rule.get("_id"),
                "name": rule.get("name", ""),
                "enabled": rule.get("enabled", True),
                "action": rule.get("action", ""),
                "matching_target": rule.get("matching_target", ""),
                "target_devices": rule.get("target_devices", []),
                "schedule": rule.get("schedule", {}),
            })
        
        return rules
    
    # -------------------------------------------------------------------------
    # Full Config Export
    # -------------------------------------------------------------------------
    
    async def export_full_config(self) -> Dict[str, Any]:
        """Export the complete controller configuration.
        
        Returns:
            Complete configuration including all networks, WLANs, rules, etc.
        """
        config = {
            "exported_at": None,  # Will be set by caller
            "site": self.site,
            "networks": await self.get_networks(),
            "wlans": await self.get_wlans(),
            "firewall_rules": await self.get_firewall_rules(),
            "firewall_groups": await self.get_firewall_groups(),
            "port_configs": await self.get_port_configs(),
            "port_forwards": await self.get_port_forwards(),
            "traffic_rules": await self.get_traffic_rules(),
            "settings": await self.get_settings(),
            "devices": [d.to_dict() for d in await self.get_devices()],
        }
        
        return config


# Convenience function to create a client
async def get_unifi_client() -> UniFiClient:
    """Create and return an authenticated UniFi client.
    
    Remember to use as context manager or call close when done.
    
    Returns:
        Authenticated UniFiClient instance
    """
    client = UniFiClient()
    await client._ensure_client()
    await client._login()
    return client

