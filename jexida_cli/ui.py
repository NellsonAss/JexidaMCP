"""Rich terminal UI components for Jexida CLI."""

from typing import Optional
from prompt_toolkit import prompt
from prompt_toolkit.formatted_text import HTML

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box


class UI:
    """Handles terminal UI rendering using Rich."""

    def __init__(self):
        """Initialize UI with Rich console."""
        self.console = Console()

    def show_header(self, host: str, user: str, model: str, working_dir: str = "") -> None:
        """
        Display the Jexida header.

        Args:
            host: SSH host
            user: SSH user
            model: Ollama model name
            working_dir: Current working directory (optional)
        """
        header_text = Text()
        header_text.append("JEXIDA", style="bold bright_cyan")
        header_text.append(" // MCP TERMINAL", style="dim cyan")

        info_lines = [
            f"host  : {host}",
            f"user  : {user}",
            f"model : {model}",
        ]
        
        if working_dir:
            # Truncate long paths
            display_dir = working_dir
            if len(display_dir) > 50:
                display_dir = "..." + display_dir[-47:]
            info_lines.append(f"dir   : {display_dir}")
        
        info_lines.extend([
            "",
            "commands: /exit  /help  /shell  /cmd  /model  /context  /session",
        ])

        info_text = "\n".join(info_lines)

        panel = Panel(
            info_text,
            title=header_text,
            border_style="dim cyan",
            box=box.ROUNDED,
        )

        self.console.print(panel)
        self.console.print()

    def show_prompt(self, user_input: str) -> None:
        """
        Display user's prompt in a panel.

        Args:
            user_input: User's input text
        """
        panel = Panel(
            user_input,
            title="[bold]PROMPT[/bold]",
            border_style="dim cyan",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()

    def show_answer(self, text: str) -> None:
        """
        Display LLM answer in a panel.

        Args:
            text: Answer text
        """
        panel = Panel(
            text,
            title="[bold bright_cyan]AGENT RESPONSE[/bold bright_cyan]",
            border_style="dim cyan",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()

    def show_shell_plan(
        self, command: str, reason: str, is_whitelisted: bool = False, target: str = "ssh"
    ) -> None:
        """
        Display proposed shell command in a plan panel.

        Args:
            command: The shell command
            reason: Explanation for the command
            is_whitelisted: Whether the command matches a whitelist pattern
            target: Execution target ("ssh" for remote, "local" for local machine)
        """
        if target == "ssh":
            target_label = "[cyan]REMOTE (SSH)[/cyan]"
        else:
            target_label = "[magenta]LOCAL[/magenta]"
        
        content = f"[bold]Target:[/bold] {target_label}\n\n[bold]Command:[/bold]\n{command}\n\n[bold]Reason:[/bold]\n{reason}"

        if is_whitelisted:
            content += "\n\n[bold green]✓ WHITELISTED[/bold green] - auto-executing"
            title = "[bold green]PLAN (WHITELISTED)[/bold green]"
            border_style = "green"
        else:
            title = "[bold yellow]PLAN[/bold yellow]"
            border_style = "yellow"

        panel = Panel(
            content,
            title=title,
            border_style=border_style,
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()

    def show_mcp_plan(self, tool_name: str, parameters: dict, reason: str) -> None:
        """
        Display proposed MCP tool execution in a plan panel.

        Args:
            tool_name: The name of the MCP tool.
            parameters: The parameters for the tool.
            reason: The agent's reason for running the tool.
        """
        import json
        params_str = json.dumps(parameters, indent=2)
        panel_content = (
            "[bold]Target:[/bold] [bold blue]MCP SERVER[/bold blue]\n\n"
            f"[bold]Tool:[/bold] [cyan]{tool_name}[/cyan]\n\n"
            f"[bold]Parameters:[/bold]\n{params_str}\n\n"
            f"[bold]Reason:[/bold]\n{reason}"
        )
        
        panel = Panel(
            panel_content,
            title="[bold yellow]PLAN[/bold yellow]",
            border_style="yellow",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()

    def show_proposed_command(
        self, command: str, reason: str, target: str = "ssh"
    ) -> None:
        """
        Display a proposed command from the agent (alias for show_plan without whitelist).

        Args:
            command: The shell command
            reason: Explanation for the command
            target: Execution target ("ssh" or "local")
        """
        self.show_shell_plan(command, reason, is_whitelisted=False, target=target)

    def confirm(self, message: str) -> bool:
        """
        Prompt user for yes/no confirmation using prompt_toolkit.

        Args:
            message: Confirmation prompt message

        Returns:
            True if user confirms, False otherwise
        """
        # prompt_toolkit doesn't render rich markup, so we use plain text.
        full_message = f"{message} [y/N]: "
        response = prompt(full_message).strip().lower()
        return response in ("y", "yes")

    def show_command_result(
        self, exit_code: int, stdout: str, stderr: str, target: str = "ssh"
    ) -> None:
        """
        Display command execution result with target information.

        Args:
            exit_code: Exit code from command
            stdout: Standard output
            stderr: Standard error
            target: Execution target ("ssh", "local", or "mcp")
        """
        if target == "ssh":
            target_label = "REMOTE"
        elif target == "local":
            target_label = "LOCAL"
        elif target == "mcp":
            target_label = "MCP TOOL"
        else:
            target_label = target.upper()

        content_parts = []
        
        if stdout:
            content_parts.append(f"[bold]Output:[/bold]\n{stdout}")
        if stderr:
            content_parts.append(f"[bold red]Error:[/bold red]\n{stderr}")
        if exit_code != 0:
            content_parts.append(f"[bold red]Exit code: {exit_code}[/bold red]")

        content = "\n\n".join(content_parts) if content_parts else "[dim](No output)[/dim]"

        status_style = "green" if exit_code == 0 else "red"
        panel = Panel(
            content,
            title=f"[bold {status_style}]{target_label} COMMAND RESULT[/bold {status_style}]",
            border_style=status_style,
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()

    def show_command_output(self, stdout: str, stderr: str, exit_code: int) -> None:
        """
        Display command execution output.

        Args:
            stdout: Standard output
            stderr: Standard error
            exit_code: Exit code
        """
        content_parts = []
        if stdout:
            content_parts.append(f"[bold]Output:[/bold]\n{stdout}")
        if stderr:
            content_parts.append(f"[bold red]Error:[/bold red]\n{stderr}")
        if exit_code != 0:
            content_parts.append(f"[bold red]Exit code: {exit_code}[/bold red]")

        content = "\n\n".join(content_parts) if content_parts else "[dim](No output)[/dim]"

        status_style = "green" if exit_code == 0 else "red"
        panel = Panel(
            content,
            title=f"[bold {status_style}]COMMAND OUTPUT[/bold {status_style}]",
            border_style=status_style,
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()

    def show_remote_command(self, command: str) -> None:
        """
        Display a remote command being executed.

        Args:
            command: The command
        """
        panel = Panel(
            command,
            title="[bold]REMOTE COMMAND[/bold]",
            border_style="dim cyan",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()

    def show_status(self, host: str, user: str, model: str, exit_code: Optional[int] = None) -> None:
        """
        Display status information.

        Args:
            host: SSH host
            user: SSH user
            model: Ollama model
            exit_code: Optional exit code
        """
        lines = [f"host  : {host}", f"user  : {user}", f"model : {model}"]
        if exit_code is not None:
            status_color = "green" if exit_code == 0 else "red"
            lines.append(f"code  : [{status_color}]{exit_code}[/{status_color}]")

        content = "\n".join(lines)
        panel = Panel(
            content,
            title="[bold]STATUS[/bold]",
            border_style="dim cyan",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()

    def show_routines(self, routines: dict) -> None:
        """
        Display available routines.

        Args:
            routines: Routines dictionary
        """
        if not routines:
            content = "[dim](No routines configured)[/dim]"
        else:
            lines = []
            for name, routine in routines.items():
                desc = routine.get("description", "No description")
                lines.append(f"[bold]{name}[/bold] - {desc}")
            content = "\n".join(lines)

        panel = Panel(
            content,
            title="[bold]ROUTINES[/bold]",
            border_style="dim cyan",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()

    def show_context(self, context_summary: str) -> None:
        """
        Display current directory context summary.

        Args:
            context_summary: Context summary text
        """
        panel = Panel(
            context_summary,
            title="[bold]DIRECTORY CONTEXT[/bold]",
            border_style="dim cyan",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()

    def show_file_content(self, file_path: str, content: str) -> None:
        """
        Display file content in a panel.

        Args:
            file_path: Path to the file
            content: File content
        """
        # Truncate very long content
        if len(content) > 5000:
            content = content[:5000] + "\n\n[dim]... (truncated)[/dim]"
        
        panel = Panel(
            content,
            title=f"[bold]FILE: {file_path}[/bold]",
            border_style="dim green",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()

    def show_search_results(self, results: list[str]) -> None:
        """
        Display search results in a panel.

        Args:
            results: List of result strings (e.g., 'path:line:content')
        """
        if not results:
            content = "[dim](No matches found)[/dim]"
        else:
            content = "\n".join(results)
        
        panel = Panel(
            content,
            title="[bold blue]SEARCH RESULTS[/bold blue]",
            border_style="blue",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()

    def show_whitelist(self, patterns: list) -> None:
        """
        Display whitelist patterns.

        Args:
            patterns: List of whitelist patterns
        """
        if not patterns:
            content = "[dim](No patterns whitelisted)[/dim]\n\n"
            content += "Use [bold]/whitelist add <pattern>[/bold] to add patterns.\n"
            content += "Patterns can be:\n"
            content += "  - Exact: [cyan]ls[/cyan] (matches only 'ls')\n"
            content += "  - Glob: [cyan]cat *[/cyan] (matches 'cat foo.txt')\n"
            content += "  - Regex: [cyan]~docker.*[/cyan] (matches 'docker ps', 'docker run')"
        else:
            lines = []
            for pattern in patterns:
                if pattern.startswith("~"):
                    pattern_type = "[magenta]regex[/magenta]"
                elif "*" in pattern or "?" in pattern:
                    pattern_type = "[yellow]glob[/yellow]"
                else:
                    pattern_type = "[green]exact[/green]"
                lines.append(f"  [cyan]{pattern}[/cyan] ({pattern_type})")
            content = "\n".join(lines)

        panel = Panel(
            content,
            title="[bold]WHITELIST[/bold]",
            border_style="dim cyan",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()

    def show_models(self, models: list, current_model: str) -> None:
        """
        Display available models.

        Args:
            models: List of model names
            current_model: Currently active model
        """
        if not models:
            content = "[dim](Could not retrieve models)[/dim]"
        else:
            lines = []
            for model in models:
                if model == current_model:
                    lines.append(f"  [bold green]● {model}[/bold green] (current)")
                else:
                    lines.append(f"  [dim]○[/dim] {model}")
            content = "\n".join(lines)

        panel = Panel(
            content,
            title="[bold]AVAILABLE MODELS[/bold]",
            border_style="dim cyan",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()

    def show_model_changed(self, old_model: str, new_model: str) -> None:
        """
        Display model change confirmation.

        Args:
            old_model: Previous model name
            new_model: New model name
        """
        content = f"Model changed: [dim]{old_model}[/dim] → [bold green]{new_model}[/bold green]"
        panel = Panel(
            content,
            title="[bold]MODEL SWITCHED[/bold]",
            border_style="green",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()

    def show_error(self, message: str) -> None:
        """
        Display an error message.

        Args:
            message: Error message
        """
        panel = Panel(
            message,
            title="[bold red]ERROR[/bold red]",
            border_style="red",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()

    def show_info(self, message: str) -> None:
        """
        Display an info message.

        Args:
            message: Info message
        """
        panel = Panel(
            message,
            title="[bold blue]INFO[/bold blue]",
            border_style="blue",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()

    def clear_screen(self) -> None:
        """Clear the terminal screen."""
        self.console.clear()

    def prompt_confirm(self, message: str) -> bool:
        """
        Prompt user for yes/no confirmation.

        Args:
            message: Confirmation prompt

        Returns:
            True if user confirms, False otherwise
        """
        response = self.console.input(f"[yellow]{message}[/yellow] ").strip().lower()
        return response in ("y", "yes")

    def prompt_approval(self, host: str, user: str, target: str = "ssh") -> str:
        """
        Prompt user for command approval with whitelist option using prompt_toolkit.

        Args:
            host: SSH host
            user: SSH user
            target: Execution target ("ssh" or "local")

        Returns:
            One of: "yes", "always", "no"
        """
        if target == "local":
            message = "Run locally? [y]es / [a]lways / [N]o: "
        else:
            message = f"Run on {user}@{host}? [y]es / [a]lways / [N]o: "
        
        response = prompt(message).strip().lower()

        if response in ("y", "yes"):
            return "yes"
        elif response in ("a", "always"):
            return "always"
        else:
            return "no"

    def prompt_write_confirmation(self, file_path: str, content: str) -> bool:
        """
        Prompt user for file write confirmation with a content preview.

        Args:
            file_path: The relative path to the file.
            content: The content to be written.

        Returns:
            True if the user confirms, False otherwise.
        """
        preview_content = content
        if len(preview_content) > 500:
            preview_content = preview_content[:500] + "\n\n[dim]... (content truncated)[/dim]"

        panel_content = f"[bold]File Path:[/bold] [cyan]{file_path}[/cyan]\n\n[bold]Content to Write:[/bold]\n{preview_content}"
        
        panel = Panel(
            panel_content,
            title="[bold yellow]PROPOSED FILE WRITE[/bold yellow]",
            border_style="yellow",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        
        message = "\nWrite to this local file? [y/N]: "
        response = prompt(message).strip().lower()
        self.console.print()
        return response in ("y", "yes")

    def get_multiline_input(self, prompt_message: str = "JEXIDA> ") -> str:
        """
        Get multi-line input from user using a prompt_toolkit box.

        Args:
            prompt_message: The prompt to display.

        Returns:
            The complete multi-line input as a string.
        """
        # Use a simple string for the prompt to avoid potential styling conflicts.
        # The prompt_toolkit session can be customized more deeply if needed.
        
        # Instructions for the user are displayed on the right side of the prompt.
        rprompt_text = "Press [Esc] then [Enter] to submit."

        try:
            # multiline=True enables the multi-line "box" mode.
            text_input = prompt(
                prompt_message,
                multiline=True,
                rprompt=rprompt_text,
            )
        except EOFError:
            return "" # Handle Ctrl+D gracefully
        except KeyboardInterrupt:
            self.console.print() # Move to the next line after Ctrl+C
            return "" # Return empty string to avoid processing incomplete input
            
        self.console.print() # Add a newline for better spacing
        return text_input

