"""Discord CLI command handlers.

Provides CLI commands for interacting with Discord via MCP tools.
"""

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..ui.renderer import Renderer
    from ..mcp_client import MCPClient


def handle_discord_help(renderer: "Renderer") -> str:
    """Show Discord command help."""
    help_text = """
[bold]Discord Bot Commands[/bold]

[cyan]/discord help[/cyan]            Show this help message
[cyan]/discord test[/cyan]            Test Discord connectivity
[cyan]/discord test <channel_id>[/cyan]  Test by sending a message
[cyan]/discord bootstrap[/cyan]       Bootstrap server from config
[cyan]/discord bootstrap <path>[/cyan]  Bootstrap with custom config
[cyan]/discord bootstrap --dry-run[/cyan]  Preview changes without applying

[dim]Examples:[/dim]
  /discord test
  /discord test 123456789012345678
  /discord bootstrap
  /discord bootstrap config/my_server.yml
  /discord bootstrap --dry-run

[dim]Environment Variables:[/dim]
  DISCORD_BOT_TOKEN    Bot token (required)
  DISCORD_GUILD_ID     Default guild ID (required)
"""
    renderer.info(help_text.strip(), title="DISCORD COMMANDS")
    return "continue"


def handle_discord_test(renderer: "Renderer", mcp_client: "MCPClient", channel_id: str = "") -> str:
    """Handle /discord test [channel_id] - test Discord connectivity."""
    renderer.info("Testing Discord connectivity...", title="DISCORD")
    
    if channel_id:
        # Test by sending a message
        result = mcp_client.run_tool("discord_send_message", {
            "channel_id": channel_id,
            "content": "🤖 JexidaMCP Discord integration test message!"
        })
        
        if result.get("success"):
            inner = result.get("result", {})
            if inner.get("ok"):
                renderer.success(
                    f"Test message sent successfully!\n\n"
                    f"Channel: {channel_id}\n"
                    f"Message ID: {inner.get('message_id', 'unknown')}",
                    title="CONNECTION OK"
                )
            else:
                renderer.error(
                    f"Failed to send test message\n\n"
                    f"Error: {inner.get('error', 'Unknown')}\n\n"
                    f"[dim]Check that:[/dim]\n"
                    f"  • DISCORD_BOT_TOKEN is set correctly\n"
                    f"  • Bot has access to the channel\n"
                    f"  • Channel ID is correct"
                )
        else:
            renderer.error(f"Request failed: {result.get('error', 'Unknown error')}")
    else:
        # Test by getting guild info
        result = mcp_client.run_tool("discord_get_guild_info", {})
        
        if result.get("success"):
            inner = result.get("result", {})
            if inner.get("ok"):
                renderer.success(
                    f"Discord connection successful!\n\n"
                    f"Guild: {inner.get('name', 'Unknown')}\n"
                    f"Guild ID: {inner.get('guild_id', 'Unknown')}\n"
                    f"Members: {inner.get('member_count', 'N/A')}",
                    title="CONNECTION OK"
                )
            else:
                error = inner.get("error", "Unknown error")
                if "missing DISCORD_BOT_TOKEN" in error or "missing DISCORD_GUILD_ID" in error:
                    renderer.error(
                        f"Discord is not configured\n\n"
                        f"Error: {error}\n\n"
                        f"[dim]Required environment variables:[/dim]\n"
                        f"  DISCORD_BOT_TOKEN=your-bot-token\n"
                        f"  DISCORD_GUILD_ID=your-guild-id"
                    )
                else:
                    renderer.error(
                        f"Discord connection failed\n\n"
                        f"Error: {error}\n\n"
                        f"[dim]Check that:[/dim]\n"
                        f"  • DISCORD_BOT_TOKEN is valid\n"
                        f"  • DISCORD_GUILD_ID is correct\n"
                        f"  • Bot is added to the server"
                    )
        else:
            renderer.error(f"Request failed: {result.get('error', 'Unknown error')}")
    
    return "continue"


def handle_discord_bootstrap(
    renderer: "Renderer",
    mcp_client: "MCPClient",
    config_path: str = "",
    dry_run: bool = False
) -> str:
    """Handle /discord bootstrap [config_path] [--dry-run] - bootstrap server from config."""
    mode = "[DRY RUN] " if dry_run else ""
    renderer.info(f"{mode}Bootstrapping Discord server...", title="DISCORD")
    
    params = {}
    if config_path:
        params["config_path"] = config_path
    if dry_run:
        params["dry_run"] = True
    
    result = mcp_client.run_tool("discord_bootstrap_server", params)
    
    if result.get("success"):
        inner = result.get("result", {})
        if inner.get("ok"):
            # Format summary
            lines = [f"Bootstrap completed for guild: {inner.get('guild_id', 'unknown')}\n"]
            
            # Categories
            cats_created = inner.get("categories_created", [])
            cats_existing = inner.get("categories_existing", [])
            if cats_created:
                lines.append("[green]Categories created:[/green]")
                for cat in cats_created:
                    lines.append(f"  [green]✓[/green] {cat}")
            if cats_existing:
                lines.append("[dim]Categories existing:[/dim]")
                for cat in cats_existing:
                    lines.append(f"  [dim]○[/dim] {cat}")
            
            # Channels
            chs_created = inner.get("channels_created", [])
            chs_existing = inner.get("channels_existing", [])
            if chs_created:
                lines.append("\n[green]Channels created:[/green]")
                for ch in chs_created:
                    lines.append(f"  [green]✓[/green] {ch}")
            if chs_existing:
                lines.append("[dim]Channels existing:[/dim]")
                for ch in chs_existing:
                    lines.append(f"  [dim]○[/dim] {ch}")
            
            # Roles
            roles_created = inner.get("roles_created", [])
            roles_existing = inner.get("roles_existing", [])
            if roles_created:
                lines.append("\n[green]Roles created:[/green]")
                for role in roles_created:
                    lines.append(f"  [green]✓[/green] {role}")
            if roles_existing:
                lines.append("[dim]Roles existing:[/dim]")
                for role in roles_existing:
                    lines.append(f"  [dim]○[/dim] {role}")
            
            # Errors
            errors = inner.get("errors", [])
            if errors:
                lines.append("\n[red]Errors:[/red]")
                for err in errors:
                    lines.append(f"  [red]✗[/red] {err}")
            
            # Summary counts
            total_created = len(cats_created) + len(chs_created) + len(roles_created)
            total_existing = len(cats_existing) + len(chs_existing) + len(roles_existing)
            lines.append(f"\n[bold]Summary:[/bold] {total_created} created, {total_existing} already existed")
            
            if dry_run:
                lines.append("\n[yellow]This was a dry run - no changes were made[/yellow]")
            
            renderer.success("\n".join(lines), title="BOOTSTRAP COMPLETE")
        else:
            renderer.error(
                f"Bootstrap failed\n\n"
                f"Error: {inner.get('error', 'Unknown')}"
            )
    else:
        renderer.error(f"Request failed: {result.get('error', 'Unknown error')}")
    
    return "continue"

