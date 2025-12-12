"""Tests for Azure orchestration flows and CLI commands.

Tests the flows.py module and CLI handlers with mocked Azure SDK calls.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import json


class TestBuildResourceNames(unittest.TestCase):
    """Test the build_resource_names helper function."""

    def test_basic_naming(self):
        """Test basic resource naming convention."""
        from jexida_dashboard.mcp_tools_core.tools.azure.flows import build_resource_names
        
        names = build_resource_names("myapp", "dev")
        
        self.assertEqual(names["resource_group"], "rg-myapp-dev")
        self.assertEqual(names["app_service_plan"], "plan-myapp-dev")
        self.assertEqual(names["web_app"], "myapp-dev")
        self.assertEqual(names["sql_server"], "sql-myapp-dev")
        self.assertEqual(names["sql_database"], "db-myapp-dev")

    def test_storage_account_sanitization(self):
        """Test storage account name is properly sanitized."""
        from jexida_dashboard.mcp_tools_core.tools.azure.flows import build_resource_names
        
        # With hyphens (should be removed)
        names = build_resource_names("my-app", "staging")
        self.assertNotIn("-", names["storage_account"])
        self.assertTrue(names["storage_account"].startswith("st"))
        self.assertTrue(len(names["storage_account"]) <= 24)

    def test_long_name_truncation(self):
        """Test that very long names are properly truncated."""
        from jexida_dashboard.mcp_tools_core.tools.azure.flows import build_resource_names
        
        names = build_resource_names("this-is-a-very-long-application-name", "production")
        
        # Storage account must be <= 24 chars
        self.assertTrue(len(names["storage_account"]) <= 24)


class TestBuildDefaultTags(unittest.TestCase):
    """Test the build_default_tags helper function."""

    def test_basic_tags(self):
        """Test basic tag generation."""
        from jexida_dashboard.mcp_tools_core.tools.azure.flows import build_default_tags
        
        tags = build_default_tags("staging")
        
        self.assertEqual(tags["system"], "jexida-mcp")
        self.assertEqual(tags["environment"], "staging")
        self.assertEqual(tags["managed-by"], "jexida-flows")

    def test_with_owner(self):
        """Test tags with owner."""
        from jexida_dashboard.mcp_tools_core.tools.azure.flows import build_default_tags
        
        tags = build_default_tags("prod", owner="admin@example.com")
        
        self.assertEqual(tags["owner"], "admin@example.com")

    def test_with_extra_tags(self):
        """Test merging extra tags."""
        from jexida_dashboard.mcp_tools_core.tools.azure.flows import build_default_tags
        
        tags = build_default_tags("dev", extra_tags={"team": "platform", "cost-center": "123"})
        
        self.assertEqual(tags["team"], "platform")
        self.assertEqual(tags["cost-center"], "123")
        self.assertEqual(tags["environment"], "dev")  # Original still there


class TestAzureFlowCreateAppEnvironment(unittest.IsolatedAsyncioTestCase):
    """Test azure_flow_create_app_environment flow."""

    async def test_successful_environment_creation(self):
        """Test successful creation of app environment."""
        from jexida_dashboard.mcp_tools_core.tools.azure.flows import (
            azure_flow_create_app_environment,
            AzureFlowCreateAppEnvironmentInput,
        )
        
        # Mock the low-level tools
        with patch("jexida_dashboard.mcp_tools_core.tools.azure.flows.azure_core_create_resource_group") as mock_rg, \
             patch("jexida_dashboard.mcp_tools_core.tools.azure.flows.azure_app_platform_create_app_service_plan") as mock_plan, \
             patch("jexida_dashboard.mcp_tools_core.tools.azure.flows.azure_app_platform_create_web_app") as mock_app:
            
            # Configure mocks
            mock_rg_result = MagicMock()
            mock_rg_result.success = True
            mock_rg_result.created = True
            mock_rg.return_value = mock_rg_result
            
            mock_plan_result = MagicMock()
            mock_plan_result.success = True
            mock_plan_result.resource_id = "/subscriptions/.../resourceGroups/rg-myapp-dev/providers/Microsoft.Web/serverfarms/plan-myapp-dev"
            mock_plan_result.sku_name = "B1"
            mock_plan_result.sku_tier = "Basic"
            mock_plan.return_value = mock_plan_result
            
            mock_app_result = MagicMock()
            mock_app_result.success = True
            mock_app_result.resource_id = "/subscriptions/.../resourceGroups/rg-myapp-dev/providers/Microsoft.Web/sites/myapp-dev"
            mock_app_result.default_hostname = "myapp-dev.azurewebsites.net"
            mock_app_result.state = "Running"
            mock_app.return_value = mock_app_result
            
            # Run the flow
            result = await azure_flow_create_app_environment(
                AzureFlowCreateAppEnvironmentInput(
                    base_name="myapp",
                    location="eastus",
                    environment="dev",
                )
            )
            
            # Verify result
            self.assertTrue(result.ok)
            self.assertEqual(result.resource_group, "rg-myapp-dev")
            self.assertEqual(result.app_service_plan, "plan-myapp-dev")
            self.assertEqual(result.web_app, "myapp-dev")
            self.assertEqual(result.web_app_url, "https://myapp-dev.azurewebsites.net")
            self.assertEqual(len(result.resources), 3)
            
            # Verify calls were made
            mock_rg.assert_called_once()
            mock_plan.assert_called_once()
            mock_app.assert_called_once()

    async def test_resource_group_failure(self):
        """Test handling of resource group creation failure."""
        from jexida_dashboard.mcp_tools_core.tools.azure.flows import (
            azure_flow_create_app_environment,
            AzureFlowCreateAppEnvironmentInput,
        )
        
        with patch("jexida_dashboard.mcp_tools_core.tools.azure.flows.azure_core_create_resource_group") as mock_rg:
            # Configure mock to fail
            mock_rg_result = MagicMock()
            mock_rg_result.success = False
            mock_rg_result.error = "Subscription not found"
            mock_rg.return_value = mock_rg_result
            
            result = await azure_flow_create_app_environment(
                AzureFlowCreateAppEnvironmentInput(
                    base_name="myapp",
                    location="eastus",
                )
            )
            
            # Should fail gracefully
            self.assertFalse(result.ok)
            self.assertIn("Subscription not found", result.error)
            self.assertEqual(len(result.resources), 0)


class TestAzureFlowAddDataServices(unittest.IsolatedAsyncioTestCase):
    """Test azure_flow_add_data_services flow."""

    async def test_successful_data_services_addition(self):
        """Test successful addition of data services."""
        from jexida_dashboard.mcp_tools_core.tools.azure.flows import (
            azure_flow_add_data_services,
            AzureFlowAddDataServicesInput,
        )
        
        with patch("jexida_dashboard.mcp_tools_core.tools.azure.flows.azure_data_create_storage_account") as mock_storage, \
             patch("jexida_dashboard.mcp_tools_core.tools.azure.flows.azure_data_create_blob_container") as mock_container, \
             patch("jexida_dashboard.mcp_tools_core.tools.azure.flows.azure_data_create_sql_server") as mock_sql, \
             patch("jexida_dashboard.mcp_tools_core.tools.azure.flows.azure_data_create_sql_database") as mock_db, \
             patch("jexida_dashboard.mcp_tools_core.tools.azure.flows.azure_data_set_sql_firewall_rule_allow_azure_services") as mock_fw:
            
            # Configure mocks
            mock_storage_result = MagicMock()
            mock_storage_result.success = True
            mock_storage_result.primary_endpoint = "https://stmyappdev.blob.core.windows.net/"
            mock_storage_result.resource_id = "/subscriptions/.../storageAccounts/stmyappdev"
            mock_storage.return_value = mock_storage_result
            
            mock_container_result = MagicMock()
            mock_container_result.success = True
            mock_container_result.resource_id = "/subscriptions/.../containers/assets"
            mock_container.return_value = mock_container_result
            
            mock_sql_result = MagicMock()
            mock_sql_result.success = True
            mock_sql_result.fqdn = "sql-myapp-dev.database.windows.net"
            mock_sql_result.resource_id = "/subscriptions/.../servers/sql-myapp-dev"
            mock_sql.return_value = mock_sql_result
            
            mock_db_result = MagicMock()
            mock_db_result.success = True
            mock_db_result.resource_id = "/subscriptions/.../databases/db-myapp-dev"
            mock_db.return_value = mock_db_result
            
            mock_fw_result = MagicMock()
            mock_fw_result.success = True
            mock_fw_result.rule_name = "AllowAzureServices"
            mock_fw.return_value = mock_fw_result
            
            result = await azure_flow_add_data_services(
                AzureFlowAddDataServicesInput(
                    resource_group="rg-myapp-dev",
                    base_name="myapp",
                    location="eastus",
                )
            )
            
            self.assertTrue(result.ok)
            self.assertIn("stmyapp", result.storage_account)
            self.assertEqual(result.blob_container, "assets")
            self.assertEqual(result.sql_server, "sql-myapp-dev")
            self.assertEqual(result.sql_database, "db-myapp-dev")

    async def test_storage_only(self):
        """Test adding only storage (no SQL)."""
        from jexida_dashboard.mcp_tools_core.tools.azure.flows import (
            azure_flow_add_data_services,
            AzureFlowAddDataServicesInput,
        )
        
        with patch("jexida_dashboard.mcp_tools_core.tools.azure.flows.azure_data_create_storage_account") as mock_storage, \
             patch("jexida_dashboard.mcp_tools_core.tools.azure.flows.azure_data_create_blob_container") as mock_container:
            
            mock_storage_result = MagicMock()
            mock_storage_result.success = True
            mock_storage_result.primary_endpoint = "https://stmyappdev.blob.core.windows.net/"
            mock_storage_result.resource_id = "/subscriptions/.../storageAccounts/stmyappdev"
            mock_storage.return_value = mock_storage_result
            
            mock_container_result = MagicMock()
            mock_container_result.success = True
            mock_container_result.resource_id = "/subscriptions/.../containers/assets"
            mock_container.return_value = mock_container_result
            
            result = await azure_flow_add_data_services(
                AzureFlowAddDataServicesInput(
                    resource_group="rg-myapp-dev",
                    base_name="myapp",
                    location="eastus",
                    include_sql=False,
                )
            )
            
            self.assertTrue(result.ok)
            self.assertIn("stmyapp", result.storage_account)
            self.assertEqual(result.sql_server, "")  # Not created
            self.assertEqual(result.sql_database, "")


class TestAzureFlowDeployStandardTemplate(unittest.IsolatedAsyncioTestCase):
    """Test azure_flow_deploy_standard_template flow."""

    async def test_successful_deployment_from_json(self):
        """Test successful deployment with JSON string template."""
        from jexida_dashboard.mcp_tools_core.tools.azure.flows import (
            azure_flow_deploy_standard_template,
            AzureFlowDeployStandardTemplateInput,
        )
        
        with patch("jexida_dashboard.mcp_tools_core.tools.azure.flows.azure_deployments_deploy_to_resource_group") as mock_deploy:
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.provisioning_state = "Succeeded"
            mock_result.correlation_id = "abc-123"
            mock_result.outputs = [
                MagicMock(key="webAppUrl", value="https://myapp.azurewebsites.net"),
            ]
            mock_deploy.return_value = mock_result
            
            template = {
                "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
                "contentVersion": "1.0.0.0",
                "resources": []
            }
            
            result = await azure_flow_deploy_standard_template(
                AzureFlowDeployStandardTemplateInput(
                    resource_group="rg-myapp-dev",
                    deployment_name="deploy-001",
                    template_source=json.dumps(template),
                )
            )
            
            self.assertTrue(result.ok)
            self.assertEqual(result.provisioning_state, "Succeeded")
            self.assertEqual(result.outputs["webAppUrl"], "https://myapp.azurewebsites.net")

    async def test_invalid_template(self):
        """Test handling of invalid template."""
        from jexida_dashboard.mcp_tools_core.tools.azure.flows import (
            azure_flow_deploy_standard_template,
            AzureFlowDeployStandardTemplateInput,
        )
        
        result = await azure_flow_deploy_standard_template(
            AzureFlowDeployStandardTemplateInput(
                resource_group="rg-myapp-dev",
                deployment_name="deploy-001",
                template_source="not valid json or file path",
            )
        )
        
        self.assertFalse(result.ok)
        self.assertIn("Could not parse", result.error)


class TestAzureCliArgsParsing(unittest.TestCase):
    """Test CLI argument parsing functions."""

    def test_parse_azure_args_basic_flags(self):
        """Test parsing basic --flag value arguments."""
        from jexida_cli.commands.azure import parse_azure_args
        
        result = parse_azure_args("--base-name myapp --location eastus")
        
        self.assertEqual(result["flags"]["base_name"], "myapp")
        self.assertEqual(result["flags"]["location"], "eastus")

    def test_parse_azure_args_equals_format(self):
        """Test parsing --flag=value format."""
        from jexida_cli.commands.azure import parse_azure_args
        
        result = parse_azure_args("--base-name=myapp --environment=staging")
        
        self.assertEqual(result["flags"]["base_name"], "myapp")
        self.assertEqual(result["flags"]["environment"], "staging")

    def test_parse_azure_args_boolean_flags(self):
        """Test parsing boolean --no-flag format."""
        from jexida_cli.commands.azure import parse_azure_args
        
        result = parse_azure_args("--no-storage --no-sql")
        
        self.assertFalse(result["flags"]["storage"])
        self.assertFalse(result["flags"]["sql"])

    def test_parse_azure_args_tags(self):
        """Test parsing --tag key=value."""
        from jexida_cli.commands.azure import parse_azure_args
        
        result = parse_azure_args("--tag env=prod --tag owner=admin")
        
        self.assertEqual(result["tags"]["env"], "prod")
        self.assertEqual(result["tags"]["owner"], "admin")

    def test_parse_azure_args_params(self):
        """Test parsing --param key=value."""
        from jexida_cli.commands.azure import parse_azure_args
        
        result = parse_azure_args("--param appName=myapp --param instanceCount=3")
        
        self.assertEqual(result["params"]["appName"], "myapp")
        self.assertEqual(result["params"]["instanceCount"], "3")


class TestAzureCliHandlers(unittest.TestCase):
    """Test Azure CLI command handlers."""

    def test_handle_azure_help(self):
        """Test /azure help output."""
        from jexida_cli.commands.azure import handle_azure_help
        
        mock_renderer = MagicMock()
        
        result = handle_azure_help(mock_renderer)
        
        self.assertEqual(result, "continue")
        mock_renderer.info.assert_called_once()
        # Check that help text contains expected content
        call_args = mock_renderer.info.call_args
        help_text = call_args[0][0]
        self.assertIn("/azure create-env", help_text)
        self.assertIn("/azure add-data", help_text)
        self.assertIn("/azure deploy", help_text)

    def test_handle_azure_create_env_missing_args(self):
        """Test create-env with missing required args."""
        from jexida_cli.commands.azure import handle_azure_create_env
        
        mock_renderer = MagicMock()
        mock_mcp = MagicMock()
        
        # Missing --base-name
        result = handle_azure_create_env(mock_renderer, mock_mcp, "--location eastus")
        
        self.assertEqual(result, "continue")
        mock_renderer.error.assert_called()
        self.assertIn("--base-name", str(mock_renderer.error.call_args))

    def test_handle_azure_create_env_success(self):
        """Test create-env successful call."""
        from jexida_cli.commands.azure import handle_azure_create_env
        
        mock_renderer = MagicMock()
        mock_mcp = MagicMock()
        mock_mcp.run_tool.return_value = {
            "success": True,
            "result": {
                "ok": True,
                "summary": "Created environment",
                "web_app_url": "https://myapp-dev.azurewebsites.net",
            }
        }
        
        result = handle_azure_create_env(
            mock_renderer, mock_mcp,
            "--base-name myapp --location eastus"
        )
        
        self.assertEqual(result, "continue")
        mock_mcp.run_tool.assert_called_once()
        call_args = mock_mcp.run_tool.call_args
        self.assertEqual(call_args[0][0], "azure_flow_create_app_environment")
        self.assertEqual(call_args[0][1]["base_name"], "myapp")
        self.assertEqual(call_args[0][1]["location"], "eastus")
        mock_renderer.success.assert_called()


if __name__ == "__main__":
    unittest.main()

