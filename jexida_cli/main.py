"""Main entry point for Jexida CLI.

A clean, modular CLI for interacting with the MCP server,
managing models, executing commands, and chatting with LLM agents.
"""

import os
import sys
from rich.console import Console

from .state.config import Config
from .state.session import Session
from .ui.renderer import Renderer
from .ssh_client import SSHClient
from .mcp_client import MCPClient
from .agent import Agent
from .executor import LocalExecutor, SSHExecutor, MCPExecutor
from .commands.router import CommandRouter
from .commands.helpers import run_startup_checks
from .commands.chat import handle_chat


console = Console()


def main() -> None:
    """Main entry point - starts the REPL loop."""
    # Load configuration
    config = Config()
    config.load()
    
    # Initialize session manager (directory context)
    session = Session(
        working_dir=os.getcwd(),
        max_depth=config.context_max_depth,
        exclude_patterns=set(config.context_exclude_patterns),
        max_file_size=config.context_max_file_size,
    )
    
    # Initialize UI renderer
    renderer = Renderer()
    
    # Initialize clients
    ssh_client = SSHClient(config.host, config.user)
    mcp_client = MCPClient(config)
    
    # Initialize agent
    agent = Agent(ssh_client, config.model, mcp_client=mcp_client)
    agent.set_context_manager(session)
    
    # Initialize executors
    local_executor = LocalExecutor()
    ssh_executor = SSHExecutor(ssh_client)
    mcp_executor = MCPExecutor(mcp_client)
    
    # Initialize command router
    router = CommandRouter(
        renderer=renderer,
        config=config,
        session=session,
        mcp_client=mcp_client,
        ssh_client=ssh_client,
        agent=agent,
    )
    
    try:
        # Run startup checks
        run_startup_checks(renderer, config, mcp_client)
        
        # Auto-load session if enabled
        if config.context_auto_load_session:
            if session.load():
                agent.set_conversation_history(session.conversation_history)
                info = session.get_info()
                if info:
                    renderer.info(
                        f"Resumed session with {info['message_count']} messages\n"
                        f"Last updated: {info['last_updated'][:19]}"
                    )
        
        # Clear screen and show header
        renderer.clear()
        renderer.header(
            host=config.host,
            user=config.user,
            model=config.model,
            working_dir=str(session.working_dir),
            mode=config.model_mode,
        )
        
        # Main REPL loop
        _run_repl(
            renderer=renderer,
            router=router,
            config=config,
            session=session,
            agent=agent,
            local_executor=local_executor,
            ssh_executor=ssh_executor,
            mcp_executor=mcp_executor,
        )
        
    except Exception as e:
        renderer.error(f"Fatal error: {str(e)}")
        if "--debug" in sys.argv:
            console.print_exception()
        sys.exit(1)
        
    finally:
        # Cleanup
        mcp_client.close()


def _run_repl(
    renderer: Renderer,
    router: CommandRouter,
    config: Config,
    session: Session,
    agent: Agent,
    local_executor: LocalExecutor,
    ssh_executor: SSHExecutor,
    mcp_executor: MCPExecutor,
) -> None:
    """Run the main REPL loop.
    
    Args:
        renderer: UI renderer instance
        router: Command router instance
        config: Configuration instance
        session: Session manager instance
        agent: LLM agent instance
        local_executor: Local command executor
        ssh_executor: SSH command executor
        mcp_executor: MCP tool executor
    """
    while True:
        try:
            # Get user input
            user_input = renderer.get_multiline_input().strip()
            
            if not user_input:
                continue
            
            # Check if it's a command
            if user_input.startswith("/"):
                result = router.route(user_input)
                
                if result == "exit":
                    break
                elif result == "continue":
                    continue
                # If None, treat as chat (shouldn't happen with / prefix)
            
            # Handle as chat message
            handle_chat(
                renderer=renderer,
                config=config,
                session=session,
                agent=agent,
                local_executor=local_executor,
                ssh_executor=ssh_executor,
                mcp_executor=mcp_executor,
                user_input=user_input,
            )
            
            # Auto-save session
            if config.context_auto_save_session:
                session.set_history(agent.conversation_history)
                session.save()
        
        except KeyboardInterrupt:
            console.print("\n\n[dim]Interrupted. Type /exit to quit.[/dim]\n")
            continue
        
        except EOFError:
            console.print("\n[dim]Session closed.[/dim]\n")
            break
        
        except Exception as e:
            renderer.error(f"Unexpected error: {str(e)}")
            if "--debug" in sys.argv:
                console.print_exception()


if __name__ == "__main__":
    main()
