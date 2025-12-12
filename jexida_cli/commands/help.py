"""Help system for Jexida CLI."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..ui.renderer import Renderer


def show_main_help(renderer: "Renderer") -> None:
    """Show the main help menu.
    
    Args:
        renderer: UI renderer instance
    """
    help_text = """[bold cyan]NAVIGATION[/bold cyan]
  [bold]/exit[/bold], [bold]/quit[/bold]   Exit the application
  [bold]/clear[/bold]         Clear screen and redraw header
  [bold]/help[/bold]          Show this help message
  [bold]/help <topic>[/bold]  Show topic-specific help

[bold cyan]SSH & COMMANDS[/bold cyan]
  [bold]/shell[/bold]              Open interactive SSH shell
  [bold]/cmd <command>[/bold]     Run a single remote command
  [bold]/ssh <host> <cmd>[/bold]  SSH passthrough (future: multi-host)

[bold cyan]MODEL MANAGEMENT[/bold cyan]
  [bold]/model[/bold]              List available models & strategies
  [bold]/model <name>[/bold]       Switch to a model
  [bold]/model set <id>[/bold]     Switch to a strategy by ID
  [bold]/model mode <mode>[/bold]  Set model mode (direct|cascade|route|orchestrate)

[bold cyan]ROUTINES[/bold cyan]
  [bold]/routines[/bold]           List available routines
  [bold]/run <routine>[/bold]      Execute a named routine

[bold cyan]WHITELIST[/bold cyan]
  [bold]/whitelist[/bold]          Show whitelisted command patterns
  [bold]/whitelist add <p>[/bold]  Add pattern to whitelist
  [bold]/whitelist rm <p>[/bold]   Remove pattern from whitelist

[bold cyan]CONTEXT & SESSION[/bold cyan]
  [bold]/context[/bold]            Show current directory context
  [bold]/session[/bold]            Show current session info
  [bold]/session clear[/bold]      Clear saved session

[dim]Type /help <topic> for detailed help on: model, ssh, routines, whitelist[/dim]"""

    renderer.info(help_text, title="JEXIDA HELP")


def show_topic_help(renderer: "Renderer", topic: str) -> None:
    """Show help for a specific topic.
    
    Args:
        renderer: UI renderer instance
        topic: Help topic name
    """
    topics = {
        "model": _help_model,
        "ssh": _help_ssh,
        "routines": _help_routines,
        "whitelist": _help_whitelist,
        "chat": _help_chat,
    }
    
    topic = topic.lower()
    if topic in topics:
        topics[topic](renderer)
    else:
        renderer.error(
            f"Unknown help topic: {topic}\n\n"
            f"Available topics: {', '.join(topics.keys())}"
        )


def _help_model(renderer: "Renderer") -> None:
    """Show model management help."""
    help_text = """[bold cyan]MODEL MANAGEMENT[/bold cyan]

Models are organized into strategies for unified orchestration.

[bold]Commands:[/bold]
  /model                    List all available models & strategies
  /model <name>             Switch to a model (e.g., phi3, gpt-4)
  /model set <id>           Switch to a strategy by full ID
  /model mode <mode>        Set the orchestration mode

[bold]Strategy Types:[/bold]
  [green]single[/green]      Use a specific model directly
  [yellow]cascade[/yellow]    Try models in order (cheap → expensive)
  [magenta]router[/magenta]     Automatically route to best model for task
  [blue]orchestrate[/blue] Multi-model collaboration

[bold]Model Modes:[/bold]
  [bold]direct[/bold]        Use the selected model directly (default)
  [bold]cascade[/bold]       Fall back through models on failure/limits
  [bold]route[/bold]         Route requests to optimal model
  [bold]orchestrate[/bold]   Enable multi-model workflows

[bold]Examples:[/bold]
  /model phi3                 Switch to phi3 model
  /model set single:gpt-4     Use GPT-4 directly
  /model set cascade:local    Use local-first cascade strategy
  /model mode cascade         Enable cascade fallback mode

[bold]Sources:[/bold]
  [green]Local[/green]     Models running in local Ollama (phi3, llama, etc.)
  [cyan]Cloud[/cyan]     API models (OpenAI, Azure, Anthropic)"""

    renderer.info(help_text, title="MODEL HELP")


def _help_ssh(renderer: "Renderer") -> None:
    """Show SSH help."""
    help_text = """[bold cyan]SSH & REMOTE COMMANDS[/bold cyan]

Execute commands on the configured remote server.

[bold]Commands:[/bold]
  /shell              Open interactive SSH shell session
  /cmd <command>      Run a single command on the remote server
  /ssh <host> <cmd>   SSH passthrough (reserved for future multi-host)

