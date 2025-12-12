"""Central command router for Jexida CLI.

Routes user input to appropriate command handlers.
"""

from typing import Optional, Callable, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..ui.renderer import Renderer
    from ..state.config import Config
    from ..state.session import Session
    from ..mcp_client import MCPClient
    from ..ssh_client import SSHClient
    from ..agent import Agent


class CommandRouter:
    """Routes CLI commands to their handlers."""

    def __init__(
        self,
        renderer: "Renderer",
        config: "Config",
        session: "Session",
        mcp_client: "MCPClient",
        ssh_client: "SSHClient",
        agent: "Agent",
    ):
        """Initialize the command router.
        
        Args:
            renderer: UI renderer instance
            config: Configuration instance
            session: Session manager instance
            mcp_client: MCP client instance
            ssh_client: SSH client instance
            agent: LLM agent instance
        """
        self.renderer = renderer
        self.config = config
        self.session = session
        self.mcp_client = mcp_client
        self.ssh_client = ssh_client
        self.agent = agent
        
        # Build command registry
        self._commands: Dict[str, Callable] = {
            "/exit": self._cmd_exit,
            "/quit": self._cmd_exit,
            "/help": self._cmd_help,
            "/clear": self._cmd_clear,
            "/context": self._cmd_context,
            "/session": self._cmd_session,
            "/session clear": self._cmd_session_clear,
            "/shell": self._cmd_shell,
            "/routines": self._cmd_routines,
            "/whitelist": self._cmd_whitelist,
            "/model": self._cmd_model,
            "/nodes": self._cmd_nodes_list,
            "/nodes list": self._cmd_nodes_list,
            "/jobs": self._cmd_jobs_list,
            "/jobs list": self._cmd_jobs_list,
            # n8n commands
            "/n8n": self._cmd_n8n_help,
            "/n8n health": self._cmd_n8n_health,
            "/n8n list": self._cmd_n8n_list,
            "/n8n list --active": self._cmd_n8n_list_active,
            "/n8n restart": self._cmd_n8n_restart,
            "/n8n backup": self._cmd_n8n_backup,
            # Azure commands
            "/azure": self._cmd_azure_help,
            "/azure status": self._cmd_azure_status,
            # Discord commands
            "/discord": self._cmd_discord_help,
            "/discord help": self._cmd_discord_help,
            "/discord test": self._cmd_discord_test,
            "/discord bootstrap": self._cmd_discord_bootstrap,
            "/discord bootstrap --dry-run": self._cmd_discord_bootstrap_dry_run,
        }
        
        # Prefix commands (need argument parsing)
        self._prefix_commands: Dict[str, Callable] = {
            "/cmd ": self._cmd_remote,
            "/run ": self._cmd_run,
            "/model ": self._cmd_model_switch,
            "/whitelist add ": self._cmd_whitelist_add,
            "/whitelist rm ": self._cmd_whitelist_remove,
            "/whitelist remove ": self._cmd_whitelist_remove,
            "/ssh ": self._cmd_ssh,
            "/help ": self._cmd_help_topic,
            "/nodes check ": self._cmd_nodes_check,
            "/jobs submit ": self._cmd_jobs_submit,
            "/jobs show ": self._cmd_jobs_show,
            # n8n prefix commands
            "/n8n get ": self._cmd_n8n_get,
            "/n8n run ": self._cmd_n8n_run,
            "/n8n exec ": self._cmd_n8n_exec,
            "/n8n webhook ": self._cmd_n8n_webhook,
            "/n8n backup ": self._cmd_n8n_backup_named,
            # Azure prefix commands
            "/azure create-env ": self._cmd_azure_create_env,
            "/azure add-data ": self._cmd_azure_add_data,
            "/azure deploy ": self._cmd_azure_deploy,
            # Discord prefix commands
            "/discord test ": self._cmd_discord_test_channel,
            "/discord bootstrap ": self._cmd_discord_bootstrap_config,
        }

    def route(self, user_input: str) -> Optional[str]:
        """Route a command to its handler.
        
        Args:
            user_input: User's input string
            
        Returns:
            Signal string ("exit", "continue") or None for chat message
        """
        # Check exact commands
        if user_input in self._commands:
            return self._commands[user_input]()
        
        # Check prefix commands
        for prefix, handler in self._prefix_commands.items():
            if user_input.startswith(prefix):
                arg = user_input[len(prefix):].strip()
                return handler(arg)
        
        # Unknown command
        if user_input.startswith("/"):
            self.renderer.error(
                f"Unknown command: {user_input}\n\nType /help for available commands."
            )
            return "continue"
        
        # Not a command - treat as chat
        return None

    # -------------------------------------------------------------------------
    # Core Commands
    # -------------------------------------------------------------------------

    def _cmd_exit(self) -> str:
        """Handle /exit or /quit."""
        if self.config.context_auto_save_session:
            self.session.save()
        self.renderer.info("Session closed.", title="GOODBYE")
        return "exit"

    def _cmd_help(self) -> str:
        """Handle /help - show main help."""
        from .help import show_main_help
        show_main_help(self.renderer)
        return "continue"

    def _cmd_help_topic(self, topic: str) -> str:
        """Handle /help <topic> - show topic-specific help."""
        from .help import show_topic_help
        show_topic_help(self.renderer, topic)
        return "continue"

    def _cmd_clear(self) -> str:
        """Handle /clear - clear screen and redraw header."""
        self.renderer.clear()
        self.renderer.header(
            host=self.config.host,
            user=self.config.user,
            model=self.config.model,
            working_dir=str(self.session.working_dir),
            mode=self.config.model_mode,
        )
        return "continue"

    def _cmd_context(self) -> str:
        """Handle /context - show directory context."""
        self.renderer.show_context(self.session.get_context_summary())
        return "continue"

    def _cmd_session(self) -> str:
        """Handle /session - show session info."""
        info = self.session.get_info()
        if info:
            content = (
                f"Messages: {info['message_count']}\n"
                f"Directory: {info['directory']}\n"
                f"Last updated: {info['last_updated']}"
            )
            self.renderer.info(content, title="SESSION")
        else:
            self.renderer.info("No saved session for this directory.")
        return "continue"

    def _cmd_session_clear(self) -> str:
        """Handle /session clear - clear session."""
        if self.session.clear():
            self.agent.clear_history()
            self.renderer.success("Session cleared.")
        else:
            self.renderer.error("Could not clear session.")
        return "continue"

    # -------------------------------------------------------------------------
    # SSH Commands
    # -------------------------------------------------------------------------

    def _cmd_shell(self) -> str:
        """Handle /shell - open interactive SSH shell."""
        self.renderer.info(
            f"Opening SSH shell to {self.config.user}@{self.config.host}...\n"
            "Type 'exit' in the SSH session to return to Jexida."
        )
        self.renderer.console.print()
        self.ssh_client.open_shell()
        self.renderer.console.print()
        self.renderer.status_bar(
            self.config.host,
            self.config.user,
            self.config.model,
        )
        return "continue"

    def _cmd_remote(self, command: str) -> str:
        """Handle /cmd <command> - run single remote command."""
        if not command:
            self.renderer.error("Usage: /cmd <command>")
            return "continue"
        
        self.renderer.info(f"[dim]Executing:[/dim] {command}", title="REMOTE COMMAND")
        stdout, stderr, exit_code = self.ssh_client.execute_command(command)
        self.renderer.result(stdout, stderr, exit_code, target="ssh")
        self.renderer.status_bar(
            self.config.host,
            self.config.user,
            self.config.model,
            exit_code,
        )
        return "continue"

    def _cmd_ssh(self, args: str) -> str:
        """Handle /ssh <target> <command> - SSH passthrough."""
        parts = args.split(" ", 1)
        if len(parts) < 2:
            self.renderer.error("Usage: /ssh <target> <command>")
            return "continue"
        
        # For now, target is just documentation - we use the configured host
        # Future: support multiple SSH targets
        command = parts[1]
        return self._cmd_remote(command)

    # -------------------------------------------------------------------------
    # Routine Commands
    # -------------------------------------------------------------------------

    def _cmd_routines(self) -> str:
        """Handle /routines - list routines."""
        self.renderer.show_routines(self.config.routines)
        return "continue"

    def _cmd_run(self, routine_name: str) -> str:
        """Handle /run <routine> - execute routine."""
        if not routine_name:
            self.renderer.error("Usage: /run <routine_name>")
            return "continue"
        
        routine = self.config.get_routine(routine_name)
        if not routine:
            self.renderer.error(
                f"Routine '{routine_name}' not found.\n"
                "Use /routines to list available routines."
            )
            return "continue"
        
        cmd = routine.get("cmd")
        if not cmd:
            self.renderer.error(f"Routine '{routine_name}' has no command defined.")
            return "continue"
        
        description = routine.get("description", "No description")
        self.renderer.info(
            f"Running routine: [bold]{routine_name}[/bold]\n{description}",
            title="ROUTINE"
        )
        
        stdout, stderr, exit_code = self.ssh_client.execute_command(cmd)
        self.renderer.result(stdout, stderr, exit_code, target="ssh")
        self.renderer.status_bar(
            self.config.host,
            self.config.user,
            self.config.model,
            exit_code,
        )
        
        # Add to agent history
        self.agent.add_tool_result(cmd, exit_code, stdout, stderr)
        return "continue"

    # -------------------------------------------------------------------------
    # Model Commands
    # -------------------------------------------------------------------------

    def _cmd_model(self) -> str:
        """Handle /model - list models and strategies."""
        from .model import handle_model_list
        handle_model_list(self.renderer, self.config, self.ssh_client, self.mcp_client)
        return "continue"

    def _cmd_model_switch(self, args: str) -> str:
        """Handle /model <name> or /model set <id> or /model mode <mode>."""
        if not args:
            return self._cmd_model()
        
        # Handle mode subcommand
        if args.startswith("mode "):
            mode = args[5:].strip()
            return self._cmd_model_mode(mode)
        
        # Handle set subcommand
        if args.startswith("set "):
            model_id = args[4:].strip()
        else:
            model_id = args
        
        from .model import handle_model_switch
        handle_model_switch(
            self.renderer,
            self.config,
            self.ssh_client,
            self.agent,
            model_id,
            self.mcp_client,
        )
        return "continue"

    def _cmd_model_mode(self, mode: str) -> str:
        """Handle /model mode <mode> - switch model mode."""
        valid_modes = ("direct", "cascade", "route", "orchestrate")
        if mode not in valid_modes:
            self.renderer.error(
                f"Invalid mode: {mode}\n\n"
                f"Valid modes: {', '.join(valid_modes)}"
            )
            return "continue"
        
        old_mode = self.config.model_mode
        try:
            self.config.set_model_mode(mode)
            self.renderer.success(
                f"Model mode changed: [dim]{old_mode}[/dim] → [bold]{mode}[/bold]",
                title="MODE CHANGED"
            )
        except Exception as e:
            self.renderer.error(f"Failed to change mode: {e}")
        
        return "continue"

    # -------------------------------------------------------------------------
    # Whitelist Commands
    # -------------------------------------------------------------------------

    def _cmd_whitelist(self) -> str:
        """Handle /whitelist - show whitelist."""
        self.renderer.show_whitelist(self.config.get_whitelist_patterns())
        return "continue"

    def _cmd_whitelist_add(self, pattern: str) -> str:
        """Handle /whitelist add <pattern>."""
        if not pattern:
            self.renderer.error("Usage: /whitelist add <pattern>")
            return "continue"
        
        self.config.add_to_whitelist(pattern)
        self.renderer.success(f"Added to whitelist: [cyan]{pattern}[/cyan]")
        return "continue"

    def _cmd_whitelist_remove(self, pattern: str) -> str:
        """Handle /whitelist rm <pattern>."""
        if not pattern:
            self.renderer.error("Usage: /whitelist rm <pattern>")
            return "continue"
        
        if self.config.remove_from_whitelist(pattern):
            self.renderer.success(f"Removed from whitelist: [cyan]{pattern}[/cyan]")
        else:
            self.renderer.error(
                f"Pattern not in whitelist: [cyan]{pattern}[/cyan]\n"
                "Use /whitelist to see current patterns."
            )
        return "continue"

    # -------------------------------------------------------------------------
    # Jobs & Nodes Commands
    # -------------------------------------------------------------------------

    def _cmd_nodes_list(self) -> str:
        """Handle /nodes or /nodes list - list worker nodes."""
        from .jobs import handle_nodes_list
        return handle_nodes_list(self.renderer, self.mcp_client)

    def _cmd_nodes_check(self, node_name: str) -> str:
        """Handle /nodes check <name> - check node connectivity."""
        from .jobs import handle_nodes_check
        return handle_nodes_check(self.renderer, self.mcp_client, node_name)

    def _cmd_jobs_list(self) -> str:
        """Handle /jobs or /jobs list - list recent jobs."""
        from .jobs import handle_jobs_list
        return handle_jobs_list(self.renderer, self.mcp_client)

    def _cmd_jobs_submit(self, args: str) -> str:
        """Handle /jobs submit --node <name> --cmd "<cmd>" - submit job."""
        from .jobs import handle_jobs_submit, parse_jobs_submit_args
        node_name, command, timeout = parse_jobs_submit_args(args)
        if not node_name or not command:
            self.renderer.error(
                'Usage: /jobs submit --node <name> --cmd "<command>" [--timeout <secs>]'
            )
            return "continue"
        return handle_jobs_submit(self.renderer, self.mcp_client, node_name, command, timeout)

    def _cmd_jobs_show(self, job_id: str) -> str:
        """Handle /jobs show <id> - show job details."""
        from .jobs import handle_jobs_show
        return handle_jobs_show(self.renderer, self.mcp_client, job_id)

    # -------------------------------------------------------------------------
    # n8n Commands
    # -------------------------------------------------------------------------

    def _cmd_n8n_help(self) -> str:
        """Handle /n8n - show n8n help."""
        from .n8n import handle_n8n_help
        return handle_n8n_help(self.renderer)

    def _cmd_n8n_health(self) -> str:
        """Handle /n8n health - check n8n health."""
        from .n8n import handle_n8n_health
        return handle_n8n_health(self.renderer, self.mcp_client)

    def _cmd_n8n_list(self) -> str:
        """Handle /n8n list - list workflows."""
        from .n8n import handle_n8n_list
        return handle_n8n_list(self.renderer, self.mcp_client)

    def _cmd_n8n_list_active(self) -> str:
        """Handle /n8n list --active - list active workflows."""
        from .n8n import handle_n8n_list
        return handle_n8n_list(self.renderer, self.mcp_client, active_only=True)

    def _cmd_n8n_get(self, workflow_id: str) -> str:
        """Handle /n8n get <id> - get workflow details."""
        from .n8n import handle_n8n_get
        return handle_n8n_get(self.renderer, self.mcp_client, workflow_id)

    def _cmd_n8n_run(self, args: str) -> str:
        """Handle /n8n run <id> [payload] - run workflow."""
        parts = args.split(" ", 1)
        workflow_id = parts[0]
        payload_str = parts[1] if len(parts) > 1 else ""
        from .n8n import handle_n8n_run
        return handle_n8n_run(self.renderer, self.mcp_client, workflow_id, payload_str)

    def _cmd_n8n_exec(self, execution_id: str) -> str:
        """Handle /n8n exec <id> - get execution details."""
        from .n8n import handle_n8n_exec
        return handle_n8n_exec(self.renderer, self.mcp_client, execution_id)

    def _cmd_n8n_webhook(self, args: str) -> str:
        """Handle /n8n webhook <path> [payload] - trigger webhook."""
        parts = args.split(" ", 1)
        path = parts[0]
        payload_str = parts[1] if len(parts) > 1 else ""
        from .n8n import handle_n8n_webhook
        return handle_n8n_webhook(self.renderer, self.mcp_client, path, payload_str)

    def _cmd_n8n_restart(self) -> str:
        """Handle /n8n restart - restart n8n stack."""
        from .n8n import handle_n8n_restart
        return handle_n8n_restart(self.renderer, self.mcp_client)

    def _cmd_n8n_backup(self) -> str:
        """Handle /n8n backup - create backup."""
        from .n8n import handle_n8n_backup
        return handle_n8n_backup(self.renderer, self.mcp_client)

    def _cmd_n8n_backup_named(self, backup_name: str) -> str:
        """Handle /n8n backup <name> - create named backup."""
        from .n8n import handle_n8n_backup
        return handle_n8n_backup(self.renderer, self.mcp_client, backup_name)

    # -------------------------------------------------------------------------
    # Azure Commands
    # -------------------------------------------------------------------------

    def _cmd_azure_help(self) -> str:
        """Handle /azure - show Azure help."""
        from .azure import handle_azure_help
        return handle_azure_help(self.renderer)

    def _cmd_azure_status(self) -> str:
        """Handle /azure status - check Azure connection status."""
        from .azure import handle_azure_status
        return handle_azure_status(self.renderer, self.mcp_client)

    def _cmd_azure_create_env(self, args: str) -> str:
        """Handle /azure create-env - create app environment."""
        from .azure import handle_azure_create_env
        return handle_azure_create_env(self.renderer, self.mcp_client, args)

    def _cmd_azure_add_data(self, args: str) -> str:
        """Handle /azure add-data - add data services."""
        from .azure import handle_azure_add_data
        return handle_azure_add_data(self.renderer, self.mcp_client, args)

    def _cmd_azure_deploy(self, args: str) -> str:
        """Handle /azure deploy - deploy ARM template."""
        from .azure import handle_azure_deploy
        return handle_azure_deploy(self.renderer, self.mcp_client, args)

    # -------------------------------------------------------------------------
    # Discord Commands
    # -------------------------------------------------------------------------

    def _cmd_discord_help(self) -> str:
        """Handle /discord - show Discord help."""
        from .discord import handle_discord_help
        return handle_discord_help(self.renderer)

    def _cmd_discord_test(self) -> str:
        """Handle /discord test - test Discord connectivity."""
        from .discord import handle_discord_test
        return handle_discord_test(self.renderer, self.mcp_client)

    def _cmd_discord_test_channel(self, channel_id: str) -> str:
        """Handle /discord test <channel_id> - test by sending message."""
        from .discord import handle_discord_test
        return handle_discord_test(self.renderer, self.mcp_client, channel_id)

    def _cmd_discord_bootstrap(self) -> str:
        """Handle /discord bootstrap - bootstrap server from config."""
        from .discord import handle_discord_bootstrap
        return handle_discord_bootstrap(self.renderer, self.mcp_client)

    def _cmd_discord_bootstrap_dry_run(self) -> str:
        """Handle /discord bootstrap --dry-run - preview bootstrap changes."""
        from .discord import handle_discord_bootstrap
        return handle_discord_bootstrap(self.renderer, self.mcp_client, dry_run=True)

    def _cmd_discord_bootstrap_config(self, args: str) -> str:
        """Handle /discord bootstrap <config_path> [--dry-run]."""
        from .discord import handle_discord_bootstrap
        dry_run = "--dry-run" in args
        config_path = args.replace("--dry-run", "").strip()
        return handle_discord_bootstrap(self.renderer, self.mcp_client, config_path, dry_run)

