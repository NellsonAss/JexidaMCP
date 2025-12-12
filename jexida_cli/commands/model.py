"""Model management commands for Jexida CLI."""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..ui.renderer import Renderer
    from ..state.config import Config
    from ..ssh_client import SSHClient
    from ..mcp_client import MCPClient
    from ..agent import Agent


def handle_model_list(
    renderer: "Renderer",
    config: "Config",
    ssh_client: "SSHClient",
    mcp_client: Optional["MCPClient"] = None,
) -> None:
    """Handle /model command - list available models and strategies.
    
    First tries to fetch from MCP server (unified registry), then falls back to local Ollama.
    
    Args:
        renderer: UI renderer instance
        config: Configuration instance
        ssh_client: SSH client instance
        mcp_client: Optional MCP client instance
    """
    # Try to get strategies from MCP server first
    if mcp_client:
        strategies_data = mcp_client.get_strategies()
        if strategies_data:
            strategies = strategies_data.get("strategies", [])
            groups = strategies_data.get("groups", [])
            current_id = mcp_client.current_strategy_id
            renderer.show_models(strategies, groups, current_id)
            return
    
    # Fallback: Query local Ollama
    renderer.info("MCP server unavailable. Showing local Ollama models:")
    
    stdout, stderr, exit_code = ssh_client.execute_command(
        "ollama list --noheader 2>/dev/null | awk '{print $1}'"
    )
    
    if exit_code != 0 or not stdout.strip():
        stdout, stderr, exit_code = ssh_client.execute_command(
            "ollama list 2>/dev/null | tail -n +2 | awk '{print $1}'"
        )
    
    if exit_code == 0 and stdout.strip():
        models = [m.strip() for m in stdout.strip().split("\n") if m.strip()]
        
        # Format as strategies for display
        strategies = []
        for model in models:
            strategies.append({
                "id": f"single:{model}",
                "display_name": model,
                "strategy_type": "single",
                "source": "local",
                "group": "Local Models",
            })
        
        current_id = f"single:{config.model}"
        renderer.show_models(strategies, ["Local Models"], current_id)
    else:
        renderer.error(
            "Could not retrieve models from Ollama.\n"
            "Check if Ollama is running on the remote server."
        )
        if stderr:
            renderer.error(stderr)


def handle_model_switch(
    renderer: "Renderer",
    config: "Config",
    ssh_client: "SSHClient",
    agent: "Agent",
    model_name: str,
    mcp_client: Optional["MCPClient"] = None,
) -> None:
    """Handle /model <name> or /model set <id> command - switch model/strategy.
    
    Supports:
    - Strategy IDs: "single:gpt-5-nano", "cascade:cloud-cheapest-first"
    - Model names for backwards compatibility: "gpt-5-nano", "llama3:latest"
    
    Args:
        renderer: UI renderer instance
        config: Configuration instance
        ssh_client: SSH client instance
        agent: Agent instance
        model_name: Model/strategy identifier
        mcp_client: Optional MCP client instance
    """
    old_model = config.model
    
    # Try MCP server first for strategy switching
    if mcp_client:
        # If it doesn't look like a strategy ID, try to make it one
        strategy_id = model_name
        if not any(strategy_id.startswith(p) for p in ("single:", "cascade:", "router:")):
            strategy_id = f"single:{model_name}"
        
        result = mcp_client.set_active_strategy(strategy_id)
        
        if result and result.get("success"):
            strategy_name = result.get("strategy", {}).get("display_name", model_name)
            renderer.show_model_changed(old_model, strategy_name)
            
            # Update local config to track the model
            if result.get("model"):
                model_id = result["model"].get("model_id", model_name)
                config.set_model(model_id)
                agent.set_model(model_id)
            return
        
        elif result and result.get("error"):
            # Try without single: prefix
            if strategy_id != model_name:
                result2 = mcp_client.set_active_strategy(model_name)
                if result2 and result2.get("success"):
                    strategy_name = result2.get("strategy", {}).get("display_name", model_name)
                    renderer.show_model_changed(old_model, strategy_name)
                    return
            
            renderer.error(
                f"Failed to switch strategy: {result.get('error')}\n\n"
                "Use /model to list available strategies."
            )
            return
    
    # Fallback: Check local Ollama model
    stdout, stderr, exit_code = ssh_client.execute_command(
        f"ollama show {model_name} --modelfile 2>/dev/null | head -1"
    )
    
    if exit_code != 0:
        renderer.error(
            f"Model/strategy '{model_name}' not found.\n\n"
            "Use /model to list available options, or:\n"
            f"  /cmd ollama pull {model_name}"
        )
        return
    
    # Update config and agent for local model
    config.set_model(model_name)
    agent.set_model(model_name)
    renderer.show_model_changed(old_model, model_name)

