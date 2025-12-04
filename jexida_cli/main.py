"""Main entry point for Jexida CLI."""

import os
import json
from rich.console import Console

from .config import Config
from .ssh_client import SSHClient
from .agent import Agent
from .context import ContextManager
from .executor import LocalExecutor, SSHExecutor, MCPExecutor
from .mcp_client import MCPClient
from .ui import UI

console = Console()


def main() -> None:
    """Main entry point - starts the REPL loop."""
    # Load configuration
    config = Config()
    config.load()

    # Initialize context manager for current working directory
    context_manager = ContextManager(
        working_dir=os.getcwd(),
        max_depth=config.context_max_depth,
        exclude_patterns=set(config.context_exclude_patterns),
        max_file_size=config.context_max_file_size,
    )

    # Initialize components
    ssh_client = SSHClient(config.host, config.user)
    mcp_client = MCPClient(config)
    agent = Agent(ssh_client, config.model, mcp_client=mcp_client)
    agent.set_context_manager(context_manager)
    ui = UI()
    
    # Initialize executors
    local_executor = LocalExecutor()
    ssh_executor = SSHExecutor(ssh_client)
    mcp_executor = MCPExecutor(mcp_client)

    try:
        # Auto-load session if enabled and exists
        if config.context_auto_load_session:
            saved_history = context_manager.load_session()
            if saved_history:
                agent.set_conversation_history(saved_history)
                session_info = context_manager.get_session_info()
                if session_info:
                    ui.show_info(
                        f"Resumed session with {session_info['message_count']} messages "
                        f"(last updated: {session_info['last_updated'][:19]})"
                    )

        # Clear screen and show header with directory info
        ui.clear_screen()
        ui.show_header(config.host, config.user, config.model, str(context_manager.working_dir))

        # Main REPL loop
        while True:
            try:
                # Get user input (multi-line support)
                user_input = ui.get_multiline_input().strip()

                if not user_input:
                    continue

                # Handle meta commands
                if user_input.startswith("/"):
                    if user_input == "/exit" or user_input == "/quit":
                        # Save session before exiting
                        if config.context_auto_save_session:
                            context_manager.save_session(agent.conversation_history)
                        console.print("\n[dim]Session closed.[/dim]\n")
                        break

                    elif user_input == "/help":
                        _show_help(ui)
                        continue

                    elif user_input == "/clear":
                        ui.clear_screen()
                        ui.show_header(config.host, config.user, config.model, str(context_manager.working_dir))
                        continue

                    elif user_input == "/context":
                        ui.show_context(context_manager.get_context_summary())
                        continue

                    elif user_input == "/session":
                        session_info = context_manager.get_session_info()
                        if session_info:
                            ui.show_info(
                                f"Session: {session_info['message_count']} messages\n"
                                f"Directory: {session_info['directory']}\n"
                                f"Last updated: {session_info['last_updated']}"
                            )
                        else:
                            ui.show_info("No saved session for this directory.")
                        continue

                    elif user_input == "/session clear":
                        if context_manager.clear_session():
                            agent.clear_history()
                            ui.show_info("Session cleared.")
                        else:
                            ui.show_error("Could not clear session.")
                        continue

                    elif user_input == "/shell":
                        ui.show_info(f"Opening SSH shell to {config.user}@{config.host}...")
                        ui.show_info("Type 'exit' in the SSH session to return to Jexida.")
                        console.print()
                        ssh_executor.open_shell()
                        console.print()
                        # Re-draw status after returning from shell
                        ui.show_status(config.host, config.user, config.model)
                        continue

                    elif user_input.startswith("/cmd "):
                        command = user_input[5:].strip()
                        if not command:
                            ui.show_error("Usage: /cmd <command>")
                            continue
                        _handle_cmd(ui, ssh_client, config, command)
                        continue

                    elif user_input == "/routines":
                        ui.show_routines(config.routines)
                        continue

                    elif user_input.startswith("/run "):
                        routine_name = user_input[5:].strip()
                        if not routine_name:
                            ui.show_error("Usage: /run <routine_name>")
                            continue
                        _handle_run(ui, ssh_client, config, agent, routine_name)
                        continue

                    elif user_input == "/model":
                        _handle_model_list(ui, ssh_client, config, mcp_client)
                        continue

                    elif user_input.startswith("/model "):
                        model_name = user_input[7:].strip()
                        if not model_name:
                            ui.show_error("Usage: /model <model_name> or /model set <strategy_id>")
                            continue
                        _handle_model_switch(ui, ssh_client, config, agent, model_name, mcp_client)
                        continue

                    elif user_input == "/whitelist":
                        ui.show_whitelist(config.get_whitelist_patterns())
                        continue

                    elif user_input.startswith("/whitelist add "):
                        pattern = user_input[15:].strip()
                        if not pattern:
                            ui.show_error("Usage: /whitelist add <pattern>")
                            continue
                        _handle_whitelist_add(ui, config, pattern)
                        continue

                    elif user_input.startswith("/whitelist rm ") or user_input.startswith("/whitelist remove "):
                        if user_input.startswith("/whitelist rm "):
                            pattern = user_input[14:].strip()
                        else:
                            pattern = user_input[18:].strip()
                        if not pattern:
                            ui.show_error("Usage: /whitelist rm <pattern>")
                            continue
                        _handle_whitelist_remove(ui, config, pattern)
                        continue

                    else:
                        ui.show_error(f"Unknown command: {user_input}. Type /help for available commands.")
                        continue

                # Normal chat message
                _handle_chat(
                    ui, agent, config, context_manager,
                    local_executor, ssh_executor, mcp_executor, user_input
                )

                # Auto-save session after each chat
                if config.context_auto_save_session:
                    context_manager.save_session(agent.conversation_history)

            except KeyboardInterrupt:
                console.print("\n\n[dim]Interrupted. Type /exit to quit.[/dim]\n")
                continue
            except EOFError:
                console.print("\n[dim]Session closed.[/dim]\n")
                break
            except Exception as e:
                ui.show_error(f"Unexpected error: {str(e)}")
                console.print_exception()
    finally:
        # Ensure client connections are closed
        mcp_client.close()


