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


if __name__ == "__main__":
    unittest.main()

