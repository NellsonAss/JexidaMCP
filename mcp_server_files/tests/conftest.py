"""Pytest fixtures for MCP Server tests."""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def reset_settings():
    """Reset settings before each test."""
    from config import reload_settings
    # Set test environment variables
    os.environ.setdefault("MCP_SERVER_PORT", "8080")
    os.environ.setdefault("MCP_LOG_LEVEL", "DEBUG")
    reload_settings()
    yield


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app."""
    from server import app
    return TestClient(app)


@pytest.fixture
def mock_subprocess():
    """Mock subprocess for Azure CLI tests."""
    with patch("asyncio.create_subprocess_exec") as mock:
        process_mock = AsyncMock()
        process_mock.communicate = AsyncMock(return_value=(b"", b""))
        process_mock.returncode = 0
        mock.return_value = process_mock
        yield mock, process_mock


@pytest.fixture
def mock_httpx():
    """Mock httpx for HTTP health probe tests."""
    with patch("httpx.AsyncClient") as mock:
        yield mock