def _show_help(ui: UI) -> None:
    """Show help message."""
    help_text = """Available commands:

[bold]/exit[/bold] or [bold]/quit[/bold]        - Exit the application
[bold]/help[/bold]                    - Show this help message
[bold]/clear[/bold]                   - Clear screen and redraw header
[bold]/shell[/bold]                   - Open interactive SSH shell
[bold]/cmd <command>[/bold]           - Run a single remote command
[bold]/routines[/bold]                - List available routines
[bold]/run <routine>[/bold]           - Execute a named routine
[bold]/model[/bold]                   - List available models & strategies
[bold]/model <name>[/bold]            - Switch to a model (e.g., gpt-5-nano)
[bold]/model set <id>[/bold]          - Switch to a strategy (e.g., cascade:local-first)
[bold]/whitelist[/bold]               - Show whitelisted command patterns
[bold]/whitelist add <pattern>[/bold] - Add pattern to whitelist
[bold]/whitelist rm <pattern>[/bold]  - Remove pattern from whitelist
[bold]/context[/bold]                 - Show current directory context summary
[bold]/session[/bold]                 - Show current session info
[bold]/session clear[/bold]           - Clear saved session

Any other input is treated as a chat message to the LLM agent.
The agent has awareness of files in the current directory.

[dim]Model & Strategy Selection:[/dim]
  Models are organized into strategies for unified orchestration.
  Use [bold]/model[/bold] to see available options including:
  - Single models (GPT-5, O-Series, Local models)
  - Auto/Cascade strategies (try cheap first, local first)

[dim]Approval options when a command is proposed:[/dim]
  [y]es     - Run this command once
  [a]lways  - Run and add to whitelist (auto-approve in future)
  [N]o      - Don't run"""
    ui.show_info(help_text)


def _handle_cmd(ui: UI, ssh_client: SSHClient, config: Config, command: str) -> None:
    """Handle /cmd command."""
    ui.show_remote_command(command)
    stdout, stderr, exit_code = ssh_client.execute_command(command)
    ui.show_command_output(stdout, stderr, exit_code)
    ui.show_status(config.host, config.user, config.model, exit_code)


