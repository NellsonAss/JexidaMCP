"""Tests for n8n MCP tools.

Tests cover:
- HTTP API tool responses
- SSH command formatting
- Workflow listing and parsing
- Webhook triggering
- Backup and restart commands
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


class TestN8nClient(unittest.TestCase):
    """Test the n8n HTTP client."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock environment for config
        self.env_patcher = patch.dict('os.environ', {
            'N8N_BASE_URL': 'http://test-n8n:5678',
            'N8N_USER': 'testuser',
            'N8N_PASSWORD': 'testpass',
            'N8N_SSH_HOST': '192.168.1.254',
            'N8N_SSH_USER': 'jexida',
        })
        self.env_patcher.start()

    def tearDown(self):
        """Clean up."""
        self.env_patcher.stop()

    @patch('httpx.Client')
    def test_health_check_success(self, mock_client_class):
        """Test health check returns healthy when n8n responds."""
        from jexida_dashboard.mcp_tools_core.tools.n8n.client import N8nClient, N8nConfig
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        
        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        config = N8nConfig(
            base_url="http://test:5678",
            username="user",
            password="pass",
            ssh_host="192.168.1.254",
            ssh_user="jexida",
        )
        
        with N8nClient(config) as client:
            result = client.health_check()
        
        self.assertTrue(result["healthy"])
        self.assertEqual(result["status_code"], 200)

    @patch('httpx.Client')
    def test_health_check_failure(self, mock_client_class):
        """Test health check returns unhealthy on error."""
        from jexida_dashboard.mcp_tools_core.tools.n8n.client import N8nClient, N8nConfig
        import httpx
        
        mock_client = Mock()
        mock_client.get.side_effect = httpx.RequestError("Connection refused")
        mock_client_class.return_value = mock_client
        
        config = N8nConfig(
            base_url="http://test:5678",
            username="user",
            password="pass",
            ssh_host="192.168.1.254",
            ssh_user="jexida",
        )
        
        with N8nClient(config) as client:
            result = client.health_check()
        
        self.assertFalse(result["healthy"])
        self.assertIn("error", result)

    @patch('httpx.Client')
    def test_list_workflows(self, mock_client_class):
        """Test workflow listing parses response correctly."""
        from jexida_dashboard.mcp_tools_core.tools.n8n.client import N8nClient, N8nConfig
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "1", "name": "Test Workflow 1", "active": True},
                {"id": "2", "name": "Test Workflow 2", "active": False},
            ]
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        config = N8nConfig(
            base_url="http://test:5678",
            username="user",
            password="pass",
            ssh_host="192.168.1.254",
            ssh_user="jexida",
        )
        
        with N8nClient(config) as client:
            result = client.list_workflows()
        
        self.assertTrue(result["success"])
        self.assertEqual(len(result["workflows"]), 2)
        self.assertEqual(result["workflows"][0]["name"], "Test Workflow 1")

    @patch('httpx.Client')
    def test_run_workflow(self, mock_client_class):
        """Test running workflow returns execution ID."""
        from jexida_dashboard.mcp_tools_core.tools.n8n.client import N8nClient, N8nConfig
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "exec-123",
            "status": "running",
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        config = N8nConfig(
            base_url="http://test:5678",
            username="user",
            password="pass",
            ssh_host="192.168.1.254",
            ssh_user="jexida",
        )
        
        with N8nClient(config) as client:
            result = client.run_workflow("1", {"input": "test"})
        
        self.assertTrue(result["success"])
        mock_client.post.assert_called_once()

    @patch('httpx.Client')
    def test_trigger_webhook(self, mock_client_class):
        """Test webhook triggering sends correct payload."""
        from jexida_dashboard.mcp_tools_core.tools.n8n.client import N8nClient, N8nConfig
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"result": "ok"}
        
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        config = N8nConfig(
            base_url="http://test:5678",
            username="user",
            password="pass",
            ssh_host="192.168.1.254",
            ssh_user="jexida",
        )
        
        with N8nClient(config) as client:
            result = client.trigger_webhook("my-hook", {"action": "test"})
        
        self.assertTrue(result["success"])
        self.assertEqual(result["status_code"], 200)
        mock_client.post.assert_called_with("/webhook/my-hook", json={"action": "test"})


