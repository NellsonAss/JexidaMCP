"""Tests for monitor.http_health_probe tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from mcp_tools.azure.monitor import (
    HttpHealthProbeInput,
    HttpHealthProbeOutput,
    http_health_probe,
)


class TestHttpHealthProbeInput:
    """Tests for HttpHealthProbeInput schema validation."""
    
    def test_valid_input_minimal(self):
        """Test valid minimal input."""
        input_data = HttpHealthProbeInput(url="https://example.com")
        assert input_data.url == "https://example.com"
        assert input_data.method == "GET"
        assert input_data.expected_status == 200
        assert input_data.timeout_seconds is None
    
    def test_valid_input_full(self):
        """Test valid full input."""
        input_data = HttpHealthProbeInput(
            url="https://api.example.com/health",
            method="POST",
            expected_status=201,
            timeout_seconds=10
        )
        assert input_data.method == "POST"
        assert input_data.expected_status == 201
        assert input_data.timeout_seconds == 10
    
    def test_invalid_url_scheme(self):
        """Test that non-http/https schemes are rejected."""
        with pytest.raises(ValueError, match="http or https"):
            HttpHealthProbeInput(url="ftp://example.com")
        with pytest.raises(ValueError, match="http or https"):
            HttpHealthProbeInput(url="file:///etc/passwd")
    
    def test_invalid_url_no_host(self):
        """Test that URLs without host are rejected."""
        with pytest.raises(ValueError, match="valid host"):
            HttpHealthProbeInput(url="http://")
    
    def test_method_case_insensitive(self):
        """Test that method is converted to uppercase."""
        input_data = HttpHealthProbeInput(url="https://example.com", method="get")
        assert input_data.method == "GET"
    
    def test_invalid_method(self):
        """Test that invalid methods are rejected."""
        with pytest.raises(ValueError, match="Method must be"):
            HttpHealthProbeInput(url="https://example.com", method="INVALID")
    
    def test_invalid_status_code(self):
        """Test that invalid status codes are rejected."""
        with pytest.raises(ValueError, match="between 100 and 599"):
            HttpHealthProbeInput(url="https://example.com", expected_status=99)
        with pytest.raises(ValueError, match="between 100 and 599"):
            HttpHealthProbeInput(url="https://example.com", expected_status=600)


class TestHttpHealthProbeExecution:
    """Tests for http_health_probe execution."""
    
    @pytest.mark.asyncio
    async def test_healthy_response(self):
        """Test healthy response when status matches expected."""
        params = HttpHealthProbeInput(
            url="https://example.com/health",
            expected_status=200
        )
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            result = await http_health_probe(params)
        
        assert result.status == "healthy"
        assert result.http_status == 200
        assert result.response_time_ms >= 0
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_unhealthy_wrong_status(self):
        """Test unhealthy response when status doesn't match."""
        params = HttpHealthProbeInput(
            url="https://example.com/health",
            expected_status=200
        )
        
        mock_response = MagicMock()
        mock_response.status_code = 503
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            result = await http_health_probe(params)
        
        assert result.status == "unhealthy"
        assert result.http_status == 503
        assert result.error is not None
        assert "Expected status 200" in result.error
    
    @pytest.mark.asyncio
    async def test_timeout_error(self):
        """Test handling of timeout errors."""
        params = HttpHealthProbeInput(
            url="https://example.com/slow",
            timeout_seconds=1
        )
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            result = await http_health_probe(params)
        
        assert result.status == "unhealthy"
        assert result.http_status is None
        assert result.error is not None
        assert "timed out" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_connection_error(self):
        """Test handling of connection errors."""
        params = HttpHealthProbeInput(url="https://nonexistent.invalid")
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            result = await http_health_probe(params)
        
        assert result.status == "unhealthy"
        assert result.http_status is None
        assert result.error is not None
        assert "connection" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_custom_method(self):
        """Test using custom HTTP method."""
        params = HttpHealthProbeInput(
            url="https://example.com/health",
            method="HEAD",
            expected_status=200
        )
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            result = await http_health_probe(params)
            
            # Verify the correct method was used
            mock_client.request.assert_called_once()
            call_kwargs = mock_client.request.call_args
            assert call_kwargs.kwargs.get("method") == "HEAD" or call_kwargs.args[0] == "HEAD"
        
        assert result.status == "healthy"
    
    @pytest.mark.asyncio
    async def test_response_time_measured(self):
        """Test that response time is measured."""
        params = HttpHealthProbeInput(url="https://example.com")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            result = await http_health_probe(params)
        
        # Response time should be a non-negative integer
        assert isinstance(result.response_time_ms, int)
        assert result.response_time_ms >= 0