def _handle_run(ui: UI, ssh_client: SSHClient, config: Config, agent: Agent, routine_name: str) -> None:
    """Handle /run command."""
    routine = config.get_routine(routine_name)
    if not routine:
        ui.show_error(f"Routine '{routine_name}' not found. Use /routines to list available routines.")
        return

    cmd = routine.get("cmd")
    if not cmd:
        ui.show_error(f"Routine '{routine_name}' has no command defined.")
        return

    description = routine.get("description", "No description")
    ui.show_info(f"Running routine: [bold]{routine_name}[/bold] - {description}")
    ui.show_remote_command(cmd)

    stdout, stderr, exit_code = ssh_client.execute_command(cmd)
    ui.show_command_output(stdout, stderr, exit_code)
    ui.show_status(config.host, config.user, config.model, exit_code)

    # Add to agent history as a tool result
    agent.add_tool_result(cmd, exit_code, stdout, stderr)


def _handle_model_list(ui: UI, ssh_client: SSHClient, config: Config, mcp_client: MCPClient = None) -> None:
    """Handle /model command - list available models and strategies.
    
    First tries to fetch from MCP server (unified registry), then falls back to local Ollama.
    """
    # Try to get strategies from MCP server first
    if mcp_client:
        strategies_data = mcp_client.get_strategies()
        if strategies_data:
            _show_strategies(ui, strategies_data, mcp_client.current_strategy_id)
            return
    
    # Fallback: Query local Ollama
    ui.show_info("MCP server unavailable. Showing local Ollama models:")
    stdout, stderr, exit_code = ssh_client.execute_command("ollama list --noheader 2>/dev/null | awk '{print $1}'")

    if exit_code != 0 or not stdout.strip():
        stdout, stderr, exit_code = ssh_client.execute_command("ollama list 2>/dev/null | tail -n +2 | awk '{print $1}'")

    if exit_code == 0 and stdout.strip():
        models = [m.strip() for m in stdout.strip().split("\n") if m.strip()]
        ui.show_models(models, config.model)
    else:
        ui.show_error("Could not retrieve models from Ollama. Check if Ollama is running.")
        if stderr:
            ui.show_error(stderr)


def _show_strategies(ui: UI, strategies_data: dict, current_strategy_id: str) -> None:
    """Display strategies grouped by category."""
    strategies = strategies_data.get("strategies", [])
    groups = strategies_data.get("groups", [])
    
    if not strategies:
        ui.show_info("No strategies available.")
        return
    
    # Group strategies
    grouped = {}
    for s in strategies:
        g = s.get("group", "Other")
        if g not in grouped:
            grouped[g] = []
        grouped[g].append(s)
    
    # Build display text
    lines = []
    for group in groups:
        if group not in grouped or not grouped[group]:
            continue
        lines.append(f"\n[bold cyan]{group}[/bold cyan]")
        for s in grouped[group]:
            strategy_id = s.get("id", "")
            name = s.get("display_name", strategy_id)
            strategy_type = s.get("strategy_type", "single")
            
            # Build info tags
            tags = []
            if strategy_type == "cascade":
                tags.append("[yellow]Auto[/yellow]")
            else:
                if s.get("source") == "local":
                    tags.append("[green]Local[/green]")
                tier = s.get("tier", "")
                if tier == "flagship":
                    tags.append("[magenta]Flagship[/magenta]")
                elif tier == "budget":
                    tags.append("[green]Budget[/green]")
                if s.get("supports_temperature"):
                    tags.append("[blue]Temp[/blue]")
                if s.get("supports_tools") is False:
                    tags.append("[red]No Tools[/red]")
            
            tag_str = " ".join(tags)
            if tag_str:
                tag_str = f" ({tag_str})"
            
            # Current indicator
            if strategy_id == current_strategy_id:
                lines.append(f"  [bold green]● {name}[/bold green]{tag_str} [dim](current)[/dim]")
            else:
                lines.append(f"  [dim]○[/dim] {name}{tag_str}")
    
    content = "\n".join(lines)
    from rich.panel import Panel
    from rich import box
    panel = Panel(
        content,
        title="[bold]AVAILABLE MODELS & STRATEGIES[/bold]",
        subtitle=f"[dim]Use /model set <id> to switch[/dim]",
        border_style="dim cyan",
        box=box.ROUNDED,
    )
    ui.console.print(panel)
    ui.console.print()


