"""Helper functions for Jexida CLI commands."""

import sys
from typing import List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..ui.renderer import Renderer
    from ..state.config import Config
    from ..mcp_client import MCPClient


def run_startup_checks(
    renderer: "Renderer",
    config: "Config",
    mcp_client: "MCPClient",
) -> bool:
    """Run startup dependency and connectivity checks.
    
    Args:
        renderer: UI renderer instance
        config: Configuration instance
        mcp_client: MCP client instance
        
    Returns:
        True if all critical checks pass
    """
    checks: List[Dict[str, Any]] = []
    has_critical_failure = False
    
    # Check Python version
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 10):
        checks.append({
            "name": "Python Version",
            "status": "ok",
            "message": f"v{python_version}",
        })
    else:
        checks.append({
            "name": "Python Version",
            "status": "error",
            "message": f"v{python_version} (requires 3.10+)",
        })
        has_critical_failure = True
    
    # Check config file
    if config.config_file.exists():
        checks.append({
            "name": "Configuration",
            "status": "ok",
            "message": str(config.config_file),
        })
    else:
        checks.append({
            "name": "Configuration",
            "status": "warning",
            "message": "Using defaults (no config file found)",
        })
    
    # Check MCP server connectivity
    try:
        strategies = mcp_client.get_strategies()
        if strategies:
            strategy_count = len(strategies.get("strategies", []))
            checks.append({
                "name": "MCP Server",
                "status": "ok",
                "message": f"Connected ({strategy_count} strategies)",
            })
        else:
            checks.append({
                "name": "MCP Server",
                "status": "warning",
                "message": "Connected but no strategies found",
            })
    except Exception as e:
        checks.append({
            "name": "MCP Server",
            "status": "warning",
            "message": f"Not reachable (local mode only): {str(e)[:40]}",
        })
    
    # Check required dependencies
    missing_deps = []
    optional_missing = []
    
    try:
        import rich  # noqa: F401
    except ImportError:
        missing_deps.append("rich")
    
    try:
        import tomlkit  # noqa: F401
    except ImportError:
        missing_deps.append("tomlkit")
    
    try:
        import httpx  # noqa: F401
    except ImportError:
        optional_missing.append("httpx")
    
    try:
        import prompt_toolkit  # noqa: F401
    except ImportError:
        optional_missing.append("prompt_toolkit")
    
    if missing_deps:
        checks.append({
            "name": "Dependencies",
            "status": "error",
            "message": f"Missing: {', '.join(missing_deps)}",
        })
        has_critical_failure = True
    elif optional_missing:
        checks.append({
            "name": "Dependencies",
            "status": "warning",
            "message": f"Optional missing: {', '.join(optional_missing)}",
        })
    else:
        checks.append({
            "name": "Dependencies",
            "status": "ok",
            "message": "All installed",
        })
    
    # Only show checks if there are warnings or errors
    has_issues = any(c["status"] != "ok" for c in checks)
    if has_issues:
        renderer.show_startup_check(checks)
    
    return not has_critical_failure


def check_mcp_server(mcp_client: "MCPClient") -> Dict[str, Any]:
    """Check MCP server connectivity and get basic info.
    
    Args:
        mcp_client: MCP client instance
        
    Returns:
        Dict with status and info
    """
    try:
        strategies = mcp_client.get_strategies()
        if strategies:
            return {
                "connected": True,
                "strategy_count": len(strategies.get("strategies", [])),
                "active_strategy": strategies.get("active_strategy_id"),
            }
        return {"connected": True, "strategy_count": 0}
    except Exception as e:
        return {"connected": False, "error": str(e)}


def format_duration(seconds: float) -> str:
    """Format a duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string (e.g., "1.5s", "2m 30s", "1h 5m")
    """
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"

