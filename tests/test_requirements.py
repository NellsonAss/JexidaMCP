"""Tests to validate requirements in site_requirements.json.

This module ensures:
1. All requirements have corresponding test methods
2. Requirements are actually implemented
3. Django views and URLs are properly configured
"""

import ast
import json
import os
import sys
import unittest
from pathlib import Path

# Add workspace root to path
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))


class RequirementsComplianceTest(unittest.TestCase):
    """Ensure all requirements in site_requirements.json are tested."""
    
    @classmethod
    def setUpClass(cls):
        """Load requirements from JSON file."""
        requirements_file = WORKSPACE_ROOT / "site_requirements.json"
        with open(requirements_file) as f:
            data = json.load(f)
        cls.requirements = data.get("requirements", [])
    
    def test_requirements_file_exists(self):
        """site_requirements.json must exist."""
        requirements_file = WORKSPACE_ROOT / "site_requirements.json"
        self.assertTrue(requirements_file.exists(), "site_requirements.json not found")
    
    def test_all_requirements_have_ids(self):
        """Every requirement must have a unique ID."""
        ids = [req.get("id") for req in self.requirements]
        self.assertTrue(all(ids), "All requirements must have IDs")
        self.assertEqual(len(ids), len(set(ids)), "Requirement IDs must be unique")
    
    def test_all_requirements_have_titles(self):
        """Every requirement must have a title."""
        for req in self.requirements:
            self.assertTrue(
                req.get("title"),
                f"Requirement {req.get('id')} missing title"
            )
    
    def test_all_requirements_have_description(self):
        """Every requirement must have a description."""
        for req in self.requirements:
            self.assertTrue(
                req.get("description"),
                f"Requirement {req.get('id')} missing description"
            )
    
    def test_req_002_dashboard_migrated(self):
        """REQ-002: Dashboard migrated from FastAPI to Django."""
        # Check Django project structure exists
        django_project = WORKSPACE_ROOT / "jexida_dashboard"
        self.assertTrue(django_project.exists(), "Django project not found")
        
        # Check key apps exist
        apps = ["dashboard", "secrets_app", "assistant_app", "accounts"]
        for app in apps:
            app_dir = django_project / app
            self.assertTrue(app_dir.exists(), f"App {app} not found")
        
        # Check views.py exists in each app
        for app in apps:
            views_file = django_project / app / "views.py"
            self.assertTrue(views_file.exists(), f"{app}/views.py not found")
    
    def test_req_003_core_services_framework_agnostic(self):
        """REQ-003: Core package has no web framework dependencies."""
        core_dir = WORKSPACE_ROOT / "core"
        self.assertTrue(core_dir.exists(), "core/ package not found")
        
        forbidden_imports = ["fastapi", "django", "flask", "starlette"]
        
        for py_file in core_dir.rglob("*.py"):
            with open(py_file) as f:
                try:
                    tree = ast.parse(f.read())
                except SyntaxError:
                    continue
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            module_name = alias.name.split(".")[0]
                            self.assertNotIn(
                                module_name,
                                forbidden_imports,
                                f"Forbidden import '{module_name}' found in {py_file}"
                            )
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            module_name = node.module.split(".")[0]
                            self.assertNotIn(
                                module_name,
                                forbidden_imports,
                                f"Forbidden import from '{module_name}' found in {py_file}"
                            )
    
    def test_req_004_database_migration(self):
        """REQ-004: Django models exist for domain objects."""
        # Check model files exist
        secrets_models = WORKSPACE_ROOT / "jexida_dashboard" / "secrets_app" / "models.py"
        self.assertTrue(secrets_models.exists(), "secrets_app/models.py not found")
        
        assistant_models = WORKSPACE_ROOT / "jexida_dashboard" / "assistant_app" / "models.py"
        self.assertTrue(assistant_models.exists(), "assistant_app/models.py not found")
        
        # Check migration command exists
        migrate_cmd = (
            WORKSPACE_ROOT / "jexida_dashboard" / "assistant_app" / 
            "management" / "commands" / "migrate_from_fastapi.py"
        )
        self.assertTrue(migrate_cmd.exists(), "migrate_from_fastapi command not found")