def _handle_model_switch(ui: UI, ssh_client: SSHClient, config: Config, agent: Agent, model_name: str, mcp_client: MCPClient = None) -> None:
    """Handle /model <name> or /model set <id> command - switch to a different model/strategy.
    
    Supports:
    - Strategy IDs: "single:gpt-5-nano", "cascade:cloud-cheapest-first"
    - Model names for backwards compatibility: "gpt-5-nano", "llama3:latest"
    """
    old_model = config.model
    
    # Handle "set" subcommand
    if model_name.startswith("set "):
        model_name = model_name[4:].strip()
    
    # Try MCP server first for strategy switching
    if mcp_client:
        # If it doesn't look like a strategy ID, try to make it one
        strategy_id = model_name
        if not strategy_id.startswith("single:") and not strategy_id.startswith("cascade:") and not strategy_id.startswith("router:"):
            # Could be a direct model name - try single: prefix
            strategy_id = f"single:{model_name}"
        
        result = mcp_client.set_active_strategy(strategy_id)
        
        if result and result.get("success"):
            strategy_name = result.get("strategy", {}).get("display_name", model_name)
            ui.show_model_changed(old_model, strategy_name)
            
            # Update local config to track the model
            if result.get("model"):
                model_id = result["model"].get("model_id", model_name)
                config.set_model(model_id)
                agent.set_model(model_id)
            return
        elif result and result.get("error"):
            # Try without single: prefix (maybe it's a different format)
            if strategy_id != model_name:
                result2 = mcp_client.set_active_strategy(model_name)
                if result2 and result2.get("success"):
                    strategy_name = result2.get("strategy", {}).get("display_name", model_name)
                    ui.show_model_changed(old_model, strategy_name)
                    return
            
            ui.show_error(f"Failed to switch strategy: {result.get('error')}")
            ui.show_info("Use /model to list available strategies.")
            return
    
    # Fallback: Check local Ollama model
    stdout, stderr, exit_code = ssh_client.execute_command(f"ollama show {model_name} --modelfile 2>/dev/null | head -1")

    if exit_code != 0:
        ui.show_error(f"Model/strategy '{model_name}' not found.")
        ui.show_info("Use /model to list available options, or:")
        ui.show_info(f"  /cmd ollama pull {model_name}")
        return

    # Update config and agent for local model
    config.set_model(model_name)
    agent.set_model(model_name)
    ui.show_model_changed(old_model, model_name)


def _handle_whitelist_add(ui: UI, config: Config, pattern: str) -> None:
    """Handle /whitelist add <pattern> command."""
    config.add_to_whitelist(pattern)
    ui.show_info(f"Added to whitelist: [cyan]{pattern}[/cyan]")


def _handle_whitelist_remove(ui: UI, config: Config, pattern: str) -> None:
    """Handle /whitelist rm <pattern> command."""
    if config.remove_from_whitelist(pattern):
        ui.show_info(f"Removed from whitelist: [cyan]{pattern}[/cyan]")
    else:
        ui.show_error(f"Pattern not in whitelist: [cyan]{pattern}[/cyan]")
        ui.show_info("Use /whitelist to see current patterns.")


