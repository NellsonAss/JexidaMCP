"""Frame-based UI components for structured terminal output."""

from typing import Optional, List, Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from rich.syntax import Syntax

from .colors import Colors, Theme


class Frame:
    """Provides frame-based terminal output with consistent styling."""
    
    def __init__(self, console: Optional[Console] = None):
        """Initialize the frame renderer.
        
        Args:
            console: Rich console instance (creates new if not provided)
        """
        self.console = console or Console()
        self.theme = Colors.get_theme()
    
    def header(
        self,
        host: str,
        user: str,
        model: str,
        working_dir: str = "",
        mode: str = "direct",
    ) -> None:
        """Display the main application header.
        
        Args:
            host: SSH host address
            user: SSH username
            model: Current model/strategy name
            working_dir: Current working directory
            mode: Model mode (direct, cascade, route, orchestrate)
        """
        title = Text()
        title.append("JEXIDA", style="bold bright_cyan")
        title.append(" // MCP TERMINAL", style="dim cyan")
        
        # Build info table for better alignment
        info_table = Table.grid(padding=(0, 2))
        info_table.add_column(style="dim", width=8)
        info_table.add_column()
        
        info_table.add_row("HOST", f"[cyan]{host}[/cyan]")
        info_table.add_row("USER", f"[cyan]{user}[/cyan]")
        info_table.add_row("MODEL", f"[bright_cyan]{model}[/bright_cyan]")
        
        if mode != "direct":
            mode_style = "yellow" if mode == "cascade" else "magenta"
            info_table.add_row("MODE", f"[{mode_style}]{mode.upper()}[/{mode_style}]")
        
        if working_dir:
            display_dir = working_dir
            if len(display_dir) > 45:
                display_dir = "..." + display_dir[-42:]
            info_table.add_row("DIR", f"[dim]{display_dir}[/dim]")
        
        panel = Panel(
            info_table,
            title=title,
            subtitle="[dim]/help for commands[/dim]",
            border_style="dim cyan",
            box=box.ROUNDED,
            padding=(0, 1),
        )
        self.console.print(panel)
        self.console.print()
    
    def status_bar(
        self,
        host: str,
        user: str,
        model: str,
        exit_code: Optional[int] = None,
    ) -> None:
        """Display a compact status bar.
        
        Args:
            host: SSH host
            user: SSH username
            model: Current model
            exit_code: Optional last command exit code
        """
        parts = [
            f"[dim]host:[/dim] [cyan]{host}[/cyan]",
            f"[dim]user:[/dim] [cyan]{user}[/cyan]",
            f"[dim]model:[/dim] [bright_cyan]{model}[/bright_cyan]",
        ]
        
        if exit_code is not None:
            color = "green" if exit_code == 0 else "red"
            parts.append(f"[dim]code:[/dim] [{color}]{exit_code}[/{color}]")
        
        status_text = "  │  ".join(parts)
        
        panel = Panel(
            status_text,
            border_style="dim cyan",
            box=box.ROUNDED,
            padding=(0, 1),
        )
        self.console.print(panel)
        self.console.print()
    
    def user_prompt(self, text: str) -> None:
        """Display the user's prompt/input.
        
        Args:
            text: User's input text
        """
        panel = Panel(
            text,
            title="[bold]PROMPT[/bold]",
            border_style="dim white",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()
    
    def agent_response(self, text: str) -> None:
        """Display an agent response.
        
        Args:
            text: Response text from the agent
        """
        panel = Panel(
            text,
            title="[bold bright_cyan]RESPONSE[/bold bright_cyan]",
            border_style="cyan",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()
    
    def plan(
        self,
        command: str,
        reason: str,
        target: str = "ssh",
        is_whitelisted: bool = False,
    ) -> None:
        """Display a proposed command plan.
        
        Args:
            command: The proposed command
            reason: Explanation for the command
            target: Target environment (ssh, local, mcp)
            is_whitelisted: Whether command is auto-approved
        """
        target_labels = {
            "ssh": "[cyan]REMOTE (SSH)[/cyan]",
            "local": "[magenta]LOCAL[/magenta]",
            "mcp": "[blue]MCP SERVER[/blue]",
        }
        target_label = target_labels.get(target, target.upper())
        
        content = f"[bold]Target:[/bold] {target_label}\n\n"
        content += f"[bold]Command:[/bold]\n[white]{command}[/white]\n\n"
        content += f"[bold]Reason:[/bold]\n{reason}"
        
        if is_whitelisted:
            content += "\n\n[bold green]✓ WHITELISTED[/bold green] - auto-executing"
            title = "[bold green]PLAN (WHITELISTED)[/bold green]"
            border = "green"
        else:
            title = "[bold yellow]PLAN[/bold yellow]"
            border = "yellow"
        
        panel = Panel(
            content,
            title=title,
            border_style=border,
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()
    
    def mcp_plan(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        reason: str,
    ) -> None:
        """Display a proposed MCP tool execution.
        
        Args:
            tool_name: Name of the MCP tool
            parameters: Tool parameters
            reason: Explanation for the action
        """
        import json
        params_str = json.dumps(parameters, indent=2)
        
        content = "[bold]Target:[/bold] [bold blue]MCP SERVER[/bold blue]\n\n"
        content += f"[bold]Tool:[/bold] [cyan]{tool_name}[/cyan]\n\n"
        content += f"[bold]Parameters:[/bold]\n{params_str}\n\n"
        content += f"[bold]Reason:[/bold]\n{reason}"
        
        panel = Panel(
            content,
            title="[bold yellow]MCP TOOL PLAN[/bold yellow]",
            border_style="yellow",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()
    
    def result(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
        target: str = "ssh",
    ) -> None:
        """Display command execution result.
        
        Args:
            stdout: Standard output
            stderr: Standard error
            exit_code: Exit code
            target: Target environment
        """
        target_labels = {
            "ssh": "REMOTE",
            "local": "LOCAL",
            "mcp": "MCP TOOL",
        }
        target_label = target_labels.get(target, target.upper())
        
        parts = []
        if stdout:
            parts.append(f"[bold]Output:[/bold]\n{stdout}")
        if stderr:
            parts.append(f"[bold red]Error:[/bold red]\n{stderr}")
        if exit_code != 0:
            parts.append(f"[bold red]Exit code: {exit_code}[/bold red]")
        
        content = "\n\n".join(parts) if parts else "[dim](No output)[/dim]"
        
        is_success = exit_code == 0
        border = "green" if is_success else "red"
        title_style = f"bold {border}"
        
        panel = Panel(
            content,
            title=f"[{title_style}]{target_label} RESULT[/{title_style}]",
            border_style=border,
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()
    
    def info(self, message: str, title: str = "INFO") -> None:
        """Display an info message.
        
        Args:
            message: Info message content
            title: Panel title
        """
        panel = Panel(
            message,
            title=f"[bold blue]{title}[/bold blue]",
            border_style="blue",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()
    
    def success(self, message: str, title: str = "SUCCESS") -> None:
        """Display a success message.
        
        Args:
            message: Success message content
            title: Panel title
        """
        panel = Panel(
            message,
            title=f"[bold green]{title}[/bold green]",
            border_style="green",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()
    
    def warning(self, message: str, title: str = "WARNING") -> None:
        """Display a warning message.
        
        Args:
            message: Warning message content
            title: Panel title
        """
        panel = Panel(
            message,
            title=f"[bold yellow]{title}[/bold yellow]",
            border_style="yellow",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()
    
    def error(self, message: str, title: str = "ERROR") -> None:
        """Display an error message.
        
        Args:
            message: Error message content
            title: Panel title
        """
        panel = Panel(
            message,
            title=f"[bold red]{title}[/bold red]",
            border_style="red",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()
    
    def file_content(self, path: str, content: str) -> None:
        """Display file content with optional syntax highlighting.
        
        Args:
            path: File path
            content: File content
        """
        # Truncate very long content
        if len(content) > 5000:
            content = content[:5000] + "\n\n[dim]... (truncated)[/dim]"
        
        # Try to apply syntax highlighting based on extension
        ext = path.rsplit(".", 1)[-1] if "." in path else ""
        syntax_map = {
            "py": "python",
            "js": "javascript",
            "ts": "typescript",
            "json": "json",
            "yaml": "yaml",
            "yml": "yaml",
            "toml": "toml",
            "md": "markdown",
            "sh": "bash",
            "bash": "bash",
        }
        
        if ext in syntax_map:
            try:
                syntax = Syntax(content, syntax_map[ext], theme="monokai", line_numbers=True)
                panel = Panel(
                    syntax,
                    title=f"[bold]FILE: {path}[/bold]",
                    border_style="dim green",
                    box=box.ROUNDED,
                )
            except Exception:
                panel = Panel(
                    content,
                    title=f"[bold]FILE: {path}[/bold]",
                    border_style="dim green",
                    box=box.ROUNDED,
                )
        else:
            panel = Panel(
                content,
                title=f"[bold]FILE: {path}[/bold]",
                border_style="dim green",
                box=box.ROUNDED,
            )
        
        self.console.print(panel)
        self.console.print()
    
    def divider(self, text: str = "") -> None:
        """Display a visual divider.
        
        Args:
            text: Optional text in the divider
        """
        if text:
            self.console.rule(f"[dim]{text}[/dim]", style="dim cyan")
        else:
            self.console.rule(style="dim cyan")
        self.console.print()
    
    def clear(self) -> None:
        """Clear the terminal screen."""
        self.console.clear()