class CorePackageTest(unittest.TestCase):
    """Test the core package functionality."""
    
    def test_providers_package_exists(self):
        """core/providers package must exist."""
        providers_dir = WORKSPACE_ROOT / "core" / "providers"
        self.assertTrue(providers_dir.exists())
    
    def test_providers_can_be_imported(self):
        """Providers can be imported."""
        try:
            from core.providers import (
                BaseProvider,
                ProviderResponse,
                ToolCall,
                MockProvider,
            )
        except ImportError as e:
            self.fail(f"Failed to import providers: {e}")
    
    def test_actions_package_exists(self):
        """core/actions package must exist."""
        actions_dir = WORKSPACE_ROOT / "core" / "actions"
        self.assertTrue(actions_dir.exists())
    
    def test_actions_can_be_imported(self):
        """Actions can be imported."""
        try:
            from core.actions import (
                ActionRegistry,
                ActionResult,
                ActionType,
                get_action_registry,
            )
        except ImportError as e:
            self.fail(f"Failed to import actions: {e}")
    
    def test_services_package_exists(self):
        """core/services package must exist."""
        services_dir = WORKSPACE_ROOT / "core" / "services"
        self.assertTrue(services_dir.exists())
    
    def test_mock_provider_is_configured(self):
        """Mock provider should always be configured."""
        from core.providers import MockProvider
        
        provider = MockProvider()
        self.assertTrue(provider.is_configured())
        self.assertEqual(provider.provider_name, "mock")


class DjangoProjectStructureTest(unittest.TestCase):
    """Test Django project structure."""
    
    def test_manage_py_exists(self):
        """manage.py must exist."""
        manage_py = WORKSPACE_ROOT / "jexida_dashboard" / "manage.py"
        self.assertTrue(manage_py.exists())
    
    def test_settings_py_exists(self):
        """settings.py must exist."""
        settings_py = WORKSPACE_ROOT / "jexida_dashboard" / "jexida_dashboard" / "settings.py"
        self.assertTrue(settings_py.exists())
    
    def test_urls_py_exists(self):
        """urls.py must exist."""
        urls_py = WORKSPACE_ROOT / "jexida_dashboard" / "jexida_dashboard" / "urls.py"
        self.assertTrue(urls_py.exists())
    
    def test_templates_directory_exists(self):
        """templates directory must exist."""
        templates_dir = WORKSPACE_ROOT / "jexida_dashboard" / "templates"
        self.assertTrue(templates_dir.exists())
    
    def test_base_template_exists(self):
        """base.html template must exist."""
        base_template = WORKSPACE_ROOT / "jexida_dashboard" / "templates" / "base.html"
        self.assertTrue(base_template.exists())


