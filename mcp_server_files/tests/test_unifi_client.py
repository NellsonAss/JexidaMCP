"""Tests for UniFi API client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_tools.unifi.client import (
    UniFiClient,
    UniFiAuthError,
    UniFiConnectionError,
    UniFiAPIError,
    UniFiDevice,
)
from tests.fixtures.unifi_responses import (
    LOGIN_SUCCESS,
    DEVICES_RESPONSE,
    WLANS_RESPONSE,
    NETWORKS_RESPONSE,
    SETTINGS_RESPONSE,
)


class TestUniFiClientInit:
    """Tests for UniFi client initialization."""
    
    def test_default_initialization(self):
        """Test client initializes with defaults from config."""
        with patch("mcp_tools.unifi.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                unifi_controller_url="https://192.168.1.1",
                unifi_username="admin",
                unifi_password="password",
                unifi_site="default",
                unifi_verify_ssl=False,
                unifi_timeout=30,
            )
            
            client = UniFiClient()
            
            assert client.base_url == "https://192.168.1.1"
            assert client.username == "admin"
            assert client.site == "default"
            assert client.verify_ssl is False
    
    def test_custom_initialization(self):
        """Test client accepts custom parameters."""
        with patch("mcp_tools.unifi.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                unifi_controller_url="https://default.url",
                unifi_username="default_user",
                unifi_password="default_pass",
                unifi_site="default",
                unifi_verify_ssl=False,
                unifi_timeout=30,
            )
            
            client = UniFiClient(
                base_url="https://custom.url",
                username="custom_user",
                password="custom_pass",
                site="custom_site",
            )
            
            assert client.base_url == "https://custom.url"
            assert client.username == "custom_user"
            assert client.site == "custom_site"


class TestUniFiClientAuth:
    """Tests for UniFi client authentication."""
    
    @pytest.mark.asyncio
    async def test_login_success(self):
        """Test successful login."""
        with patch("mcp_tools.unifi.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                unifi_controller_url="https://192.168.1.1",
                unifi_username="admin",
                unifi_password="password",
                unifi_site="default",
                unifi_verify_ssl=False,
                unifi_timeout=30,
            )
            
            client = UniFiClient()
            
            with patch.object(client, "_client") as mock_http:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_http.post = AsyncMock(return_value=mock_response)
                
                client._client = mock_http
                await client._login()
                
                assert client._authenticated is True
    
    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self):
        """Test login with invalid credentials."""
        with patch("mcp_tools.unifi.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                unifi_controller_url="https://192.168.1.1",
                unifi_username="admin",
                unifi_password="wrong",
                unifi_site="default",
                unifi_verify_ssl=False,
                unifi_timeout=30,
            )
            
            client = UniFiClient()
            
            with patch.object(client, "_client") as mock_http:
                mock_response = MagicMock()
                mock_response.status_code = 401
                mock_http.post = AsyncMock(return_value=mock_response)
                
                client._client = mock_http
                
                with pytest.raises(UniFiAuthError, match="Invalid"):
                    await client._login()
    
    @pytest.mark.asyncio
    async def test_login_no_url(self):
        """Test login without URL configured."""
        with patch("mcp_tools.unifi.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                unifi_controller_url=None,
                unifi_username="admin",
                unifi_password="password",
                unifi_site="default",
                unifi_verify_ssl=False,
                unifi_timeout=30,
            )
            
            client = UniFiClient()
            
            with pytest.raises(UniFiConnectionError, match="not configured"):
                await client._login()


class TestUniFiClientDevices:
    """Tests for device retrieval."""
    
    @pytest.mark.asyncio
    async def test_get_devices(self):
        """Test getting device list."""
        with patch("mcp_tools.unifi.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                unifi_controller_url="https://192.168.1.1",
                unifi_username="admin",
                unifi_password="password",
                unifi_site="default",
                unifi_verify_ssl=False,
                unifi_timeout=30,
            )
            
            client = UniFiClient()
            client._authenticated = True
            
            with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = DEVICES_RESPONSE["data"]
                
                devices = await client.get_devices()
                
                assert len(devices) == 3
                assert devices[0].name == "UDM Pro"
                assert devices[0].device_type == "gateway"
                assert devices[1].device_type == "switch"
                assert devices[2].device_type == "ap"
    
    def test_classify_device_type(self):
        """Test device type classification."""
        assert UniFiClient._classify_device_type("udm") == "gateway"
        assert UniFiClient._classify_device_type("ugw") == "gateway"
        assert UniFiClient._classify_device_type("usw") == "switch"
        assert UniFiClient._classify_device_type("uap") == "ap"
        assert UniFiClient._classify_device_type("unknown") == "other"


class TestUniFiClientWLANs:
    """Tests for WLAN retrieval."""
    
    @pytest.mark.asyncio
    async def test_get_wlans(self):
        """Test getting WLAN list."""
        with patch("mcp_tools.unifi.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                unifi_controller_url="https://192.168.1.1",
                unifi_username="admin",
                unifi_password="password",
                unifi_site="default",
                unifi_verify_ssl=False,
                unifi_timeout=30,
            )
            
            client = UniFiClient()
            client._authenticated = True
            
            with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = WLANS_RESPONSE["data"]
                
                wlans = await client.get_wlans()
                
                assert len(wlans) == 3
                assert wlans[0]["name"] == "HomeNetwork"
                assert wlans[0]["security"] == "wpapsk"
                assert wlans[1]["is_guest"] is True
                assert wlans[2]["security"] == "open"


class TestUniFiClientNetworks:
    """Tests for network retrieval."""
    
    @pytest.mark.asyncio
    async def test_get_networks(self):
        """Test getting network list."""
        with patch("mcp_tools.unifi.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                unifi_controller_url="https://192.168.1.1",
                unifi_username="admin",
                unifi_password="password",
                unifi_site="default",
                unifi_verify_ssl=False,
                unifi_timeout=30,
            )
            
            client = UniFiClient()
            client._authenticated = True
            
            with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = NETWORKS_RESPONSE["data"]
                
                networks = await client.get_networks()
                
                assert len(networks) == 2
                assert networks[0]["name"] == "Default"
                assert networks[0]["purpose"] == "corporate"
                assert networks[1]["purpose"] == "wan"


class TestUniFiClientSettings:
    """Tests for settings retrieval."""
    
    @pytest.mark.asyncio
    async def test_get_upnp_settings(self):
        """Test getting UPnP settings."""
        with patch("mcp_tools.unifi.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                unifi_controller_url="https://192.168.1.1",
                unifi_username="admin",
                unifi_password="password",
                unifi_site="default",
                unifi_verify_ssl=False,
                unifi_timeout=30,
            )
            
            client = UniFiClient()
            client._authenticated = True
            
            # Build settings dict from response
            settings_dict = {}
            for setting in SETTINGS_RESPONSE["data"]:
                settings_dict[setting["key"]] = setting
            
            with patch.object(client, "get_settings", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = settings_dict
                
                upnp = await client.get_upnp_settings()
                
                assert upnp["upnp_enabled"] is True
                assert upnp["upnp_nat_pmp_enabled"] is True


class TestUniFiDevice:
    """Tests for UniFiDevice dataclass."""
    
    def test_to_dict(self):
        """Test device to_dict conversion."""
        device = UniFiDevice(
            name="Test Device",
            model="USW-24",
            device_type="switch",
            ip="192.168.1.2",
            mac="aa:bb:cc:dd:ee:ff",
            firmware="6.5.59",
            adopted=True,
            uptime_seconds=86400,
        )
        
        result = device.to_dict()
        
        assert result["name"] == "Test Device"
        assert result["type"] == "switch"
        assert result["uptime_seconds"] == 86400

