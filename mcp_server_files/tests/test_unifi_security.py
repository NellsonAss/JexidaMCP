"""Tests for unifi_get_security_settings tool."""

import pytest
from unittest.mock import AsyncMock, patch

from mcp_tools.unifi.security import (
    unifi_get_security_settings,
    UniFiSecuritySettingsInput,
)
from mcp_tools.unifi.client import UniFiConnectionError
from tests.fixtures.unifi_responses import (
    WLANS_RESPONSE,
    NETWORKS_RESPONSE,
    FIREWALL_RULES_RESPONSE,
    FIREWALL_GROUPS_RESPONSE,
)


class TestUniFiGetSecuritySettings:
    """Tests for unifi_get_security_settings tool."""
    
    @pytest.mark.asyncio
    async def test_get_security_settings_success(self):
        """Test successful security settings retrieval."""
        with patch("mcp_tools.unifi.security.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            
            # Setup mock responses
            mock_client.get_wlans = AsyncMock(return_value=WLANS_RESPONSE["data"])
            mock_client.get_networks = AsyncMock(return_value=NETWORKS_RESPONSE["data"])
            mock_client.get_upnp_settings = AsyncMock(return_value={
                "upnp_enabled": True,
                "upnp_nat_pmp_enabled": True,
                "upnp_secure_mode": False,
            })
            mock_client.get_mgmt_settings = AsyncMock(return_value={
                "remote_access_enabled": True,
                "ssh_auth_password_enabled": True,
                "unifi_remote_access_enabled": False,
            })
            mock_client.get_threat_management_settings = AsyncMock(return_value={
                "ips_enabled": False,
                "ips_mode": "disabled",
                "dns_filtering_enabled": False,
                "honeypot_enabled": False,
            })
            mock_client.get_dpi_settings = AsyncMock(return_value={
                "dpi_enabled": False,
                "dpi_restrictions_enabled": False,
            })
            mock_client.get_firewall_rules = AsyncMock(return_value={
                "wan_in": FIREWALL_RULES_RESPONSE["data"][:2],
                "lan_in": FIREWALL_RULES_RESPONSE["data"][2:],
                "wan_out": [],
                "wan_local": [],
                "lan_out": [],
                "lan_local": [],
                "guest_in": [],
                "guest_out": [],
                "guest_local": [],
            })
            mock_client.get_firewall_groups = AsyncMock(
                return_value=FIREWALL_GROUPS_RESPONSE["data"]
            )
            
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client
            
            params = UniFiSecuritySettingsInput()
            result = await unifi_get_security_settings(params)
            
            assert result.success is True
            assert result.wifi is not None
            assert len(result.wifi.networks) == 3
            assert result.vlans is not None
            assert len(result.vlans.networks) == 2
            assert result.remote_access is not None
            assert result.remote_access.upnp_enabled is True
            assert result.threat_management is not None
            assert result.threat_management.ids_ips_enabled is False
    
    @pytest.mark.asyncio
    async def test_get_security_settings_without_firewall(self):
        """Test security settings without firewall rules."""
        with patch("mcp_tools.unifi.security.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            
            mock_client.get_wlans = AsyncMock(return_value=[])
            mock_client.get_networks = AsyncMock(return_value=[])
            mock_client.get_upnp_settings = AsyncMock(return_value={})
            mock_client.get_mgmt_settings = AsyncMock(return_value={})
            mock_client.get_threat_management_settings = AsyncMock(return_value={})
            mock_client.get_dpi_settings = AsyncMock(return_value={})
            mock_client.get_firewall_rules = AsyncMock(return_value={})
            mock_client.get_firewall_groups = AsyncMock(return_value=[])
            
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client
            
            params = UniFiSecuritySettingsInput(include_firewall_rules=False)
            result = await unifi_get_security_settings(params)
            
            assert result.success is True
            # Firewall rules not fetched
            mock_client.get_firewall_rules.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_get_security_settings_connection_error(self):
        """Test handling of connection errors."""
        with patch("mcp_tools.unifi.security.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(
                side_effect=UniFiConnectionError("Connection refused")
            )
            MockClient.return_value = mock_client
            
            params = UniFiSecuritySettingsInput()
            result = await unifi_get_security_settings(params)
            
            assert result.success is False
            assert "Connection error" in result.error


class TestWifiNetworkMapping:
    """Tests for WiFi network data mapping."""
    
    @pytest.mark.asyncio
    async def test_wifi_security_mapping(self):
        """Test that WiFi security settings are correctly mapped."""
        with patch("mcp_tools.unifi.security.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            
            mock_client.get_wlans = AsyncMock(return_value=[
                {
                    "_id": "test1",
                    "name": "SecureNet",
                    "enabled": True,
                    "security": "wpapsk",
                    "wpa_mode": "wpa3",
                    "wpa3_support": True,
                    "wpa3_transition": False,
                    "hide_ssid": True,
                    "is_guest": False,
                    "vlan_enabled": True,
                    "vlan": 100,
                    "l2_isolation": True,
                    "mac_filter_enabled": True,
                    "pmf_mode": "required",
                }
            ])
            mock_client.get_networks = AsyncMock(return_value=[])
            mock_client.get_upnp_settings = AsyncMock(return_value={})
            mock_client.get_mgmt_settings = AsyncMock(return_value={})
            mock_client.get_threat_management_settings = AsyncMock(return_value={})
            mock_client.get_dpi_settings = AsyncMock(return_value={})
            mock_client.get_firewall_rules = AsyncMock(return_value={})
            mock_client.get_firewall_groups = AsyncMock(return_value=[])
            
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client
            
            params = UniFiSecuritySettingsInput()
            result = await unifi_get_security_settings(params)
            
            assert result.success is True
            wifi = result.wifi.networks[0]
            assert wifi.name == "SecureNet"
            assert wifi.security == "wpapsk"
            assert wifi.wpa_mode == "wpa3"
            assert wifi.wpa3_support is True
            assert wifi.hide_ssid is True
            assert wifi.vlan_enabled is True
            assert wifi.vlan == "100"
            assert wifi.client_isolation is True
            assert wifi.pmf_mode == "required"