class DashboardRequirementsTest(unittest.TestCase):
    """Test DASH-001 through DASH-006 dashboard requirements."""
    
    def test_dash_001_overview_mcp_status(self):
        """DASH-001: Dashboard overview shows MCP status, nodes, and jobs."""
        # Check home template exists and has key sections
        home_template = WORKSPACE_ROOT / "jexida_dashboard" / "templates" / "dashboard" / "home.html"
        self.assertTrue(home_template.exists(), "home.html template not found")
        
        with open(home_template) as f:
            content = f.read()
        
        # Check for MCP status section
        self.assertIn("MCP Status", content, "MCP Status section not found in home.html")
        self.assertIn("mcp_status", content, "mcp_status variable not used in template")
        
        # Check for nodes section
        self.assertIn("Worker Nodes", content, "Worker Nodes section not found")
        self.assertIn("nodes_active", content, "nodes_active variable not used")
        
        # Check for jobs section
        self.assertIn("Jobs", content, "Jobs section not found")
        self.assertIn("jobs_running", content, "jobs_running variable not used")
    
    def test_dash_002_models_view_exists(self):
        """DASH-002: Model selection and orchestration mode UI."""
        # Check models template exists
        models_template = WORKSPACE_ROOT / "jexida_dashboard" / "templates" / "dashboard" / "models.html"
        self.assertTrue(models_template.exists(), "models.html template not found")
        
        with open(models_template) as f:
            content = f.read()
        
        # Check for model selection form
        self.assertIn("model_id", content, "model_id form field not found")
        self.assertIn("available_models", content, "available_models not used in template")
        
        # Check for orchestration modes
        self.assertIn("direct", content, "direct mode not mentioned")
        self.assertIn("cascade", content, "cascade mode not mentioned")
        self.assertIn("router", content, "router mode not mentioned")
        
        # Check URL exists in urls.py
        urls_file = WORKSPACE_ROOT / "jexida_dashboard" / "dashboard" / "urls.py"
        with open(urls_file) as f:
            urls_content = f.read()
        self.assertIn("models", urls_content, "models URL not found in urls.py")
    
    def test_dash_003_tool_categories_displayed(self):
        """DASH-003: Tool categories with safe entry points."""
        # Check home template has category links
        home_template = WORKSPACE_ROOT / "jexida_dashboard" / "templates" / "dashboard" / "home.html"
        with open(home_template) as f:
            content = f.read()
        
        # Check for category display
        self.assertIn("top_categories", content, "top_categories not used in home.html")
        self.assertIn("Tool Categories", content, "Tool Categories section not found")
    
    def test_dash_004_network_hardening_view(self):
        """DASH-004: Network Hardening section with evaluations."""
        # Check network hardening template exists
        hardening_template = WORKSPACE_ROOT / "jexida_dashboard" / "templates" / "dashboard" / "network_hardening.html"
        self.assertTrue(hardening_template.exists(), "network_hardening.html not found")
        
        with open(hardening_template) as f:
            content = f.read()
        
        # Check for evaluation sections
        self.assertIn("evaluations", content, "evaluations variable not used")
        # Evaluations are rendered from view data, not hardcoded in template
        self.assertIn("eval.name", content, "evaluation names not rendered")
        self.assertIn("eval.description", content, "evaluation descriptions not rendered")
        self.assertIn("Security Checks", content, "Security Checks section not found")
        
        # Check for run button
        self.assertIn("run_evaluation", content, "run_evaluation URL not found")
        
        # Check evaluation result partial exists
        result_partial = WORKSPACE_ROOT / "jexida_dashboard" / "templates" / "dashboard" / "partials" / "evaluation_result.html"
        self.assertTrue(result_partial.exists(), "evaluation_result.html partial not found")
    
    def test_dash_005_nodes_health_indicators(self):
        """DASH-005: Worker node health in dashboard."""
        # Check home template has node health info
        home_template = WORKSPACE_ROOT / "jexida_dashboard" / "templates" / "dashboard" / "home.html"
        with open(home_template) as f:
            content = f.read()
        
        # Check for node status indicators
        self.assertIn("recent_nodes", content, "recent_nodes not used in template")
        self.assertIn("is_active", content, "is_active status not checked")
        self.assertIn("node_detail", content, "node_detail link not found")
    
    def test_dash_006_assistant_mcp_tools_bridge(self):
        """DASH-006: AI Assistant connects to MCP tools."""
        # Check mcp_tools_bridge.py exists
        bridge_file = WORKSPACE_ROOT / "jexida_dashboard" / "assistant_app" / "mcp_tools_bridge.py"
        self.assertTrue(bridge_file.exists(), "mcp_tools_bridge.py not found")
        
        with open(bridge_file) as f:
            bridge_content = f.read()
        
        # Check for key functions in bridge
        self.assertIn("get_mcp_tool_definitions", bridge_content, "get_mcp_tool_definitions not defined")
        self.assertIn("execute_mcp_tool", bridge_content, "execute_mcp_tool not defined")
        self.assertIn("is_dangerous_tool", bridge_content, "is_dangerous_tool not defined")
        
        # Check api_views.py has confirm-tool endpoint
        api_views = WORKSPACE_ROOT / "jexida_dashboard" / "assistant_app" / "api_views.py"
        with open(api_views) as f:
            api_content = f.read()
        self.assertIn("api_confirm_tool", api_content, "api_confirm_tool not in api_views")
        self.assertIn("pending_tool_call", api_content, "pending_tool_call handling not found")
        
        # Check api_urls.py has the endpoint
        api_urls = WORKSPACE_ROOT / "jexida_dashboard" / "assistant_app" / "api_urls.py"
        with open(api_urls) as f:
            urls_content = f.read()
        self.assertIn("confirm-tool", urls_content, "confirm-tool URL not found")
        
        # Check chat template has confirmation modal
        chat_template = WORKSPACE_ROOT / "jexida_dashboard" / "templates" / "assistant" / "chat.html"
        with open(chat_template) as f:
            chat_content = f.read()
        self.assertIn("toolConfirmModal", chat_content, "Tool confirmation modal not found")
        self.assertIn("pendingToolCall", chat_content, "pendingToolCall handling not found")
    
    def test_mcp_azure_001_azure_sdk_tools(self):
        """MCP-AZURE-001: Azure SDK MCP Tools for Infrastructure Automation."""
        azure_tools_dir = WORKSPACE_ROOT / "jexida_dashboard" / "mcp_tools_core" / "tools" / "azure"
        
        # Check core Azure modules exist
        self.assertTrue(
            (azure_tools_dir / "auth.py").exists(),
            "azure/auth.py not found"
        )
        self.assertTrue(
            (azure_tools_dir / "core.py").exists(),
            "azure/core.py not found"
        )
        self.assertTrue(
            (azure_tools_dir / "resources.py").exists(),
            "azure/resources.py not found"
        )
        self.assertTrue(
            (azure_tools_dir / "deployments.py").exists(),
            "azure/deployments.py not found"
        )
        self.assertTrue(
            (azure_tools_dir / "app_platform.py").exists(),
            "azure/app_platform.py not found"
        )
        self.assertTrue(
            (azure_tools_dir / "data.py").exists(),
            "azure/data.py not found"
        )
        self.assertTrue(
            (azure_tools_dir / "monitoring.py").exists(),
            "azure/monitoring.py not found"
        )
        self.assertTrue(
            (azure_tools_dir / "cost.py").exists(),
            "azure/cost.py not found"
        )
        
        # Check Phase 2 stubs exist
        self.assertTrue(
            (azure_tools_dir / "network.py").exists(),
            "azure/network.py stub not found"
        )
        self.assertTrue(
            (azure_tools_dir / "security.py").exists(),
            "azure/security.py stub not found"
        )
        self.assertTrue(
            (azure_tools_dir / "compute.py").exists(),
            "azure/compute.py stub not found"
        )
        self.assertTrue(
            (azure_tools_dir / "kubernetes.py").exists(),
            "azure/kubernetes.py stub not found"
        )
        
        # Check auth module has required functions
        with open(azure_tools_dir / "auth.py") as f:
            auth_content = f.read()
        self.assertIn("get_azure_credential", auth_content, "get_azure_credential not found")
        self.assertIn("DefaultAzureCredential", auth_content, "DefaultAzureCredential not used")
        self.assertIn("AzureError", auth_content, "AzureError class not found")
        self.assertIn("AzureAuthError", auth_content, "AzureAuthError class not found")
        
        # Check core module has required tools
        with open(azure_tools_dir / "core.py") as f:
            core_content = f.read()
        self.assertIn("azure_core_get_connection_info", core_content, "get_connection_info not found")
        self.assertIn("azure_core_list_subscriptions", core_content, "list_subscriptions not found")
        self.assertIn("azure_core_list_resource_groups", core_content, "list_resource_groups not found")
        self.assertIn("azure_core_create_resource_group", core_content, "create_resource_group not found")
        self.assertIn("azure_core_delete_resource_group", core_content, "delete_resource_group not found")
        
        # Check registration script exists
        register_script = WORKSPACE_ROOT / "scripts" / "register_azure_sdk_tools.py"
        self.assertTrue(register_script.exists(), "register_azure_sdk_tools.py not found")
        
        # Check documentation exists
        docs_file = WORKSPACE_ROOT / "docs" / "azure_mcp_tools.md"
        self.assertTrue(docs_file.exists(), "docs/azure_mcp_tools.md not found")
        
        # Check Azure test file exists
        test_file = WORKSPACE_ROOT / "tests" / "test_azure_tools.py"
        self.assertTrue(test_file.exists(), "tests/test_azure_tools.py not found")
        
        # Check requirements.txt has Azure SDK packages
        requirements_file = WORKSPACE_ROOT / "jexida_dashboard" / "requirements.txt"
        with open(requirements_file) as f:
            requirements_content = f.read()
        self.assertIn("azure-identity", requirements_content, "azure-identity not in requirements.txt")
        self.assertIn("azure-mgmt-resource", requirements_content, "azure-mgmt-resource not in requirements.txt")


if __name__ == "__main__":
    unittest.main()

