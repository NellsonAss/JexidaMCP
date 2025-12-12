"""High-level UI renderer that combines Frame with input handling."""

from typing import Optional, List, Dict, Any
from prompt_toolkit import prompt
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from .frame import Frame
from .colors import Colors


class Renderer:
    """High-level UI renderer combining output and input."""
    
    def __init__(self, console: Optional[Console] = None):
        """Initialize the renderer.
        
        Args:
            console: Rich console instance
        """
        self.console = console or Console()
        self.frame = Frame(self.console)
    
    # -------------------------------------------------------------------------
    # Input Methods
    # -------------------------------------------------------------------------
    
    def get_input(self, prompt_text: str = "JEXIDA> ") -> str:
        """Get single-line input from user.
        
        Args:
            prompt_text: Prompt to display
            
        Returns:
            User input string
        """
        try:
            return prompt(prompt_text).strip()
        except (EOFError, KeyboardInterrupt):
            return ""
    
    def get_multiline_input(self, prompt_text: str = "JEXIDA> ") -> str:
        """Get multi-line input from user.
        
        Args:
            prompt_text: Prompt to display
            
        Returns:
            Complete multi-line input
        """
        try:
            text = prompt(
                prompt_text,
                multiline=True,
                rprompt="[Esc]+[Enter] to submit",
            )
            self.console.print()
            return text
        except (EOFError, KeyboardInterrupt):
            self.console.print()
            return ""
    
    def confirm(self, message: str, default: bool = False) -> bool:
        """Prompt for yes/no confirmation.
        
        Args:
            message: Confirmation message
            default: Default value if empty response
            
        Returns:
            True if confirmed, False otherwise
        """
        suffix = "[Y/n]" if default else "[y/N]"
        full_message = f"{message} {suffix}: "
        
        try:
            response = prompt(full_message).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        
        if not response:
            return default
        return response in ("y", "yes")
    
    def prompt_approval(
        self,
        host: str,
        user: str,
        target: str = "ssh",
    ) -> str:
        """Prompt for command approval with whitelist option.
        
        Args:
            host: SSH host
            user: SSH user
            target: Execution target
            
        Returns:
            One of: "yes", "always", "no"
        """
        if target == "local":
            message = "Run locally? [y]es / [a]lways / [N]o: "
        else:
            message = f"Run on {user}@{host}? [y]es / [a]lways / [N]o: "
        
        try:
            response = prompt(message).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "no"
        
        if response in ("y", "yes"):
            return "yes"
        elif response in ("a", "always"):
            return "always"
        return "no"
    
    def prompt_file_write(self, path: str, content: str) -> bool:
        """Prompt for file write confirmation with preview.
        
        Args:
            path: File path
            content: Content to write
            
        Returns:
            True if confirmed
        """
        preview = content[:500]
        if len(content) > 500:
            preview += "\n\n[dim]... (content truncated)[/dim]"
        
        panel_content = f"[bold]Path:[/bold] [cyan]{path}[/cyan]\n\n"
        panel_content += f"[bold]Content:[/bold]\n{preview}"
        
        panel = Panel(
            panel_content,
            title="[bold yellow]PROPOSED FILE WRITE[/bold yellow]",
            border_style="yellow",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        
        return self.confirm("Write to this file?")
    
    # -------------------------------------------------------------------------
    # List Display Methods
    # -------------------------------------------------------------------------
    
    def show_models(
        self,
        strategies: List[Dict[str, Any]],
        groups: List[str],
        current_id: Optional[str] = None,
    ) -> None:
        """Display available models and strategies.
        
        Args:
            strategies: List of strategy definitions
            groups: List of group names in display order
            current_id: Currently active strategy ID
        """
        if not strategies:
            self.frame.info("No strategies available.")
            return
        
        # Group strategies
        grouped: Dict[str, List[Dict]] = {}
        for s in strategies:
            group = s.get("group", "Other")
            if group not in grouped:
                grouped[group] = []
            grouped[group].append(s)
        
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
                elif strategy_type == "router":
                    tags.append("[magenta]Router[/magenta]")
                else:
                    if s.get("source") == "local":
                        tags.append("[green]Local[/green]")
                    tier = s.get("tier", "")
                    if tier == "flagship":
                        tags.append("[magenta]Flagship[/magenta]")
                    elif tier == "budget":
                        tags.append("[green]Budget[/green]")
                
                tag_str = " ".join(tags)
                if tag_str:
                    tag_str = f" ({tag_str})"
                
                if strategy_id == current_id:
                    lines.append(f"  [bold green]● {name}[/bold green]{tag_str} [dim](current)[/dim]")
                else:
                    lines.append(f"  [dim]○[/dim] {name}{tag_str}")
        
        content = "\n".join(lines)
        
        panel = Panel(
            content,
            title="[bold]MODELS & STRATEGIES[/bold]",
            subtitle="[dim]/model set <id> to switch[/dim]",
            border_style="dim cyan",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()
    
    def show_routines(self, routines: Dict[str, Dict[str, str]]) -> None:
        """Display available routines.
        
        Args:
            routines: Routine definitions
        """
        if not routines:
            content = "[dim](No routines configured)[/dim]\n\n"
            content += "Add routines in ~/.jexida/config.toml under [routines]"
        else:
            lines = []
            for name, routine in routines.items():
                desc = routine.get("description", "No description")
                cmd = routine.get("cmd", "")
                lines.append(f"[bold cyan]{name}[/bold cyan] - {desc}")
                if cmd:
                    lines.append(f"  [dim]cmd: {cmd}[/dim]")
            content = "\n".join(lines)
        
        panel = Panel(
            content,
            title="[bold]ROUTINES[/bold]",
            subtitle="[dim]/run <name> to execute[/dim]",
            border_style="dim cyan",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()
    
    def show_whitelist(self, patterns: List[str]) -> None:
        """Display whitelist patterns.
        
        Args:
            patterns: List of whitelist patterns
        """
        if not patterns:
            content = "[dim](No patterns whitelisted)[/dim]\n\n"
            content += "[bold]Usage:[/bold]\n"
            content += "  /whitelist add <pattern>  - Add pattern\n"
            content += "  /whitelist rm <pattern>   - Remove pattern\n\n"
            content += "[bold]Pattern Types:[/bold]\n"
            content += "  Exact: [cyan]ls[/cyan] - matches only 'ls'\n"
            content += "  Glob:  [cyan]cat *[/cyan] - matches 'cat foo.txt'\n"
            content += "  Regex: [cyan]~docker.*[/cyan] - matches 'docker ps'"
        else:
            lines = []
            for pattern in patterns:
                if pattern.startswith("~"):
                    ptype = "[magenta]regex[/magenta]"
                elif "*" in pattern or "?" in pattern:
                    ptype = "[yellow]glob[/yellow]"
                else:
                    ptype = "[green]exact[/green]"
                lines.append(f"  [cyan]{pattern}[/cyan] ({ptype})")
            content = "\n".join(lines)
        
        panel = Panel(
            content,
            title="[bold]WHITELIST[/bold]",
            border_style="dim cyan",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()
    
    def show_context(self, summary: str) -> None:
        """Display directory context summary.
        
        Args:
            summary: Context summary text
        """
        self.frame.info(summary, title="DIRECTORY CONTEXT")
    
    def show_search_results(self, results: List[str]) -> None:
        """Display search results.
        
        Args:
            results: List of result strings
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
    
    # -------------------------------------------------------------------------
    # Startup Display Methods
    # -------------------------------------------------------------------------
    
    def show_startup_check(
        self,
        checks: List[Dict[str, Any]],
    ) -> None:
        """Display startup dependency checks.
        
        Args:
            checks: List of check results with keys: name, status, message
        """
        lines = []
        for check in checks:
            name = check.get("name", "Unknown")
            status = check.get("status", "error")
            message = check.get("message", "")
            
            if status == "ok":
                icon = "[green]✓[/green]"
            elif status == "warning":
                icon = "[yellow]⚠[/yellow]"
            else:
                icon = "[red]✗[/red]"
            
            line = f"{icon} [bold]{name}[/bold]"
            if message:
                line += f" - {message}"
            lines.append(line)
        
        content = "\n".join(lines)
        
        panel = Panel(
            content,
            title="[bold]STARTUP CHECKS[/bold]",
            border_style="dim cyan",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()
    
    def show_model_changed(self, old_model: str, new_model: str) -> None:
        """Display model change confirmation.
        
        Args:
            old_model: Previous model name
            new_model: New model name
        """
        content = f"[dim]{old_model}[/dim] → [bold green]{new_model}[/bold green]"
        self.frame.success(content, title="MODEL SWITCHED")
    
    # -------------------------------------------------------------------------
    # Delegate Methods to Frame
    # -------------------------------------------------------------------------
    
    def header(self, *args, **kwargs) -> None:
        """Display header (delegates to frame)."""
        self.frame.header(*args, **kwargs)
    
    def status_bar(self, *args, **kwargs) -> None:
        """Display status bar (delegates to frame)."""
        self.frame.status_bar(*args, **kwargs)
    
    def user_prompt(self, *args, **kwargs) -> None:
        """Display user prompt (delegates to frame)."""
        self.frame.user_prompt(*args, **kwargs)
    
    def agent_response(self, *args, **kwargs) -> None:
        """Display agent response (delegates to frame)."""
        self.frame.agent_response(*args, **kwargs)
    
    def plan(self, *args, **kwargs) -> None:
        """Display plan (delegates to frame)."""
        self.frame.plan(*args, **kwargs)
    
    def mcp_plan(self, *args, **kwargs) -> None:
        """Display MCP plan (delegates to frame)."""
        self.frame.mcp_plan(*args, **kwargs)
    
    def result(self, *args, **kwargs) -> None:
        """Display result (delegates to frame)."""
        self.frame.result(*args, **kwargs)
    
    def info(self, *args, **kwargs) -> None:
        """Display info (delegates to frame)."""
        self.frame.info(*args, **kwargs)
    
    def success(self, *args, **kwargs) -> None:
        """Display success (delegates to frame)."""
        self.frame.success(*args, **kwargs)
    
    def warning(self, *args, **kwargs) -> None:
        """Display warning (delegates to frame)."""
        self.frame.warning(*args, **kwargs)
    
    def error(self, *args, **kwargs) -> None:
        """Display error (delegates to frame)."""
        self.frame.error(*args, **kwargs)
    
    def file_content(self, *args, **kwargs) -> None:
        """Display file content (delegates to frame)."""
        self.frame.file_content(*args, **kwargs)
    
    def clear(self) -> None:
        """Clear screen (delegates to frame)."""
        self.frame.clear()