def _handle_chat(
    ui: UI,
    agent: Agent,
    config: Config,
    context_manager: ContextManager,
    local_executor: LocalExecutor,
    ssh_executor: SSHExecutor,
    mcp_executor: MCPExecutor,
    user_input: str
) -> None:
    """
    Handle normal chat message.

    Args:
        ui: UI instance for display
        agent: Agent instance for LLM interaction
        config: Configuration instance
        context_manager: Context manager for local files
        local_executor: Executor for local commands
        ssh_executor: Executor for SSH commands
        mcp_executor: Executor for MCP server tools
        user_input: User's chat message
    """
    ui.show_prompt(user_input)

    # Get response from agent
    response_type, parsed_data = agent.chat(user_input, config.routines)

    if response_type == "answer" and parsed_data:
        # Display answer
        text = parsed_data.get("text", "")
        ui.show_answer(text)
        ui.show_status(config.host, config.user, config.model)

    elif response_type == "read_file" and parsed_data:
        # Handle file read request
        file_path = parsed_data.get("path", "")
        reason = parsed_data.get("reason", "")
        
        ui.show_info(f"Agent wants to read file: [cyan]{file_path}[/cyan]\nReason: {reason}")
        
        content = context_manager.read_file_content(file_path)
        if content and not content.startswith("[Error"):
            ui.show_file_content(file_path, content)
            agent.add_file_content_to_history(file_path, content)
        else:
            error_message = content or f"Could not read file: {file_path}"
            ui.show_error(error_message)
            agent.add_tool_error_to_history("read_file", file_path, error_message)

        ui.show_status(config.host, config.user, config.model)

    elif response_type == "write_file" and parsed_data:
        file_path = parsed_data.get("path", "")
        content = parsed_data.get("content", "")
        
        if ui.prompt_write_confirmation(file_path, content):
            success, message = context_manager.write_file_content(file_path, content)
            if success:
                ui.show_info(message)
                agent.add_tool_result_to_history("write_file", f"Wrote to {file_path}", message)
            else:
                ui.show_error(message)
                agent.add_tool_error_to_history("write_file", file_path, message)
        else:
            ui.show_info("File write cancelled by user.")
            agent.add_tool_error_to_history("write_file", file_path, "Cancelled by user")
            
        ui.show_status(config.host, config.user, config.model)

    elif response_type == "search_files" and parsed_data:
        pattern = parsed_data.get("search_pattern", "")
        string = parsed_data.get("search_string", "")
        reason = parsed_data.get("reason", "")

        ui.show_info(f"Agent wants to search files: pattern='{pattern}' string='{string}'\nReason: {reason}")
        
        results = context_manager.search_files(pattern, string)
        ui.show_search_results(results)
        
        result_str = "\n".join(results) if results else "(No matches found)"
        agent.add_tool_result_to_history("search_files", f"pattern='{pattern}', string='{string}'", result_str)
        ui.show_status(config.host, config.user, config.model)

    elif response_type == "mcp_tool" and parsed_data:
        tool_name = parsed_data.get("tool_name", "")
        parameters = parsed_data.get("parameters", {})
        reason = parsed_data.get("reason", "No reason provided")

        ui.show_mcp_plan(tool_name, parameters, reason)

        if ui.confirm("Execute this MCP tool?"):
            command_str = json.dumps({"tool_name": tool_name, "parameters": parameters})
            exit_code, stdout, stderr = mcp_executor.run(command_str)

            ui.show_command_result(exit_code, stdout, stderr, target="mcp")
            ui.show_status(config.host, config.user, config.model, exit_code)
            agent.add_tool_result(command_str, exit_code, stdout, stderr, target="mcp")
        else:
            ui.show_info("MCP tool execution cancelled by user.")
            agent.add_tool_error_to_history("mcp_tool", tool_name, "Cancelled by user")
            ui.show_status(config.host, config.user, config.model)

    elif response_type == "shell" and parsed_data:
        command = parsed_data.get("command", "")
        reason = parsed_data.get("reason", "No reason provided")
        target = parsed_data.get("target", "ssh")

        is_whitelisted = config.is_whitelisted(command)
        ui.show_shell_plan(command, reason, is_whitelisted=is_whitelisted, target=target)

        should_run = False
        add_to_whitelist = False

        if is_whitelisted:
            should_run = True
        else:
            approval = ui.prompt_approval(config.host, config.user, target=target)
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
            
            ui.show_command_result(exit_code, stdout, stderr, target=target)
            ui.show_status(config.host, config.user, config.model, exit_code)
            agent.add_tool_result(command, exit_code, stdout, stderr, target=target)

            if add_to_whitelist:
                config.add_to_whitelist(command)
                ui.show_info(f"Added to whitelist: [cyan]{command}[/cyan]")
        else:
            ui.show_info("Command not executed.")
            agent.add_tool_error_to_history("shell", command, "Cancelled by user")
            ui.show_status(config.host, config.user, config.model)

    else:
        # Fallback: treat as plain answer
        if parsed_data and "text" in parsed_data:
            ui.show_answer(parsed_data["text"])
        else:
            ui.show_answer("(No response)")
        ui.show_status(config.host, config.user, config.model)


if __name__ == "__main__":
    main()

