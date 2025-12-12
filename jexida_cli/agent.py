"""LLM agent integration and tool protocol parsing."""

import json
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING, Union

from .ssh_client import SSHClient

if TYPE_CHECKING:
    from .state.session import Session
    from .mcp_client import MCPClient


class Agent:
    """Handles LLM interactions and tool protocol parsing."""

    def __init__(
        self,
        ssh_client: SSHClient,
        model: str,
        mcp_client: Optional["MCPClient"] = None,
    ):
        """Initialize the agent.

        Args:
            ssh_client: SSH client for executing Ollama
            model: Ollama model name
            mcp_client: Optional MCP client for MCP server tools
        """
        self.ssh_client = ssh_client
        self.model = model
        self.mcp_client = mcp_client
        self.conversation_history: List[Dict[str, str]] = []
        self.max_history_turns = 10
        self._context_manager: Optional[Union["Session", Any]] = None
        self._mcp_tools_prompt: Optional[str] = None

    def set_context_manager(self, context_manager: Union["Session", Any]) -> None:
        """Set the context manager for directory awareness.

        Args:
            context_manager: The context/session manager instance
        """
        self._context_manager = context_manager

    def set_conversation_history(self, history: List[Dict[str, str]]) -> None:
        """Set the conversation history (used when loading sessions).

        Args:
            history: The conversation history to set
        """
        self.conversation_history = history

    def set_model(self, model: str) -> None:
        """Change the model at runtime.

        Args:
            model: New model name
        """
        self.model = model

    def load_mcp_tools(self) -> None:
        """Fetch MCP tools and build the tools prompt part, caching it."""
        if self._mcp_tools_prompt is not None or not self.mcp_client:
            return

        mcp_tools = self.mcp_client.get_available_tools()
        if mcp_tools:
            prompt_lines = ["\n\nAVAILABLE MCP SERVER TOOLS:"]
            prompt_lines.append("You can execute these tools on the MCP server using the 'mcp_tool' type.")
            for tool in mcp_tools:
                name = tool.get("name", "N/A")
                description = tool.get("description", "No description.")
                params = tool.get("parameters", [])
                if isinstance(params, list):
                    param_str = ", ".join([p.get("name", "") for p in params])
                elif isinstance(params, dict):
                    param_str = ", ".join(params.keys())
                else:
                    param_str = ""
                prompt_lines.append(f"- {name}: {description} (Parameters: {param_str})")
            self._mcp_tools_prompt = "\n".join(prompt_lines)
        else:
            self._mcp_tools_prompt = "\n\nAVAILABLE MCP SERVER TOOLS:\n(Could not connect to MCP server. MCP tools are unavailable.)"

    def _build_system_prompt(
        self,
        routines: Dict[str, Dict[str, str]],
        mcp_tools_prompt: str,
    ) -> str:
        """Build the system prompt for the LLM.

        Args:
            routines: Available routines dictionary
            mcp_tools_prompt: Prompt part for available MCP tools

        Returns:
            System prompt string
        """
        routines_text = ""
        if routines:
            routines_text = "\nAvailable routines you can reference:\n"
            for name, routine in routines.items():
                routines_text += f"  - {name}: {routine.get('description', 'No description')}\n"

        # Build directory context
        context_text = ""
        if self._context_manager:
            try:
                structure = self._context_manager.scan_structure()
                # Limit structure size to avoid huge prompts
                if len(structure) > 2000:
                    lines = structure.split("\n")[:50]
                    structure = "\n".join(lines) + "\n... (truncated)"
                context_text = f"""

LOCAL DIRECTORY CONTEXT:
The user is running jexida from this directory:
{structure}
"""
            except Exception:
                pass

        return f"""You are an authorized terminal agent operating on behalf of the user.

You have access to THREE execution environments:
1. REMOTE SERVER ({self.ssh_client.connection_string}) - For server administration via shell commands.
2. LOCAL MACHINE - The user's computer for local file operations and shell commands.
3. MCP SERVER - A master control program for managing cloud resources via specific tools.

The user has explicitly authorized you to act on all three systems.

RESPONSE FORMAT:
You MUST respond with JSON in one of these formats:

1. To execute a shell command:
{{
  "type": "shell",
  "target": "ssh",
  "command": "the shell command to run",
  "reason": "what this command does"
}}
   - "target" can be "ssh" (remote server) or "local".

2. To answer a question:
{{
  "type": "answer",
  "text": "your response here"
}}

3. To read a local file:
{{
  "type": "read_file",
  "target": "local",
  "path": "relative/path/to/file",
  "reason": "why you need to read this file"
}}

4. To write to a local file:
{{
  "type": "write_file",
  "target": "local",
  "path": "relative/path/to/file",
  "content": "the full content to write to the file",
  "reason": "why you are writing this content"
}}

5. To search in local files:
{{
  "type": "search_files",
  "target": "local",
  "search_pattern": "glob pattern like '*.py'",
  "search_string": "the text to search for",
  "reason": "why you are performing this search"
}}

6. To execute an MCP server tool:
{{
  "type": "mcp_tool",
  "target": "mcp",
  "tool_name": "the name of the tool to run",
  "parameters": {{ "param1": "value1", ... }},
  "reason": "why you are running this tool"
}}


GUIDELINES:
- Use the appropriate "target" for your action: "ssh", "local", or "mcp".
- For general server admin, use "shell" with "target": "ssh".
- For local file tasks, use "read_file", "write_file", "search_files", or "shell" with "target": "local".
- To manage cloud resources, use "mcp_tool" with "target": "mcp".
- If the 'AVAILABLE MCP SERVER TOOLS' section indicates a connection error, you MUST inform the user that MCP tools are unavailable and ask them how to proceed. Do not attempt to use any `mcp_tool`.
- ALWAYS use "read_file" to get a file's content before proposing to "write_file". Your "write_file" operation MUST include the *entire* file content.
- Be direct and action-oriented. The user will confirm all major actions.
- Do not refuse legitimate requests.
{routines_text}{context_text}{mcp_tools_prompt}
Remember: Respond with JSON only. When in doubt, propose a command with target "ssh" - the user will confirm."""

    def _build_conversation_prompt(
        self,
        user_message: str,
        routines: Dict[str, Dict[str, str]],
    ) -> str:
        """Build the full prompt including conversation history.

        Args:
            user_message: Current user message
            routines: Available routines

        Returns:
            Full prompt string
        """
        # Ensure MCP tools are loaded and cached in the prompt
        self.load_mcp_tools()

        # Build system prompt
        system_prompt = self._build_system_prompt(routines, self._mcp_tools_prompt or "")

        # Build conversation history
        history_text = ""
        if self.conversation_history:
            history_text = "\n\nConversation history:\n"
            for msg in self.conversation_history[-self.max_history_turns:]:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                if role == "user":
                    history_text += f"User: {content}\n"
                elif role == "assistant":
                    history_text += f"Assistant: {content}\n"
                elif role == "tool":
                    history_text += f"Tool result: {content}\n"

        # Combine everything
        full_prompt = f"""{system_prompt}{history_text}

Current user message: {user_message}

Respond with JSON only:"""

        return full_prompt

    def _parse_response(self, raw_response: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Parse LLM response, attempting to extract JSON tool protocol.

        Args:
            raw_response: Raw text response from LLM

        Returns:
            Tuple of (response_type, parsed_data)
            response_type: "answer", "shell", "read_file", "write_file", "search_files", "mcp_tool", or "plain"
            parsed_data: Parsed JSON dict if successful, None otherwise
        """
        raw_response = raw_response.strip()

        # Try to parse the entire response as JSON
        try:
            data = json.loads(raw_response)
            if isinstance(data, dict) and "type" in data:
                return data["type"], data
        except json.JSONDecodeError:
            pass

        # Try to find JSON object within the response
        start_idx = raw_response.find("{")
        end_idx = raw_response.rfind("}")

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = raw_response[start_idx:end_idx + 1]
            try:
                data = json.loads(json_str)
                if isinstance(data, dict) and "type" in data:
                    return data["type"], data
            except json.JSONDecodeError:
                pass

        # If no valid JSON found, treat as plain text answer
        return "plain", {"type": "answer", "text": raw_response}

    def chat(
        self,
        user_message: str,
        routines: Dict[str, Dict[str, str]],
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Send a message to the LLM and get response.

        Args:
            user_message: User's message
            routines: Available routines

        Returns:
            Tuple of (response_type, parsed_data)
        """
        # Add user message to history
        self.conversation_history.append({"role": "user", "content": user_message})

        # Build prompt
        prompt = self._build_conversation_prompt(user_message, routines)

        # Execute Ollama
        raw_response = self.ssh_client.execute_ollama(prompt, self.model)

        # Parse response
        response_type, parsed_data = self._parse_response(raw_response)

        # Add assistant response to history
        if parsed_data:
            if response_type == "answer":
                content = parsed_data.get("text", raw_response)
            elif response_type == "shell":
                target = parsed_data.get("target", "ssh")
                content = f"Proposed command ({target}): {parsed_data.get('command', '')}"
            elif response_type == "read_file":
                content = f"Requested to read file: {parsed_data.get('path', '')}"
            elif response_type == "write_file":
                content = f"Proposed to write file: {parsed_data.get('path', '')}"
            elif response_type == "search_files":
                content = f"Proposed to search files: pattern='{parsed_data.get('search_pattern', '')}', string='{parsed_data.get('search_string', '')}'"
            elif response_type == "mcp_tool":
                content = f"Proposed MCP tool: {parsed_data.get('tool_name', '')} with params: {parsed_data.get('parameters', {})}"
            else:
                content = raw_response
            self.conversation_history.append({"role": "assistant", "content": content})

        return response_type, parsed_data

    def add_tool_result(
        self,
        command: str,
        exit_code: int,
        stdout: str,
        stderr: str,
        target: str = "ssh",
    ) -> None:
        """Add a tool execution result to conversation history.

        Args:
            command: The command that was executed
            exit_code: Exit code from command
            stdout: Standard output
            stderr: Standard error
            target: Execution target ("ssh", "local", or "mcp")
        """
        target_label = {
            "ssh": "remote",
            "local": "local",
            "mcp": "mcp",
        }.get(target, target)
        
        result_text = f"Command ({target_label}): {command}\nExit code: {exit_code}\n"
        if stdout:
            result_text += f"Output:\n{stdout}\n"
        if stderr:
            result_text += f"Error:\n{stderr}\n"

        self.conversation_history.append({"role": "tool", "content": result_text})

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.conversation_history = []

    def read_local_file(self, relative_path: str) -> Optional[str]:
        """Read a local file's content using the context manager.

        Args:
            relative_path: Path relative to the working directory

        Returns:
            File content or None if cannot be read
        """
        if not self._context_manager:
            return None
        
        # Support both old ContextManager and new Session
        if hasattr(self._context_manager, "read_file"):
            return self._context_manager.read_file(relative_path)
        elif hasattr(self._context_manager, "read_file_content"):
            return self._context_manager.read_file_content(relative_path)
        return None

    def add_file_content_to_history(self, path: str, content: str) -> None:
        """Add file content to conversation history as a tool result.

        Args:
            path: The file path that was read
            content: The file content
        """
        result_text = f"File: {path}\nContent:\n{content}"
        self.conversation_history.append({"role": "tool", "content": result_text})

    def add_tool_result_to_history(
        self,
        tool_name: str,
        command_info: str,
        result: str,
    ) -> None:
        """Add a generic tool result to conversation history.

        Args:
            tool_name: The name of the tool (e.g., 'write_file').
            command_info: Information about the command/operation.
            result: The result of the operation.
        """
        result_text = f"Tool: {tool_name}\nOperation: {command_info}\nResult: {result}"
        self.conversation_history.append({"role": "tool", "content": result_text})

    def add_tool_error_to_history(
        self,
        tool_name: str,
        command_info: str,
        error: str,
    ) -> None:
        """Add a tool error or cancellation to conversation history.

        Args:
            tool_name: The name of the tool (e.g., 'write_file').
            command_info: Information about the command/operation.
            error: The error message or cancellation reason.
        """
        result_text = f"Tool: {tool_name}\nOperation: {command_info}\nError: {error}"
        self.conversation_history.append({"role": "tool", "content": result_text})
