"""Tests for Azure SDK MCP tools.

Tests authentication, error handling, and core tool functionality
using mocked Azure SDK clients.
"""

import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

# Add workspace root to path
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "jexida_dashboard"))


class TestAzureAuth(unittest.TestCase):
    """Test Azure authentication module."""
    
    def setUp(self):
        """Clear credential cache before each test."""
        # Import here to avoid import errors if Azure SDK not installed
        try:
            from jexida_dashboard.mcp_tools_core.tools.azure import auth
            auth.clear_credential_cache()
        except ImportError:
            self.skipTest("Azure SDK not installed")
    
    def test_azure_errors_have_correct_types(self):
        """Test that Azure error classes have correct error types."""
        from jexida_dashboard.mcp_tools_core.tools.azure.auth import (
            AzureError,
            AzureAuthError,
            AzureConfigError,
            AzureNotFoundError,
            AzureValidationError,
            AzureAPIError,
            AzureAuthorizationError,
        )
        
        # Test error types
        self.assertEqual(AzureError("test").error_type, "AzureError")
        self.assertEqual(AzureAuthError("test").error_type, "AuthenticationError")
        self.assertEqual(AzureConfigError("test").error_type, "ConfigurationError")
        self.assertEqual(AzureNotFoundError("test").error_type, "NotFoundError")
        self.assertEqual(AzureValidationError("test").error_type, "ValidationError")
        self.assertEqual(AzureAPIError("test").error_type, "AzureAPIError")
        self.assertEqual(AzureAuthorizationError("test").error_type, "AuthorizationError")
    
    def test_error_to_dict(self):
        """Test error serialization to dict."""
        from jexida_dashboard.mcp_tools_core.tools.azure.auth import AzureAuthError
        
        error = AzureAuthError("Failed to authenticate", {"reason": "expired"})
        error_dict = error.to_dict()
        
        self.assertEqual(error_dict["error_type"], "AuthenticationError")
        self.assertEqual(error_dict["message"], "Failed to authenticate")
        self.assertEqual(error_dict["details"]["reason"], "expired")
    
    def test_get_subscription_id_from_param(self):
        """Test that explicit param takes precedence."""
        from jexida_dashboard.mcp_tools_core.tools.azure.auth import get_subscription_id
        
        result = get_subscription_id("explicit-sub-id")
        self.assertEqual(result, "explicit-sub-id")
    
    @patch.dict(os.environ, {"AZURE_SUBSCRIPTION_ID": "env-sub-id"})
    def test_get_subscription_id_from_env(self):
        """Test subscription ID from environment."""
        from jexida_dashboard.mcp_tools_core.tools.azure.auth import get_subscription_id
        
        result = get_subscription_id()
        self.assertEqual(result, "env-sub-id")
    
    @patch.dict(os.environ, {}, clear=True)
    def test_get_subscription_id_raises_when_missing(self):
        """Test that missing subscription ID raises error."""
        from jexida_dashboard.mcp_tools_core.tools.azure.auth import (
            get_subscription_id,
            AzureConfigError,
        )
        
        # Clear any cached env vars
        os.environ.pop("AZURE_SUBSCRIPTION_ID", None)
        
        with self.assertRaises(AzureConfigError):
            get_subscription_id()
    
    @patch.dict(os.environ, {
        "AZURE_TENANT_ID": "tenant",
        "AZURE_CLIENT_ID": "client",
        "AZURE_CLIENT_SECRET": "secret",
    })
    def test_get_azure_config_shows_correct_state(self):
        """Test config returns correct state without exposing secrets."""
        from jexida_dashboard.mcp_tools_core.tools.azure.auth import get_azure_config
        
        config = get_azure_config()
        
        self.assertEqual(config["tenant_id"], "tenant")
        self.assertEqual(config["client_id"], "client")
        self.assertTrue(config["has_client_secret"])
        # Secret should NOT be in config
        self.assertNotIn("client_secret", config)
    
    @patch.dict(os.environ, {
        "AZURE_TENANT_ID": "tenant",
        "AZURE_CLIENT_ID": "client",
        "AZURE_CLIENT_SECRET": "secret",
        "AZURE_SUBSCRIPTION_ID": "sub",
    })
    def test_validate_config_with_full_sp_creds(self):
        """Test config validation with complete service principal."""
        from jexida_dashboard.mcp_tools_core.tools.azure.auth import validate_azure_config
        
        is_valid, message = validate_azure_config()
        
        self.assertTrue(is_valid)
        self.assertIn("Service principal", message)
    
    @patch.dict(os.environ, {"AZURE_TENANT_ID": "tenant"}, clear=True)
    def test_validate_config_with_partial_creds(self):
        """Test config validation with partial credentials."""
        from jexida_dashboard.mcp_tools_core.tools.azure.auth import validate_azure_config
        
        is_valid, message = validate_azure_config()
        
        self.assertFalse(is_valid)
        self.assertIn("Partial", message)
    
    def test_wrap_azure_error_classifies_auth_errors(self):
        """Test error wrapping classifies auth errors correctly."""
        from jexida_dashboard.mcp_tools_core.tools.azure.auth import (
            wrap_azure_error,
            AzureAuthError,
        )
        
        error = Exception("Authentication failed: invalid credentials")
        wrapped = wrap_azure_error(error)
        
        self.assertIsInstance(wrapped, AzureAuthError)
    
    def test_wrap_azure_error_classifies_not_found(self):
        """Test error wrapping classifies not found errors."""
        from jexida_dashboard.mcp_tools_core.tools.azure.auth import (
            wrap_azure_error,
            AzureNotFoundError,
        )
        
        error = Exception("Resource not found")
        wrapped = wrap_azure_error(error)
        
        self.assertIsInstance(wrapped, AzureNotFoundError)