[bold]Configuration:[/bold]
The SSH host is configured in ~/.jexida/config.toml:

  [connection]
  host = "192.168.1.224"
  user = "jexida"

[bold]Interactive Shell:[/bold]
The /shell command opens a full interactive session. Type 'exit'
in the SSH session to return to Jexida.

[bold]Examples:[/bold]
  /cmd ls -la             List files on remote server
  /cmd docker ps          Check Docker containers
  /cmd systemctl status   Check system services
  /shell                  Open interactive session

[bold]Agent Commands:[/bold]
When chatting with the agent, it can propose commands to run.
You'll be prompted to approve each command unless it matches
a whitelist pattern."""

    renderer.info(help_text, title="SSH HELP")


def _help_routines(renderer: "Renderer") -> None:
    """Show routines help."""
    help_text = """[bold cyan]ROUTINES[/bold cyan]

Routines are pre-defined command sequences for common tasks.

[bold]Commands:[/bold]
  /routines         List all available routines
  /run <name>       Execute a routine by name

[bold]Configuration:[/bold]
Define routines in ~/.jexida/config.toml:

  [routines]
  status = { cmd = "docker ps && df -h", description = "Server status" }
  logs = { cmd = "tail -100 /var/log/syslog", description = "Recent logs" }
  restart = { cmd = "sudo systemctl restart myapp", description = "Restart app" }

[bold]Routine Format:[/bold]
  name = { cmd = "<command>", description = "<what it does>" }

[bold]Examples:[/bold]
  /routines              Show all configured routines
  /run status            Execute the 'status' routine
  /run logs              Execute the 'logs' routine

[bold]Tips:[/bold]
  - Chain commands with && for sequential execution
  - Use routines for complex multi-step operations
  - Routine results are added to agent conversation history"""

    renderer.info(help_text, title="ROUTINES HELP")


def _help_whitelist(renderer: "Renderer") -> None:
    """Show whitelist help."""
    help_text = """[bold cyan]COMMAND WHITELIST[/bold cyan]

The whitelist allows auto-approving commands from the agent.

[bold]Commands:[/bold]
  /whitelist              Show current whitelist patterns
  /whitelist add <p>      Add a pattern
  /whitelist rm <p>       Remove a pattern

[bold]Pattern Types:[/bold]

  [green]Exact Match[/green]
    Pattern: ls
    Matches: only "ls"
    
  [yellow]Glob/Wildcard[/yellow]
    Pattern: cat *
    Matches: "cat file.txt", "cat /etc/hosts"
    
  [magenta]Regex[/magenta] (prefix with ~)
    Pattern: ~docker.*
    Matches: "docker ps", "docker-compose up"

[bold]Examples:[/bold]
  /whitelist add ls -la            Exact match
  /whitelist add "cat *"           Glob pattern
  /whitelist add "~docker.*"       Regex pattern
  /whitelist rm "docker.*"         Remove pattern

[bold]Approval Flow:[/bold]
When the agent proposes a command:
  [y]es     Run this command once
  [a]lways  Run and add to whitelist (auto-approve in future)
  [N]o      Don't run the command

[bold]Safety:[/bold]
  - Whitelisted commands run without confirmation
  - Be careful with broad patterns like "*"
  - Review your whitelist regularly with /whitelist"""

    renderer.info(help_text, title="WHITELIST HELP")


def _help_chat(renderer: "Renderer") -> None:
    """Show chat interaction help."""
    help_text = """[bold cyan]CHAT INTERACTION[/bold cyan]

Any input not starting with / is sent to the LLM agent.

[bold]Agent Capabilities:[/bold]
  - Execute remote commands (via SSH)
  - Execute local commands
  - Read/write local files
  - Search files in current directory
  - Call MCP server tools

[bold]Agent Response Types:[/bold]
  [cyan]Answer[/cyan]         Text response to your question
  [yellow]Shell Plan[/yellow]     Proposed command to execute
  [blue]MCP Tool[/blue]       Proposed MCP server tool call
  [green]File Read[/green]     Request to read a local file
  [magenta]File Write[/magenta]   Proposed file modification

[bold]Directory Context:[/bold]
The agent has awareness of files in your current directory.
Use /context to see what files the agent can access.

[bold]Session Persistence:[/bold]
Conversation history is saved in .jexida/session.json
and automatically restored when you return to the directory.

[bold]Multi-line Input:[/bold]
Press [Esc] then [Enter] to submit multi-line input.
This is useful for complex prompts or code snippets.

[bold]Tips:[/bold]
  - Be specific about what you want to accomplish
  - The agent will explain its reasoning before acting
  - You always have the final approval on actions"""

    renderer.info(help_text, title="CHAT HELP")