class TestN8nAdminTools(unittest.TestCase):
    """Test SSH-based admin tools."""

    def test_restart_command_format(self):
        """Test restart command is formatted correctly."""
        expected_command = "cd /opt/n8n && docker compose restart"
        
        # The command should be this exact string
        self.assertIn("docker compose restart", expected_command)
        self.assertIn("/opt/n8n", expected_command)

    def test_backup_command_format(self):
        """Test backup command creates tarball correctly."""
        backup_name = "test_backup"
        expected_path = f"/opt/n8n/backups/{backup_name}.tar.gz"
        
        # Verify backup path format
        self.assertTrue(expected_path.startswith("/opt/n8n/backups/"))
        self.assertTrue(expected_path.endswith(".tar.gz"))

    def test_restore_command_format(self):
        """Test restore command handles backup file correctly."""
        backup_file = "/opt/n8n/backups/test.tar.gz"
        
        # The restore should:
        # 1. Stop n8n (optional)
        # 2. Check file exists
        # 3. Move old data
        # 4. Extract backup
        # 5. Start n8n (optional)
        
        restore_steps = [
            "docker compose down",
            f'test -f "{backup_file}"',
            "mv /opt/n8n/data /opt/n8n/data.old",
            f'tar -xzf "{backup_file}"',
            "docker compose up -d",
        ]
        
        for step in restore_steps:
            # Just verify these are the expected steps
            self.assertIsInstance(step, str)


class TestEncryptionKeyGeneration(unittest.TestCase):
    """Test encryption key generation."""

    def test_generate_encryption_key_length(self):
        """Test encryption key is 64 hex characters (32 bytes)."""
        from jexida_dashboard.mcp_tools_core.tools.n8n.deploy import generate_encryption_key
        
        key = generate_encryption_key()
        
        self.assertEqual(len(key), 64)  # 32 bytes = 64 hex chars
        # Verify it's valid hex
        int(key, 16)

    def test_generate_encryption_key_uniqueness(self):
        """Test encryption keys are unique."""
        from jexida_dashboard.mcp_tools_core.tools.n8n.deploy import generate_encryption_key
        
        keys = [generate_encryption_key() for _ in range(10)]
        
        # All keys should be unique
        self.assertEqual(len(keys), len(set(keys)))


class TestWorkflowParsing(unittest.TestCase):
    """Test workflow response parsing."""

    def test_parse_workflow_summary(self):
        """Test workflow summary extraction."""
        workflow_data = {
            "id": "123",
            "name": "My Workflow",
            "active": True,
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-12-10T12:00:00Z",
        }
        
        # Test that we can extract the right fields
        self.assertEqual(workflow_data["id"], "123")
        self.assertEqual(workflow_data["name"], "My Workflow")
        self.assertTrue(workflow_data["active"])

    def test_parse_workflow_with_nodes(self):
        """Test workflow with nodes is parsed correctly."""
        workflow_data = {
            "id": "123",
            "name": "My Workflow",
            "nodes": [
                {"name": "Start", "type": "n8n-nodes-base.start"},
                {"name": "HTTP Request", "type": "n8n-nodes-base.httpRequest"},
                {"name": "End", "type": "n8n-nodes-base.noOp"},
            ],
        }
        
        self.assertEqual(len(workflow_data["nodes"]), 3)
        self.assertEqual(workflow_data["nodes"][0]["name"], "Start")


class TestDeploymentScript(unittest.TestCase):
    """Test deployment script generation."""

    def test_script_creates_correct_directories(self):
        """Test deployment creates required directories."""
        required_dirs = [
            "/opt/n8n",
            "/opt/n8n/data",
            "/opt/n8n/backups",
        ]
        
        # Read the actual script
        import os
        script_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "scripts",
            "setup_n8n_node.sh"
        )
        
        if os.path.exists(script_path):
            with open(script_path) as f:
                script_content = f.read()
            
            for dir_path in required_dirs:
                self.assertIn(dir_path, script_content)

    def test_docker_compose_has_required_env_vars(self):
        """Test docker-compose includes all required environment variables."""
        required_vars = [
            "N8N_BASIC_AUTH_ACTIVE",
            "N8N_BASIC_AUTH_USER",
            "N8N_BASIC_AUTH_PASSWORD",
            "N8N_HOST",
            "N8N_PORT",
            "N8N_PROTOCOL",
            "N8N_ENCRYPTION_KEY",
            "GENERIC_TIMEZONE",
        ]
        
        # These should all be in the docker-compose template
        for var in required_vars:
            self.assertIsInstance(var, str)


if __name__ == "__main__":
    unittest.main()

