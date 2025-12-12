#!/usr/bin/env python3
"""Register Discord MCP tools in the database.

Run this on the MCP server after deploying the Discord tools module.
"""

import os
import sys
import django

# Add the jexida_dashboard to the path
sys.path.insert(0, '/opt/jexida-mcp/jexida_dashboard')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jexida_dashboard.settings')

django.setup()

from mcp_tools_core.models import Tool

TOOLS = [
    # Get Guild Info
    {
        "name": "discord_get_guild_info",
        "description": "Get Discord guild (server) information. Retrieves basic info about a Discord server. Useful for testing connectivity.",
        "handler_path": "mcp_tools_core.tools.discord.api.discord_get_guild_info",
        "tags": "discord,guild,info",
        "input_schema": {
            "type": "object",
            "properties": {
                "guild_id": {
                    "type": "string",
                    "description": "Guild ID. If not provided, uses configured DISCORD_GUILD_ID"
                }
            },
            "required": []
        }
    },
    # Send Message
    {
        "name": "discord_send_message",
        "description": "Send a message to a Discord channel. Sends text content with optional embeds.",
        "handler_path": "mcp_tools_core.tools.discord.api.discord_send_message",
        "tags": "discord,message,chat",
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_id": {
                    "type": "string",
                    "description": "Target channel ID"
                },
                "content": {
                    "type": "string",
                    "description": "Message content"
                },
                "embeds": {
                    "type": "array",
                    "description": "Optional list of embed objects",
                    "items": {"type": "object"}
                }
            },
            "required": ["channel_id", "content"]
        }
    },
    # Create Text Channel
    {
        "name": "discord_create_text_channel",
        "description": "Create a text channel in a Discord guild. Optionally under a category.",
        "handler_path": "mcp_tools_core.tools.discord.api.discord_create_text_channel",
        "tags": "discord,channel,create",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Channel name (lowercase, no spaces)"
                },
                "guild_id": {
                    "type": "string",
                    "description": "Guild ID. If not provided, uses configured DISCORD_GUILD_ID"
                },
                "parent_id": {
                    "type": "string",
                    "description": "Parent category ID (optional)"
                },
                "topic": {
                    "type": "string",
                    "description": "Channel topic (optional)"
                }
            },
            "required": ["name"]
        }
    },
    # Create Category Channel
    {
        "name": "discord_create_category_channel",
        "description": "Create a category channel in a Discord guild. Categories can contain text channels.",
        "handler_path": "mcp_tools_core.tools.discord.api.discord_create_category_channel",
        "tags": "discord,category,create",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Category name"
                },
                "guild_id": {
                    "type": "string",
                    "description": "Guild ID. If not provided, uses configured DISCORD_GUILD_ID"
                }
            },
            "required": ["name"]
        }
    },
    # Ensure Role
    {
        "name": "discord_ensure_role",
        "description": "Ensure a role exists in a Discord guild. Creates the role if it doesn't exist, returns existing role otherwise. Idempotent operation.",
        "handler_path": "mcp_tools_core.tools.discord.api.discord_ensure_role",
        "tags": "discord,role,create",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Role name"
                },
                "guild_id": {
                    "type": "string",
                    "description": "Guild ID. If not provided, uses configured DISCORD_GUILD_ID"
                },
                "permissions": {
                    "type": "integer",
                    "description": "Permission bit set (optional)"
                },
                "color": {
                    "type": "integer",
                    "description": "Role color as integer (optional)"
                },
                "hoist": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether to display role separately in member list"
                }
            },
            "required": ["name"]
        }
    },
    # Bootstrap Server
    {
        "name": "discord_bootstrap_server",
        "description": "Bootstrap a Discord server from a YAML configuration. Creates categories, channels, and roles as defined in the spec. Idempotent - safe to run multiple times.",
        "handler_path": "mcp_tools_core.tools.discord.bootstrap.discord_bootstrap_server",
        "tags": "discord,bootstrap,setup,automation",
        "input_schema": {
            "type": "object",
            "properties": {
                "config_path": {
                    "type": "string",
                    "default": "config/discord_server.yml",
                    "description": "Path to YAML config file"
                },
                "guild_id": {
                    "type": "string",
                    "description": "Override guild ID from config or environment"
                },
                "dry_run": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, only report what would be done without making changes"
                }
            },
            "required": []
        }
    },
]


def main():
    print("Registering Discord MCP tools...")
    print("=" * 60)

    for tool_data in TOOLS:
        tool, created = Tool.objects.update_or_create(
            name=tool_data["name"],
            defaults={
                "description": tool_data["description"],
                "handler_path": tool_data["handler_path"],
                "tags": tool_data["tags"],
                "input_schema": tool_data["input_schema"],
                "is_active": True,
            }
        )
        action = "Created" if created else "Updated"
        print(f"  {action}: {tool.name}")

    print()
    print(f"Registered {len(TOOLS)} Discord tools successfully!")


if __name__ == "__main__":
    main()