class TestAzureCoreTools(unittest.TestCase):
    """Test Azure Core tools with mocked SDK."""
    
    def test_connection_info_returns_config(self):
        """Test that connection info returns current config."""
        from jexida_dashboard.mcp_tools_core.tools.azure.core import (
            azure_core_get_connection_info,
            AzureCoreGetConnectionInfoInput,
        )
        
        with patch.dict(os.environ, {
            "AZURE_SUBSCRIPTION_ID": "test-sub",
            "AZURE_TENANT_ID": "test-tenant",
        }):
            params = AzureCoreGetConnectionInfoInput()
            result = asyncio.run(azure_core_get_connection_info(params))
            
            self.assertTrue(result.success)
            self.assertEqual(result.subscription_id, "test-sub")
            self.assertEqual(result.tenant_id, "test-tenant")
    
    @patch("jexida_dashboard.mcp_tools_core.tools.azure.core.get_azure_credential")
    @patch("azure.mgmt.resource.SubscriptionClient")
    def test_list_subscriptions_calls_sdk(self, mock_client_class, mock_get_cred):
        """Test that list_subscriptions calls the SDK correctly."""
        from jexida_dashboard.mcp_tools_core.tools.azure.core import (
            azure_core_list_subscriptions,
            AzureCoreListSubscriptionsInput,
        )
        
        # Setup mocks
        mock_cred = MagicMock()
        mock_get_cred.return_value = mock_cred
        
        mock_sub = MagicMock()
        mock_sub.subscription_id = "sub-123"
        mock_sub.display_name = "Test Sub"
        mock_sub.state = MagicMock(value="Enabled")
        mock_sub.tenant_id = "tenant-123"
        
        mock_client = MagicMock()
        mock_client.subscriptions.list.return_value = [mock_sub]
        mock_client_class.return_value = mock_client
        
        params = AzureCoreListSubscriptionsInput()
        result = asyncio.run(azure_core_list_subscriptions(params))
        
        self.assertTrue(result.success)
        self.assertEqual(result.count, 1)
        self.assertEqual(result.subscriptions[0].subscription_id, "sub-123")
        self.assertEqual(result.subscriptions[0].display_name, "Test Sub")


class TestAzureResourcesTools(unittest.TestCase):
    """Test Azure Resources tools with mocked SDK."""
    
    def test_parse_resource_id(self):
        """Test resource ID parsing."""
        from jexida_dashboard.mcp_tools_core.tools.azure.resources import _parse_resource_id
        
        resource_id = "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Web/sites/myapp"
        parsed = _parse_resource_id(resource_id)
        
        self.assertEqual(parsed["subscription_id"], "sub-123")
        self.assertEqual(parsed["resource_group"], "rg-test")
        self.assertEqual(parsed["provider"], "Microsoft.Web")
        self.assertEqual(parsed["type"], "sites")
        self.assertEqual(parsed["name"], "myapp")
    
    def test_delete_resource_requires_force(self):
        """Test that delete requires force=True."""
        from jexida_dashboard.mcp_tools_core.tools.azure.resources import (
            azure_resources_delete_resource,
            AzureResourcesDeleteResourceInput,
        )
        
        params = AzureResourcesDeleteResourceInput(
            resource_id="/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Web/sites/app",
            force=False
        )
        result = asyncio.run(azure_resources_delete_resource(params))
        
        self.assertFalse(result.success)
        self.assertFalse(result.deleted)
        self.assertIn("force", result.error.lower())


