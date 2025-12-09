"""Tests for unifi_list_devices tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_tools.unifi.devices import (
    unifi_list_devices,
    UniFiListDevicesInput,
    UniFiListDevicesOutput,
)
from mcp_tools.unifi.client import UniFiDevice, UniFiConnectionError, UniFiAuthError


class TestUniFiListDevices:
    """Tests for unifi_list_devices tool."""
    
    @pytest.mark.asyncio
    async def test_list_devices_success(self):
        """Test successful device listing."""
        mock_devices = [
            UniFiDevice(
                name="UDM Pro",
                model="UDM-Pro",
                device_type="gateway",
                ip="192.168.1.1",
                mac="aa:bb:cc:dd:ee:01",
                firmware="3.2.7",
                adopted=True,
                uptime_seconds=864000,
            ),
            UniFiDevice(
                name="Main Switch",
                model="USW-24",
                device_type="switch",
                ip="192.168.1.2",
                mac="aa:bb:cc:dd:ee:02",
                firmware="6.5.59",
                adopted=True,
                uptime_seconds=432000,
            ),
        ]
        
        with patch("mcp_tools.unifi.devices.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get_devices = AsyncMock(return_value=mock_devices)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client
            
            params = UniFiListDevicesInput()
            result = await unifi_list_devices(params)
            
            assert result.success is True
            assert result.device_count == 2
            assert len(result.devices) == 2
            assert result.devices[0].name == "UDM Pro"
            assert result.devices[0].type == "gateway"
            assert result.devices[1].type == "switch"
    
    @pytest.mark.asyncio
    async def test_list_devices_with_site_id(self):
        """Test device listing with custom site ID."""
        with patch("mcp_tools.unifi.devices.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get_devices = AsyncMock(return_value=[])
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client
            
            params = UniFiListDevicesInput(site_id="custom_site")
            result = await unifi_list_devices(params)
            
            MockClient.assert_called_once_with(site="custom_site")
            assert result.success is True
    
    @pytest.mark.asyncio
    async def test_list_devices_connection_error(self):
        """Test handling of connection errors."""
        with patch("mcp_tools.unifi.devices.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(
                side_effect=UniFiConnectionError("Connection refused")
            )
            MockClient.return_value = mock_client
            
            params = UniFiListDevicesInput()
            result = await unifi_list_devices(params)
            
            assert result.success is False
            assert "Connection error" in result.error
    
    @pytest.mark.asyncio
    async def test_list_devices_auth_error(self):
        """Test handling of authentication errors."""
        with patch("mcp_tools.unifi.devices.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(
                side_effect=UniFiAuthError("Invalid credentials")
            )
            MockClient.return_value = mock_client
            
            params = UniFiListDevicesInput()
            result = await unifi_list_devices(params)
            
            assert result.success is False
            assert "Authentication error" in result.error


class TestUniFiListDevicesInput:
    """Tests for input validation."""
    
    def test_default_site_id(self):
        """Test default site_id is None."""
        params = UniFiListDevicesInput()
        assert params.site_id is None
    
    def test_custom_site_id(self):
        """Test custom site_id."""
        params = UniFiListDevicesInput(site_id="my_site")
        assert params.site_id == "my_site"

