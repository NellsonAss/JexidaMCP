"""Tests for network_scan_local tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_tools.unifi.network_scan import (
    network_scan_local,
    NetworkScanInput,
    parse_nmap_xml,
    validate_subnet,
    validate_ports,
)
from tests.fixtures.unifi_responses import NMAP_XML_OUTPUT, NMAP_XML_EMPTY


class TestValidateSubnet:
    """Tests for subnet validation."""
    
    def test_valid_subnets(self):
        """Test valid subnet formats."""
        assert validate_subnet("192.168.1.0/24") is True
        assert validate_subnet("10.0.0.0/8") is True
        assert validate_subnet("172.16.0.0/12") is True
        assert validate_subnet("192.168.1.1") is True
    
    def test_invalid_subnets(self):
        """Test invalid subnet formats."""
        assert validate_subnet("") is False
        assert validate_subnet("192.168.1.0/33") is False  # Invalid prefix
        assert validate_subnet("256.0.0.0/24") is False  # Invalid octet
        assert validate_subnet("192.168.1.0/24; rm -rf /") is False  # Injection
        assert validate_subnet("192.168.1.0/24 && echo pwned") is False
        assert validate_subnet("192.168.1.0/24`whoami`") is False


class TestValidatePorts:
    """Tests for port validation."""
    
    def test_valid_port_specs(self):
        """Test valid port specifications."""
        assert validate_ports("top-100") is True
        assert validate_ports("top-1000") is True
        assert validate_ports("common") is True
        assert validate_ports("22,80,443") is True
        assert validate_ports("1-1024") is True
        assert validate_ports("80") is True
        assert validate_ports("") is True  # Empty is OK
        assert validate_ports(None) is True
    
    def test_invalid_port_specs(self):
        """Test invalid port specifications."""
        assert validate_ports("22; rm -rf /") is False
        assert validate_ports("22 && echo pwned") is False
        assert validate_ports("22|cat /etc/passwd") is False
        assert validate_ports("22`whoami`") is False


class TestParseNmapXml:
    """Tests for nmap XML parsing."""
    
    def test_parse_hosts_found(self):
        """Test parsing XML with hosts found."""
        result = parse_nmap_xml(NMAP_XML_OUTPUT)
        
        assert result.success is True
        assert result.hosts_up == 2
        assert result.hosts_total == 255
        assert len(result.hosts) == 2
        
        # Check first host
        host1 = result.hosts[0]
        assert host1.ip == "192.168.1.1"
        assert host1.mac == "AA:BB:CC:DD:EE:01"
        assert host1.vendor == "Ubiquiti"
        assert host1.hostname == "udm-pro"
        assert len(host1.ports) == 2
        
        # Check ports
        port_nums = [p.port for p in host1.ports]
        assert 22 in port_nums
        assert 443 in port_nums
    
    def test_parse_no_hosts_found(self):
        """Test parsing XML with no hosts found."""
        result = parse_nmap_xml(NMAP_XML_EMPTY)
        
        assert result.success is True
        assert result.hosts_up == 0
        assert len(result.hosts) == 0
    
    def test_parse_invalid_xml(self):
        """Test parsing invalid XML."""
        from mcp_tools.unifi.network_scan import NmapError
        
        with pytest.raises(NmapError):
            parse_nmap_xml("not valid xml")


class TestNetworkScanInput:
    """Tests for NetworkScanInput validation."""
    
    def test_valid_input(self):
        """Test valid input."""
        params = NetworkScanInput(
            subnets=["192.168.1.0/24"],
            ports="top-100",
        )
        assert params.subnets == ["192.168.1.0/24"]
        assert params.ports == "top-100"
    
    def test_invalid_subnet_rejected(self):
        """Test invalid subnet is rejected."""
        with pytest.raises(ValueError, match="Invalid"):
            NetworkScanInput(
                subnets=["192.168.1.0/24; rm -rf /"],
                ports="top-100",
            )
    
    def test_empty_subnets_rejected(self):
        """Test empty subnets list is rejected."""
        with pytest.raises(ValueError, match="At least one subnet"):
            NetworkScanInput(subnets=[])
    
    def test_too_many_subnets_rejected(self):
        """Test too many subnets is rejected."""
        with pytest.raises(ValueError, match="Maximum 10"):
            NetworkScanInput(
                subnets=[f"192.168.{i}.0/24" for i in range(15)]
            )
    
    def test_invalid_ports_rejected(self):
        """Test invalid port specification is rejected."""
        with pytest.raises(ValueError, match="Invalid"):
            NetworkScanInput(
                subnets=["192.168.1.0/24"],
                ports="22; rm -rf /",
            )


class TestNetworkScanLocal:
    """Tests for network_scan_local tool."""
    
    @pytest.mark.asyncio
    async def test_scan_success(self):
        """Test successful network scan."""
        with patch("mcp_tools.unifi.network_scan.asyncio.create_subprocess_exec") as mock_exec:
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(
                return_value=(NMAP_XML_OUTPUT.encode(), b"")
            )
            mock_exec.return_value = mock_process
            
            with patch("mcp_tools.unifi.network_scan.asyncio.wait_for") as mock_wait:
                mock_wait.return_value = (NMAP_XML_OUTPUT.encode(), b"")
                
                params = NetworkScanInput(
                    subnets=["192.168.1.0/24"],
                    ports="top-100",
                )
                result = await network_scan_local(params)
                
                assert result.success is True
                assert result.hosts_up == 2
                assert len(result.hosts) == 2
    
    @pytest.mark.asyncio
    async def test_scan_nmap_not_found(self):
        """Test handling when nmap is not installed."""
        with patch("mcp_tools.unifi.network_scan.asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.side_effect = FileNotFoundError("nmap not found")
            
            params = NetworkScanInput(
                subnets=["192.168.1.0/24"],
            )
            result = await network_scan_local(params)
            
            assert result.success is False
            assert "not found" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_scan_timeout(self):
        """Test handling scan timeout."""
        import asyncio
        
        with patch("mcp_tools.unifi.network_scan.asyncio.create_subprocess_exec") as mock_exec:
            mock_process = MagicMock()
            mock_process.kill = MagicMock()
            mock_process.communicate = AsyncMock(return_value=(b"", b""))
            mock_exec.return_value = mock_process
            
            with patch("mcp_tools.unifi.network_scan.asyncio.wait_for") as mock_wait:
                mock_wait.side_effect = asyncio.TimeoutError()
                
                params = NetworkScanInput(
                    subnets=["192.168.1.0/24"],
                )
                result = await network_scan_local(params)
                
                assert result.success is False
                assert "timed out" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_scan_with_preset_ports(self):
        """Test scan with port presets."""
        with patch("mcp_tools.unifi.network_scan.asyncio.create_subprocess_exec") as mock_exec:
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(
                return_value=(NMAP_XML_EMPTY.encode(), b"")
            )
            mock_exec.return_value = mock_process
            
            with patch("mcp_tools.unifi.network_scan.asyncio.wait_for") as mock_wait:
                mock_wait.return_value = (NMAP_XML_EMPTY.encode(), b"")
                
                # Test different presets
                for preset in ["top-100", "top-1000", "common"]:
                    params = NetworkScanInput(
                        subnets=["10.0.0.0/24"],
                        ports=preset,
                    )
                    result = await network_scan_local(params)
                    assert result.success is True