class TestAzureDeploymentsTools(unittest.TestCase):
    """Test Azure Deployments tools with mocked SDK."""
    
    def test_format_parameters(self):
        """Test parameter formatting for ARM deployments."""
        from jexida_dashboard.mcp_tools_core.tools.azure.deployments import (
            _format_parameters_for_deployment
        )
        
        # Test raw values
        raw_params = {"appName": "myapp", "sku": "B1"}
        formatted = _format_parameters_for_deployment(raw_params)
        
        self.assertEqual(formatted["appName"]["value"], "myapp")
        self.assertEqual(formatted["sku"]["value"], "B1")
        
        # Test already-formatted values
        arm_params = {"appName": {"value": "myapp"}}
        formatted = _format_parameters_for_deployment(arm_params)
        
        self.assertEqual(formatted["appName"]["value"], "myapp")
    
    def test_get_status_requires_rg_for_rg_scope(self):
        """Test that get_status requires resource_group for RG scope."""
        from jexida_dashboard.mcp_tools_core.tools.azure.deployments import (
            azure_deployments_get_status,
            AzureDeploymentsGetStatusInput,
        )
        
        params = AzureDeploymentsGetStatusInput(
            deployment_name="test-deploy",
            scope="resource_group",
            resource_group=None  # Missing
        )
        result = asyncio.run(azure_deployments_get_status(params))
        
        self.assertFalse(result.success)
        self.assertIn("resource_group", result.error)


class TestAzureDataTools(unittest.TestCase):
    """Test Azure Data tools."""
    
    def test_resolve_secret_from_env(self):
        """Test secret resolution from environment."""
        from jexida_dashboard.mcp_tools_core.tools.azure.data import _resolve_secret
        
        with patch.dict(os.environ, {"MY_SECRET": "secret-value"}):
            value = _resolve_secret("MY_SECRET")
            self.assertEqual(value, "secret-value")
    
    def test_resolve_secret_raises_when_not_found(self):
        """Test that missing secret raises error."""
        from jexida_dashboard.mcp_tools_core.tools.azure.data import _resolve_secret
        
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("NONEXISTENT_SECRET", None)
            with self.assertRaises(ValueError):
                _resolve_secret("NONEXISTENT_SECRET")


class TestAzureCostTools(unittest.TestCase):
    """Test Azure Cost tools."""
    
    def test_get_time_period_dates(self):
        """Test time period to date conversion."""
        from jexida_dashboard.mcp_tools_core.tools.azure.cost import (
            _get_time_period_dates,
            TimePeriod,
        )
        
        from_date, to_date = _get_time_period_dates(TimePeriod.LAST_7_DAYS)
        
        # Should return valid ISO date strings
        self.assertRegex(from_date, r"\d{4}-\d{2}-\d{2}")
        self.assertRegex(to_date, r"\d{4}-\d{2}-\d{2}")
    
    def test_mock_data_fallback(self):
        """Test that cost summary falls back to mock data."""
        from jexida_dashboard.mcp_tools_core.tools.azure.cost import (
            _generate_mock_cost_data,
            TimePeriod,
        )
        
        result = _generate_mock_cost_data(
            "test-sub",
            None,
            TimePeriod.LAST_30_DAYS
        )
        
        self.assertTrue(result.success)
        self.assertTrue(result.is_mock_data)
        self.assertGreater(result.total_cost, 0)
        self.assertEqual(result.currency, "USD")
        self.assertGreater(len(result.breakdown), 0)


