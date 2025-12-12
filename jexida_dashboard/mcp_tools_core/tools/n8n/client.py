"""HTTP client for n8n REST API.

Handles authentication and provides reusable connection logic
for all n8n API interactions.
"""

import os
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class N8nConfig:
    """Configuration for n8n connection."""
    
    base_url: str
    username: str
    password: str
    ssh_host: str
    ssh_user: str
    timeout: int = 30
    
    @classmethod
    def from_env(cls) -> "N8nConfig":
        """Load configuration from environment variables."""
        return cls(
            base_url=os.environ.get("N8N_BASE_URL", "http://192.168.1.254:5678"),
            username=os.environ.get("N8N_USER", "admin"),
            password=os.environ.get("N8N_PASSWORD", ""),
            ssh_host=os.environ.get("N8N_SSH_HOST", "192.168.1.254"),
            ssh_user=os.environ.get("N8N_SSH_USER", "jexida"),
            timeout=int(os.environ.get("N8N_TIMEOUT", "30")),
        )
    
    @classmethod
    def from_secrets_store(cls) -> Optional["N8nConfig"]:
        """Load configuration from the encrypted secrets store.
        
        Returns:
            N8nConfig if secrets found, None otherwise
        """
        try:
            from secrets_app.models import Secret
            
            def get_secret(key: str, default: str = "") -> str:
                """Get a secret value by key."""
                try:
                    secret = Secret.objects.get(service_type="n8n", key=key)
                    return secret.get_value()
                except Secret.DoesNotExist:
                    return default
            
            # Check if we have n8n secrets
            if not Secret.objects.filter(service_type="n8n").exists():
                return None
            
            url = get_secret("url", "http://192.168.1.254:5678")
            username = get_secret("username", "admin")
            password = get_secret("password", "")
            
            # Extract host from URL for SSH
            import re
            host_match = re.search(r'://([^:/]+)', url)
            ssh_host = host_match.group(1) if host_match else "192.168.1.254"
            
            logger.info("Loaded n8n config from secrets store")
            return cls(
                base_url=url,
                username=username,
                password=password,
                ssh_host=ssh_host,
                ssh_user="jexida",
                timeout=30,
            )
        except Exception as e:
            logger.debug(f"Could not load from secrets store: {e}")
            return None
    
    @classmethod
    def from_settings(cls) -> "N8nConfig":
        """Load configuration from secrets store, then Django settings, then env."""
        # Try secrets store first (encrypted credentials)
        config = cls.from_secrets_store()
        if config:
            return config
        
        # Fall back to Django settings / env vars
        try:
            from django.conf import settings
            return cls(
                base_url=getattr(settings, "N8N_BASE_URL", None) or os.environ.get("N8N_BASE_URL", "http://192.168.1.254:5678"),
                username=getattr(settings, "N8N_USER", None) or os.environ.get("N8N_USER", "admin"),
                password=getattr(settings, "N8N_PASSWORD", None) or os.environ.get("N8N_PASSWORD", ""),
                ssh_host=getattr(settings, "N8N_SSH_HOST", None) or os.environ.get("N8N_SSH_HOST", "192.168.1.254"),
                ssh_user=getattr(settings, "N8N_SSH_USER", None) or os.environ.get("N8N_SSH_USER", "jexida"),
                timeout=int(getattr(settings, "N8N_TIMEOUT", None) or os.environ.get("N8N_TIMEOUT", "30")),
            )
        except Exception:
            return cls.from_env()


class N8nClient:
    """HTTP client for n8n REST API with Basic Auth support."""
    
    def __init__(self, config: Optional[N8nConfig] = None):
        """Initialize the client.
        
        Args:
            config: Optional configuration. If not provided, loads from settings/env.
        """
        self.config = config or N8nConfig.from_settings()
        self._client: Optional[httpx.Client] = None
    
    @property
    def client(self) -> httpx.Client:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.config.base_url,
                auth=(self.config.username, self.config.password),
                timeout=self.config.timeout,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
        return self._client
    
    def close(self):
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def health_check(self) -> Dict[str, Any]:
        """Check n8n health status.
        
        Returns:
            Health check result with status and details
        """
        try:
            response = self.client.get("/healthz")
            return {
                "healthy": response.status_code == 200,
                "status_code": response.status_code,
                "response": response.text,
            }
        except httpx.RequestError as e:
            return {
                "healthy": False,
                "status_code": 0,
                "error": str(e),
            }
    
    def list_workflows(self) -> Dict[str, Any]:
        """List all workflows.
        
        Returns:
            List of workflows or error
        """
        try:
            response = self.client.get("/api/v1/workflows")
            response.raise_for_status()
            return {
                "success": True,
                "workflows": response.json().get("data", []),
            }
        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
            }
        except httpx.RequestError as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Get a specific workflow by ID.
        
        Args:
            workflow_id: The workflow ID
            
        Returns:
            Workflow details or error
        """
        try:
            response = self.client.get(f"/api/v1/workflows/{workflow_id}")
            response.raise_for_status()
            return {
                "success": True,
                "workflow": response.json(),
            }
        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
            }
        except httpx.RequestError as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    def run_workflow(self, workflow_id: str, payload: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute a workflow.
        
        Args:
            workflow_id: The workflow ID to run
            payload: Optional input data for the workflow
            
        Returns:
            Execution result or error
        """
        try:
            response = self.client.post(
                f"/api/v1/workflows/{workflow_id}/run",
                json=payload or {},
            )
            response.raise_for_status()
            return {
                "success": True,
                "execution": response.json(),
            }
        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
            }
        except httpx.RequestError as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    def get_execution(self, execution_id: str) -> Dict[str, Any]:
        """Get execution details.
        
        Args:
            execution_id: The execution ID
            
        Returns:
            Execution details or error
        """
        try:
            response = self.client.get(f"/api/v1/executions/{execution_id}")
            response.raise_for_status()
            return {
                "success": True,
                "execution": response.json(),
            }
        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
            }
        except httpx.RequestError as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    def trigger_webhook(self, path: str, payload: Optional[Dict] = None) -> Dict[str, Any]:
        """Trigger a webhook endpoint.
        
        Args:
            path: Webhook path (after /webhook/)
            payload: Optional JSON payload
            
        Returns:
            Webhook response or error
        """
        try:
            # Webhooks don't use /api/v1 prefix
            url = f"/webhook/{path.lstrip('/')}"
            response = self.client.post(url, json=payload or {})
            
            # Webhooks may return various status codes depending on workflow
            return {
                "success": True,
                "status_code": response.status_code,
                "response": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
            }
        except httpx.RequestError as e:
            return {
                "success": False,
                "error": str(e),
            }

