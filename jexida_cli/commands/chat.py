"""Chat message handling for Jexida CLI."""

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..ui.renderer import Renderer
    from ..state.config import Config
    from ..state.session import Session
    from ..agent import Agent
    from ..executor import LocalExecutor, SSHExecutor, MCPExecutor


def handle_chat(
    renderer: "Renderer",
    config: "Config",
    session: "Session",
    agent: "Agent",
    local_executor: "LocalExecutor",
    ssh_executor: "SSHExecutor",
    mcp_executor: "MCPExecutor",
    user_input: str,
) -> None:
    """Handle a chat message from the user.
    
    Args:
        renderer: UI renderer instance
        config: Configuration instance
        session: Session manager instance
        agent: LLM agent instance
        local_executor: Local command executor
        ssh_executor: SSH command executor
        mcp_executor: MCP tool executor
        user_input: User's chat message
    """
    renderer.user_prompt(user_input)
    
    # Get response from agent
    response_type, parsed_data = agent.chat(user_input, config.routines)
    
    if response_type == "answer" and parsed_data:
        _handle_answer(renderer, config, parsed_data)
    
    elif response_type == "read_file" and parsed_data:
        _handle_read_file(renderer, config, session, agent, parsed_data)
    
    elif response_type == "write_file" and parsed_data:
        _handle_write_file(renderer, config, session, agent, parsed_data)
    
    elif response_type == "search_files" and parsed_data:
        _handle_search_files(renderer, config, session, agent, parsed_data)
    
    elif response_type == "mcp_tool" and parsed_data:
        _handle_mcp_tool(renderer, config, agent, mcp_executor, parsed_data)
    
    elif response_type == "shell" and parsed_data:
        _handle_shell(
            renderer, config, agent,
            local_executor, ssh_executor,
            parsed_data,
        )
    
    else:
        # Fallback: treat as plain answer
        text = parsed_data.get("text", "(No response)") if parsed_data else "(No response)"
        renderer.agent_response(text)
        renderer.status_bar(config.host, config.user, config.model)


def _handle_answer(
    renderer: "Renderer",
    config: "Config",
    data: dict,
) -> None:
    """Handle an answer response from the agent."""
    text = data.get("text", "")
    renderer.agent_response(text)
    renderer.status_bar(config.host, config.user, config.model)


def _handle_read_file(
    renderer: "Renderer",
    config: "Config",
    session: "Session",
    agent: "Agent",
    data: dict,
) -> None:
    """Handle a file read request from the agent."""
    file_path = data.get("path", "")
    reason = data.get("reason", "")
    
    renderer.info(
        f"Reading file: [cyan]{file_path}[/cyan]\n\nReason: {reason}",
        title="FILE READ"
    )
    
    content = session.read_file(file_path)
    if content and not content.startswith("[Error"):
        renderer.file_content(file_path, content)
        agent.add_file_content_to_history(file_path, content)
    else:
        error_msg = content or f"Could not read file: {file_path}"
        renderer.error(error_msg)
        agent.add_tool_error_to_history("read_file", file_path, error_msg)
    
    renderer.status_bar(config.host, config.user, config.model)


def _handle_write_file(
    renderer: "Renderer",
    config: "Config",
    session: "Session",
    agent: "Agent",
    data: dict,
) -> None:
    """Handle a file write request from the agent."""
    file_path = data.get("path", "")
    content = data.get("content", "")
    
    if renderer.prompt_file_write(file_path, content):
        success, message = session.write_file(file_path, content)
        if success:
            renderer.success(message)
            agent.add_tool_result_to_history("write_file", f"Wrote to {file_path}", message)
        else:
            renderer.error(message)
            agent.add_tool_error_to_history("write_file", file_path, message)
    else:
        renderer.info("File write cancelled by user.")
        agent.add_tool_error_to_history("write_file", file_path, "Cancelled by user")
    
    renderer.status_bar(config.host, config.user, config.model)


def _handle_search_files(
    renderer: "Renderer",
    config: "Config",
    session: "Session",
    agent: "Agent",
    data: dict,
) -> None:
    """Handle a file search request from the agent."""
    pattern = data.get("search_pattern", "")
    search_string = data.get("search_string", "")
    reason = data.get("reason", "")
    
    renderer.info(
        f"Searching files: pattern='{pattern}' string='{search_string}'\n\nReason: {reason}",
        title="FILE SEARCH"
    )
    
    results = session.search_files(pattern, search_string)
    renderer.show_search_results(results)
    
    result_str = "\n".join(results) if results else "(No matches found)"
    agent.add_tool_result_to_history(
        "search_files",
        f"pattern='{pattern}', string='{search_string}'",
        result_str,
    )
    
    renderer.status_bar(config.host, config.user, config.model)


def _handle_mcp_tool(
    renderer: "Renderer",
    config: "Config",
    agent: "Agent",
    mcp_executor: "MCPExecutor",
    data: dict,
) -> None:
    """Handle an MCP tool execution request from the agent."""
    tool_name = data.get("tool_name", "")
    parameters = data.get("parameters", {})
    reason = data.get("reason", "No reason provided")
    
    renderer.mcp_plan(tool_name, parameters, reason)
    
    if renderer.confirm("Execute this MCP tool?"):
        command_str = json.dumps({"tool_name": tool_name, "parameters": parameters})
        exit_code, stdout, stderr = mcp_executor.run(command_str)
        
        renderer.result(stdout, stderr, exit_code, target="mcp")
        renderer.status_bar(config.host, config.user, config.model, exit_code)
        agent.add_tool_result(command_str, exit_code, stdout, stderr, target="mcp")
    else:
        renderer.info("MCP tool execution cancelled by user.")
        agent.add_tool_error_to_history("mcp_tool", tool_name, "Cancelled by user")
        renderer.status_bar(config.host, config.user, config.model)


def _handle_shell(
    renderer: "Renderer",
    config: "Config",
    agent: "Agent",
    local_executor: "LocalExecutor",
    ssh_executor: "SSHExecutor",
    data: dict,
) -> None:
    """Handle a shell command request from the agent."""
    command = data.get("command", "")
    reason = data.get("reason", "No reason provided")
    target = data.get("target", "ssh")
    
    is_whitelisted = config.is_whitelisted(command)
    renderer.plan(command, reason, target=target, is_whitelisted=is_whitelisted)
    
    should_run = False
    add_to_whitelist = False
    
    if is_whitelisted:
        should_run = True
    else:
        approval = renderer.prompt_approval(config.host, config.user, target=target)
        if approval == "yes":
            should_run = True
        elif approval == "always":
            should_run = True
            add_to_whitelist = True
    
    if should_run:
        if target == "local":
            exit_code, stdout, stderr = local_executor.run(command)
        else:
            exit_code, stdout, stderr = ssh_executor.run(command)
        
        renderer.result(stdout, stderr, exit_code, target=target)
        renderer.status_bar(config.host, config.user, config.model, exit_code)
        agent.add_tool_result(command, exit_code, stdout, stderr, target=target)
        
        if add_to_whitelist:
            config.add_to_whitelist(command)
            renderer.success(f"Added to whitelist: [cyan]{command}[/cyan]")
    else:
        renderer.info("Command not executed.")
        agent.add_tool_error_to_history("shell", command, "Cancelled by user")
        renderer.status_bar(config.host, config.user, config.model)