class TestAzureStubModules(unittest.TestCase):
    """Test that stub modules raise NotImplementedError."""
    
    def test_network_stubs_raise(self):
        """Test network tools raise NotImplementedError."""
        from jexida_dashboard.mcp_tools_core.tools.azure.network import (
            azure_network_create_vnet,
            AzureNetworkCreateVnetInput,
        )
        
        params = AzureNetworkCreateVnetInput(
            resource_group="rg",
            name="vnet",
            location="eastus"
        )
        
        with self.assertRaises(NotImplementedError):
            asyncio.run(azure_network_create_vnet(params))
    
    def test_security_stubs_raise(self):
        """Test security tools raise NotImplementedError."""
        from jexida_dashboard.mcp_tools_core.tools.azure.security import (
            azure_security_create_key_vault,
            AzureSecurityCreateKeyVaultInput,
        )
        
        params = AzureSecurityCreateKeyVaultInput(
            resource_group="rg",
            name="kv-test",
            location="eastus"
        )
        
        with self.assertRaises(NotImplementedError):
            asyncio.run(azure_security_create_key_vault(params))
    
    def test_compute_stubs_raise(self):
        """Test compute tools raise NotImplementedError."""
        from jexida_dashboard.mcp_tools_core.tools.azure.compute import (
            azure_compute_create_vm,
            AzureComputeCreateVmInput,
        )
        
        params = AzureComputeCreateVmInput(
            resource_group="rg",
            name="vm-test",
            location="eastus",
            admin_username="admin"
        )
        
        with self.assertRaises(NotImplementedError):
            asyncio.run(azure_compute_create_vm(params))
    
    def test_kubernetes_stubs_raise(self):
        """Test kubernetes tools raise NotImplementedError."""
        from jexida_dashboard.mcp_tools_core.tools.azure.kubernetes import (
            azure_kubernetes_create_aks_cluster,
            AzureKubernetesCreateAksClusterInput,
        )
        
        params = AzureKubernetesCreateAksClusterInput(
            resource_group="rg",
            name="aks-test",
            location="eastus"
        )
        
        with self.assertRaises(NotImplementedError):
            asyncio.run(azure_kubernetes_create_aks_cluster(params))


class TestAzureToolsIntegration(unittest.TestCase):
    """Integration tests for Azure tools package."""
    
    def test_all_modules_importable(self):
        """Test that all Azure modules can be imported."""
        from jexida_dashboard.mcp_tools_core.tools import azure
        
        # Check all expected modules exist
        self.assertTrue(hasattr(azure, 'auth'))
        self.assertTrue(hasattr(azure, 'core'))
        self.assertTrue(hasattr(azure, 'resources'))
        self.assertTrue(hasattr(azure, 'deployments'))
        self.assertTrue(hasattr(azure, 'app_platform'))
        self.assertTrue(hasattr(azure, 'data'))
        self.assertTrue(hasattr(azure, 'monitoring'))
        self.assertTrue(hasattr(azure, 'cost'))
        self.assertTrue(hasattr(azure, 'network'))
        self.assertTrue(hasattr(azure, 'security'))
        self.assertTrue(hasattr(azure, 'compute'))
        self.assertTrue(hasattr(azure, 'kubernetes'))
    
    def test_all_tool_functions_exported(self):
        """Test that all tool functions are exported from __init__."""
        from jexida_dashboard.mcp_tools_core.tools import azure
        
        # Core tools
        self.assertTrue(callable(getattr(azure, 'azure_core_get_connection_info', None)))
        self.assertTrue(callable(getattr(azure, 'azure_core_list_subscriptions', None)))
        self.assertTrue(callable(getattr(azure, 'azure_core_list_resource_groups', None)))
        self.assertTrue(callable(getattr(azure, 'azure_core_create_resource_group', None)))
        self.assertTrue(callable(getattr(azure, 'azure_core_delete_resource_group', None)))
        
        # Resources tools
        self.assertTrue(callable(getattr(azure, 'azure_resources_get_resource', None)))
        self.assertTrue(callable(getattr(azure, 'azure_resources_delete_resource', None)))
        self.assertTrue(callable(getattr(azure, 'azure_resources_list_by_type', None)))
        self.assertTrue(callable(getattr(azure, 'azure_resources_search', None)))
        
        # Deployments tools
        self.assertTrue(callable(getattr(azure, 'azure_deployments_deploy_to_resource_group', None)))
        self.assertTrue(callable(getattr(azure, 'azure_deployments_deploy_to_subscription', None)))
        self.assertTrue(callable(getattr(azure, 'azure_deployments_get_status', None)))
        self.assertTrue(callable(getattr(azure, 'azure_deployments_list', None)))
        
        # Cost tools
        self.assertTrue(callable(getattr(azure, 'azure_cost_get_summary', None)))
        self.assertTrue(callable(getattr(azure, 'azure_cost_get_top_cost_drivers', None)))
    
    def test_error_classes_exported(self):
        """Test that error classes are exported."""
        from jexida_dashboard.mcp_tools_core.tools import azure
        
        self.assertTrue(hasattr(azure, 'AzureError'))
        self.assertTrue(hasattr(azure, 'AzureAuthError'))
        self.assertTrue(hasattr(azure, 'AzureConfigError'))
        self.assertTrue(hasattr(azure, 'AzureNotFoundError'))
        self.assertTrue(hasattr(azure, 'AzureValidationError'))
        self.assertTrue(hasattr(azure, 'AzureAPIError'))
        self.assertTrue(hasattr(azure, 'AzureAuthorizationError'))


if __name__ == "__main__":
    unittest.main()

