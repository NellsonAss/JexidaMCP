"""Client for interacting with the Jexida MCP server API.

Supports both tool execution and the unified model/strategy orchestration system.
Updated to match the new Django REST API paths.
"""

import httpx
from typing import Optional, Dict, Any, List

from .state.config import Config


class MCPClient:
    """Handles HTTP communication with the MCP server.
    
    Provides methods for:
    - Tool discovery and execution
    - Strategy/model listing and selection
    - Chat completion through the unified registry
    
    API Paths (Django):
    - Tools: /tools/api/tools/
    - Tools run: /tools/api/tools/{name}/run/
    - Assistant: /api/assistant/
    """

    def __init__(self, config: Config):
        """Initialize the MCP client.

        Args:
            config: The application configuration.
        """
        self.host = config.host
        self.port = config.mcp_port
        self.timeout = config.mcp_timeout
        
        # Base URLs for different API endpoints
        # Tools API is under /tools/api/
        # Assistant API is under /api/assistant/
        self.base_url = f"http://{self.host}:{self.port}"
        self.tools_api_url = f"{self.base_url}/tools/api"
        self.assistant_api_url = f"{self.base_url}/api/assistant"
        
        # Use persistent clients for connection pooling
        self._tools_client = httpx.Client(
            base_url=self.tools_api_url,
            timeout=self.timeout,
        )
        self._assistant_client = httpx.Client(
            base_url=self.assistant_api_url,
            timeout=self.timeout,
        )
        
        # Track current strategy
        self._current_strategy_id: Optional[str] = None

    # -------------------------------------------------------------------------
    # Tool Management
    # -------------------------------------------------------------------------

    def get_available_tools(self) -> Optional[List[Dict[str, Any]]]:
        """Fetch the list of available tools from the MCP server.

        Returns:
            A list of tool definitions, or None on error.
        """
        try:
            response = self._tools_client.get("/tools/")
            response.raise_for_status()
            data = response.json()
            
            # Handle both direct list and wrapped response
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "tools" in data:
                return data["tools"]
            return data
        except (httpx.RequestError, httpx.HTTPStatusError):
            return None

    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a specific tool on the MCP server.

        Args:
            tool_name: The name of the tool to execute.
            parameters: A dictionary of parameters for the tool.

        Returns:
            A dictionary containing the result of the tool execution.
        """
        try:
            response = self._tools_client.post(
                f"/tools/{tool_name}/run/",
                json=parameters,
            )
            response.raise_for_status()
            result = response.json()
            
            # Ensure success flag is set
            if "success" not in result:
                result["success"] = True
            return result
            
        except httpx.HTTPStatusError as e:
            try:
                error_details = e.response.json()
            except Exception:
                error_details = {"error": e.response.text}
            return {
                "success": False,
                "error": f"MCP Server Error: {e.response.status_code}",
                "details": error_details,
            }
        except httpx.RequestError as e:
            return {
                "success": False,
                "error": "Network error while contacting MCP server",
                "details": str(e),
            }

    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific tool.

        Args:
            tool_name: The name of the tool.

        Returns:
            Tool information dict, or None on error.
        """
        try:
            response = self._tools_client.get(f"/tools/{tool_name}/")
            response.raise_for_status()
            return response.json()
        except (httpx.RequestError, httpx.HTTPStatusError):
            return None

    # -------------------------------------------------------------------------
    # Strategy/Model Management (Unified Orchestration System)
    # -------------------------------------------------------------------------

    def get_strategies(self) -> Optional[Dict[str, Any]]:
        """Fetch all available strategies from the MCP server.

        Returns:
            Dict with 'strategies', 'active_strategy_id', and 'groups', or None on error.
        """
        try:
            response = self._assistant_client.get("/strategies/")
            response.raise_for_status()
            data = response.json()
            self._current_strategy_id = data.get("active_strategy_id")
            return data
        except (httpx.RequestError, httpx.HTTPStatusError):
            return None

    def get_active_strategy(self) -> Optional[Dict[str, Any]]:
        """Get the currently active strategy.

        Returns:
            Dict with 'strategy', 'strategy_id', and optionally 'model', or None on error.
        """
        try:
            response = self._assistant_client.get("/strategies/active/")
            response.raise_for_status()
            data = response.json()
            self._current_strategy_id = data.get("strategy_id")
            return data
        except (httpx.RequestError, httpx.HTTPStatusError):
            return None

    def set_active_strategy(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """Set the active strategy.

        Args:
            strategy_id: ID of the strategy to activate (e.g., "single:gpt-5-nano")

        Returns:
            Dict with 'success', 'strategy', 'message', or None on error.
        """
        try:
            response = self._assistant_client.post(
                "/strategies/active/",
                params={"strategy_id": strategy_id},
            )
            response.raise_for_status()
            data = response.json()
            if data.get("success"):
                self._current_strategy_id = strategy_id
            return data
        except httpx.HTTPStatusError as e:
            try:
                error_details = e.response.json()
            except Exception:
                error_details = {"error": e.response.text}
            return {
                "success": False,
                "error": f"Server Error: {e.response.status_code}",
                "details": error_details,
            }
        except httpx.RequestError as e:
            return {
                "success": False,
                "error": "Network error",
                "details": str(e),
            }

    def get_strategy_details(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific strategy.

        Args:
            strategy_id: Strategy identifier

        Returns:
            Dict with 'strategy' and 'models', or None on error.
        """
        try:
            response = self._assistant_client.get(f"/strategies/{strategy_id}/")
            response.raise_for_status()
            return response.json()
        except (httpx.RequestError, httpx.HTTPStatusError):
            return None

    def discover_local_models(self, ollama_host: str = "http://localhost:11434") -> Optional[Dict[str, Any]]:
        """Trigger discovery of local models from Ollama.

        Args:
            ollama_host: URL of the Ollama server

        Returns:
            Dict with 'success', 'discovered_count', 'models', or None on error.
        """
        try:
            response = self._assistant_client.post(
                "/strategies/discover-local/",
                params={"ollama_host": ollama_host},
            )
            response.raise_for_status()
            return response.json()
        except (httpx.RequestError, httpx.HTTPStatusError):
            return None

    @property
    def current_strategy_id(self) -> Optional[str]:
        """Get the current strategy ID (cached)."""
        return self._current_strategy_id

    # -------------------------------------------------------------------------
    # Chat Completion
    # -------------------------------------------------------------------------

    def chat(
        self,
        message: str,
        conversation_id: Optional[int] = None,
        temperature: Optional[float] = None,
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a chat message through the assistant API.

        Args:
            message: User message
            conversation_id: Optional existing conversation ID
            temperature: Optional temperature override
            mode: Optional mode override

        Returns:
            Dict with response data.
        """
        try:
            payload: Dict[str, Any] = {
                "message": message,
            }
            if conversation_id:
                payload["conversation_id"] = conversation_id
            if temperature is not None:
                payload["temperature"] = temperature
            if mode:
                payload["mode"] = mode

            response = self._assistant_client.post(
                "/chat/",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            try:
                error_details = e.response.json()
            except Exception:
                error_details = {"error": e.response.text}
            return {
                "success": False,
                "error": f"Server Error: {e.response.status_code}",
                "details": error_details,
            }
        except httpx.RequestError as e:
            return {
                "success": False,
                "error": "Network error",
                "details": str(e),
            }

    def get_status(self) -> Dict[str, Any]:
        """Get assistant status.

        Returns:
            Dict with provider info, model, etc.
        """
        try:
            response = self._assistant_client.get("/status/")
            response.raise_for_status()
            return response.json()
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            return {
                "error": str(e),
                "connected": False,
            }

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP clients."""
        self._tools_client.close()
        self._assistant_client.close()

    def __enter__(self) -> "MCPClient":
        """Context manager entry."""
        return self

    def __exit__(self, *args) -> None:
        """Context manager exit."""
        self.close()
