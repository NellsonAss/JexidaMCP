"""MCP Protocol Server for Cursor Integration.

This module provides an MCP-protocol-compliant server that exposes
the UniFi and Azure tools to Cursor and other MCP clients.

Uses the official MCP Python SDK with stdio transport.

IMPORTANT: All logging MUST go to stderr, not stdout!
The MCP protocol uses stdout for JSON-RPC communication.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

# CRITICAL: Configure logging to stderr BEFORE any other imports
# to prevent any module from accidentally logging to stdout
def setup_mcp_logging(level: str = "INFO") -> None:
    """Configure logging for MCP server - all output to stderr."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create handler that writes to stderr ONLY
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    
    # Configure root logger - remove any existing handlers first
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(numeric_level)
    root_logger.addHandler(handler)
    
    # Quiet down noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

# Set up logging IMMEDIATELY before any imports that might log
setup_mcp_logging("WARNING")  # Start quiet, will reconfigure after settings load

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Add the mcp_server_files directory to the path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import get_settings

# Reconfigure logging with actual settings
settings = get_settings()
setup_mcp_logging(settings.mcp_log_level)
logger = logging.getLogger(__name__)

# Create the MCP server instance
mcp = Server("jexida-mcp")


# -----------------------------------------------------------------------------
# Tool Definitions
# -----------------------------------------------------------------------------

def get_tool_definitions() -> list[Tool]:
    """Return the list of available MCP tools with their schemas."""
    return [
        # UniFi Tools
        Tool(
            name="unifi_list_devices",
            description="List all UniFi devices (gateways, switches, access points) from the controller",
            inputSchema={
                "type": "object",
                "properties": {
                    "site_id": {
                        "type": "string",
                        "description": "UniFi site ID (defaults to configured site)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="unifi_get_security_settings",
            description="Get comprehensive security settings from UniFi controller including WiFi, VLANs, firewall rules, remote access, and threat management",
            inputSchema={
                "type": "object",
                "properties": {
                    "site_id": {
                        "type": "string",
                        "description": "UniFi site ID (defaults to configured site)"
                    },
                    "include_firewall_rules": {
                        "type": "boolean",
                        "description": "Include detailed firewall rules",
                        "default": True
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="unifi_apply_changes",
            description="Apply configuration changes to UniFi controller with dry-run support",
            inputSchema={
                "type": "object",
                "properties": {
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, compute and return diff without applying changes",
                        "default": True
                    },
                    "site_id": {
                        "type": "string",
                        "description": "UniFi site ID (defaults to configured site)"
                    },
                    "wifi_edits": {
                        "type": "array",
                        "description": "WiFi/WLAN changes to apply",
                        "items": {
                            "type": "object",
                            "properties": {
                                "ssid": {"type": "string", "description": "SSID name to modify"},
                                "enabled": {"type": "boolean"},
                                "security": {"type": "string"},
                                "wpa_mode": {"type": "string"},
                                "wpa3_support": {"type": "boolean"},
                                "hide_ssid": {"type": "boolean"},
                                "l2_isolation": {"type": "boolean"}
                            },
                            "required": ["ssid"]
                        }
                    },
                    "firewall_edits": {
                        "type": "array",
                        "description": "Firewall rule changes to apply",
                        "items": {"type": "object"}
                    },
                    "vlan_edits": {
                        "type": "array",
                        "description": "VLAN/network changes to apply",
                        "items": {"type": "object"}
                    },
                    "upnp_edits": {
                        "type": "object",
                        "description": "UPnP setting changes",
                        "properties": {
                            "upnp_enabled": {"type": "boolean"},
                            "upnp_nat_pmp_enabled": {"type": "boolean"},
                            "upnp_secure_mode": {"type": "boolean"}
                        }
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="network_scan_local",
            description="Run a local network scan using nmap to discover devices and open ports",
            inputSchema={
                "type": "object",
                "properties": {
                    "subnets": {
                        "type": "array",
                        "description": "List of subnets to scan in CIDR notation (e.g., ['192.168.1.0/24'])",
                        "items": {"type": "string"}
                    },
                    "ports": {
                        "type": "string",
                        "description": "Port specification: 'top-100', 'top-1000', 'common', or port range like '1-1024'",
                        "default": "top-100"
                    }
                },
                "required": ["subnets"]
            }
        ),
        Tool(
            name="network_hardening_audit",
            description="Perform a comprehensive security audit of UniFi network configuration against best practices",
            inputSchema={
                "type": "object",
                "properties": {
                    "site_id": {
                        "type": "string",
                        "description": "UniFi site ID (defaults to configured site)"
                    },
                    "run_scan": {
                        "type": "boolean",
                        "description": "Also run a network scan to discover devices",
                        "default": False
                    },
                    "scan_subnets": {
                        "type": "array",
                        "description": "Subnets to scan if run_scan is True",
                        "items": {"type": "string"}
                    },
                    "policy_path": {
                        "type": "string",
                        "description": "Path to custom security policy JSON file"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="network_apply_hardening_plan",
            description="Apply a hardening plan from the security audit in controlled phases",
            inputSchema={
                "type": "object",
                "properties": {
                    "plan": {
                        "type": "object",
                        "description": "Hardening plan from network_hardening_audit recommended_changes",
                        "properties": {
                            "changes": {
                                "type": "array",
                                "items": {"type": "object"}
                            }
                        }
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Set to true to actually apply changes (false for preview)",
                        "default": False
                    },
                    "phased": {
                        "type": "boolean",
                        "description": "Apply changes in phases (true) or all at once (false)",
                        "default": True
                    },
                    "site_id": {
                        "type": "string",
                        "description": "UniFi site ID (defaults to configured site)"
                    },
                    "stop_on_failure": {
                        "type": "boolean",
                        "description": "Stop if a phase fails",
                        "default": True
                    }
                },
                "required": ["plan"]
            }
        ),
        # Azure Tools
        Tool(
            name="azure_cli_run",
            description="Execute an Azure CLI command safely with subscription context",
            inputSchema={
                "type": "object",
                "properties": {
                    "subscription_id": {
                        "type": "string",
                        "description": "Azure subscription ID (GUID format)"
                    },
                    "command": {
                        "type": "string",
                        "description": "Azure CLI command (everything after 'az', e.g., 'group list --output json')"
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, return the command that would be executed without running it",
                        "default": False
                    }
                },
                "required": ["subscription_id", "command"]
            }
        ),
        Tool(
            name="azure_cost_get_summary",
            description="Get Azure cost summary for a subscription or resource group",
            inputSchema={
                "type": "object",
                "properties": {
                    "subscription_id": {
                        "type": "string",
                        "description": "Azure subscription ID (GUID format)"
                    },
                    "resource_group": {
                        "type": "string",
                        "description": "Optional resource group to filter costs"
                    },
                    "time_period": {
                        "type": "string",
                        "description": "Time period: 'Last7Days', 'Last30Days', or 'MonthToDate'",
                        "enum": ["Last7Days", "Last30Days", "MonthToDate"],
                        "default": "Last30Days"
                    }
                },
                "required": ["subscription_id"]
            }
        ),
        Tool(
            name="http_health_probe",
            description="Perform HTTP health check on a URL endpoint",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to probe (must be http or https)"
                    },
                    "method": {
                        "type": "string",
                        "description": "HTTP method to use",
                        "default": "GET"
                    },
                    "expected_status": {
                        "type": "integer",
                        "description": "Expected HTTP status code for healthy response",
                        "default": 200
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Request timeout in seconds"
                    }
                },
                "required": ["url"]
            }
        ),
        # Synology NAS Tools - FileStation
        Tool(
            name="synology_list_files",
            description="List files and folders in a Synology NAS directory",
            inputSchema={
                "type": "object",
                "properties": {
                    "folder_path": {
                        "type": "string",
                        "description": "Folder path to list (e.g., /volume1/shared)",
                        "default": "/"
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Starting offset",
                        "default": 0
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum items to return",
                        "default": 100
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Sort field: name, size, mtime",
                        "default": "name"
                    },
                    "sort_direction": {
                        "type": "string",
                        "description": "Sort direction: asc, desc",
                        "default": "asc"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="synology_get_file_info",
            description="Get detailed information about a file or folder on Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to file or folder"
                    }
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="synology_create_folder",
            description="Create a new folder on Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {
                    "folder_path": {
                        "type": "string",
                        "description": "Parent folder path"
                    },
                    "name": {
                        "type": "string",
                        "description": "Name of new folder"
                    }
                },
                "required": ["folder_path", "name"]
            }
        ),
        Tool(
            name="synology_delete_files",
            description="Delete files or folders from Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "description": "List of paths to delete",
                        "items": {"type": "string"}
                    }
                },
                "required": ["paths"]
            }
        ),
        Tool(
            name="synology_move_files",
            description="Move files or folders to another location on Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "description": "Source paths to move",
                        "items": {"type": "string"}
                    },
                    "dest_folder": {
                        "type": "string",
                        "description": "Destination folder path"
                    },
                    "overwrite": {
                        "type": "boolean",
                        "description": "Overwrite existing files",
                        "default": False
                    }
                },
                "required": ["paths", "dest_folder"]
            }
        ),
        Tool(
            name="synology_rename_file",
            description="Rename a file or folder on Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to file/folder to rename"
                    },
                    "new_name": {
                        "type": "string",
                        "description": "New name"
                    }
                },
                "required": ["path", "new_name"]
            }
        ),
        Tool(
            name="synology_search_files",
            description="Search for files on Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {
                    "folder_path": {
                        "type": "string",
                        "description": "Folder to search in"
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Search pattern (supports wildcards)"
                    },
                    "extension": {
                        "type": "string",
                        "description": "Filter by file extension (e.g., 'txt', 'pdf')"
                    },
                    "file_type": {
                        "type": "string",
                        "description": "Filter by type: file, dir, or all",
                        "default": "all"
                    }
                },
                "required": ["folder_path", "pattern"]
            }
        ),
        # Synology NAS Tools - Download Station
        Tool(
            name="synology_list_downloads",
            description="List all download tasks in Synology Download Station",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="synology_add_download",
            description="Add a new download task to Synology Download Station (URL or magnet link)",
            inputSchema={
                "type": "object",
                "properties": {
                    "uri": {
                        "type": "string",
                        "description": "URL or magnet link to download"
                    },
                    "destination": {
                        "type": "string",
                        "description": "Destination folder path (optional)"
                    }
                },
                "required": ["uri"]
            }
        ),
        Tool(
            name="synology_pause_download",
            description="Pause a download task in Synology Download Station",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to pause"
                    }
                },
                "required": ["task_id"]
            }
        ),
        Tool(
            name="synology_resume_download",
            description="Resume a paused download task in Synology Download Station",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to resume"
                    }
                },
                "required": ["task_id"]
            }
        ),
        Tool(
            name="synology_delete_download",
            description="Delete a download task from Synology Download Station",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to delete"
                    },
                    "force_complete": {
                        "type": "boolean",
                        "description": "Delete even if download is not complete",
                        "default": False
                    }
                },
                "required": ["task_id"]
            }
        ),
        # Synology NAS Tools - System
        Tool(
            name="synology_get_system_info",
            description="Get system information from Synology NAS including CPU, memory, and uptime",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="synology_get_storage_info",
            description="Get storage volume information from Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="synology_get_network_info",
            description="Get network information from Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        # Synology NAS Tools - Users
        Tool(
            name="synology_list_users",
            description="List all user accounts on Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="synology_get_user_info",
            description="Get information about a specific user on Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Username to get info for"
                    }
                },
                "required": ["username"]
            }
        ),
        Tool(
            name="synology_create_user",
            description="Create a new user account on Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Username for new account"
                    },
                    "password": {
                        "type": "string",
                        "description": "Password for new account"
                    },
                    "description": {
                        "type": "string",
                        "description": "User description",
                        "default": ""
                    },
                    "email": {
                        "type": "string",
                        "description": "Email address",
                        "default": ""
                    }
                },
                "required": ["username", "password"]
            }
        ),
        Tool(
            name="synology_delete_user",
            description="Delete a user account from Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Username to delete"
                    }
                },
                "required": ["username"]
            }
        ),
        # Synology NAS Tools - Packages
        Tool(
            name="synology_list_packages",
            description="List DSM packages on Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {
                    "installed_only": {
                        "type": "boolean",
                        "description": "Only return installed packages",
                        "default": True
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="synology_install_package",
            description="Install a DSM package on Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {
                    "package_name": {
                        "type": "string",
                        "description": "Package ID/name to install"
                    }
                },
                "required": ["package_name"]
            }
        ),
        Tool(
            name="synology_uninstall_package",
            description="Uninstall a DSM package from Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {
                    "package_name": {
                        "type": "string",
                        "description": "Package ID/name to uninstall"
                    }
                },
                "required": ["package_name"]
            }
        ),
        # Synology NAS Tools - Surveillance Station
        Tool(
            name="synology_list_cameras",
            description="List all cameras in Synology Surveillance Station",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="synology_get_camera_info",
            description="Get information about a specific camera in Synology Surveillance Station",
            inputSchema={
                "type": "object",
                "properties": {
                    "camera_id": {
                        "type": "integer",
                        "description": "Camera ID"
                    }
                },
                "required": ["camera_id"]
            }
        ),
        Tool(
            name="synology_enable_camera",
            description="Enable or disable a camera in Synology Surveillance Station",
            inputSchema={
                "type": "object",
                "properties": {
                    "camera_id": {
                        "type": "integer",
                        "description": "Camera ID"
                    },
                    "enabled": {
                        "type": "boolean",
                        "description": "Enable (true) or disable (false) the camera",
                        "default": True
                    }
                },
                "required": ["camera_id"]
            }
        ),
        # Synology NAS Tools - Backup
        Tool(
            name="synology_list_backup_tasks",
            description="List Hyper Backup tasks on Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="synology_run_backup_task",
            description="Trigger a Hyper Backup task to run on Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "Backup task ID to run"
                    }
                },
                "required": ["task_id"]
            }
        ),
        Tool(
            name="synology_get_backup_status",
            description="Get the current status of a Hyper Backup task on Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "Backup task ID"
                    }
                },
                "required": ["task_id"]
            }
        ),
        # Synology NAS Tools - Groups
        Tool(
            name="synology_list_groups",
            description="List all user groups on Synology NAS",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="synology_get_group_info",
            description="Get information about a specific group including its members",
            inputSchema={
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Group name"}},
                "required": ["name"]
            }
        ),
        Tool(
            name="synology_create_group",
            description="Create a new user group on Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Group name"},
                    "description": {"type": "string", "description": "Group description", "default": ""}
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="synology_delete_group",
            description="Delete a user group from Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Group name to delete"}},
                "required": ["name"]
            }
        ),
        Tool(
            name="synology_add_group_member",
            description="Add a user to a group on Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {
                    "group_name": {"type": "string", "description": "Group name"},
                    "username": {"type": "string", "description": "Username to add"}
                },
                "required": ["group_name", "username"]
            }
        ),
        Tool(
            name="synology_remove_group_member",
            description="Remove a user from a group on Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {
                    "group_name": {"type": "string", "description": "Group name"},
                    "username": {"type": "string", "description": "Username to remove"}
                },
                "required": ["group_name", "username"]
            }
        ),
        # Synology NAS Tools - Shared Folders
        Tool(
            name="synology_list_shared_folders",
            description="List all shared folders on Synology NAS",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="synology_get_shared_folder_info",
            description="Get information about a specific shared folder on Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Shared folder name"}},
                "required": ["name"]
            }
        ),
        Tool(
            name="synology_create_shared_folder",
            description="Create a new shared folder on Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Shared folder name"},
                    "vol_path": {"type": "string", "description": "Volume path", "default": "/volume1"},
                    "desc": {"type": "string", "description": "Description", "default": ""},
                    "enable_recycle_bin": {"type": "boolean", "description": "Enable recycle bin", "default": True}
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="synology_delete_shared_folder",
            description="Delete a shared folder from Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Shared folder name to delete"}},
                "required": ["name"]
            }
        ),
        # Synology NAS Tools - Web Station
        Tool(
            name="synology_list_web_services",
            description="List all web services/virtual hosts in Synology Web Station",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="synology_list_php_profiles",
            description="List PHP profiles available in Synology Web Station",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="synology_get_webstation_status",
            description="Get Web Station status and configuration",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        # Synology NAS Tools - Network
        Tool(
            name="synology_get_network_config",
            description="Get network configuration from Synology NAS (hostname, DNS, gateway)",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="synology_list_network_interfaces",
            description="List network interfaces on Synology NAS",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        # Synology NAS Tools - Security
        Tool(
            name="synology_get_security_settings",
            description="Get security settings from Synology NAS",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="synology_list_firewall_rules",
            description="List firewall rules on Synology NAS",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="synology_get_autoblock_settings",
            description="Get auto-block settings from Synology NAS",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="synology_list_blocked_ips",
            description="List blocked IP addresses on Synology NAS",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="synology_run_security_scan",
            description="Run a security advisor scan on Synology NAS",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        # Synology NAS Tools - Task Scheduler
        Tool(
            name="synology_list_scheduled_tasks",
            description="List scheduled tasks on Synology NAS",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="synology_run_scheduled_task",
            description="Run a scheduled task immediately on Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {"task_id": {"type": "integer", "description": "Task ID to run"}},
                "required": ["task_id"]
            }
        ),
        Tool(
            name="synology_enable_scheduled_task",
            description="Enable or disable a scheduled task on Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "Task ID"},
                    "enabled": {"type": "boolean", "description": "Enable or disable", "default": True}
                },
                "required": ["task_id"]
            }
        ),
        # Synology NAS Tools - Docker
        Tool(
            name="synology_list_docker_containers",
            description="List Docker containers on Synology NAS",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="synology_get_docker_container_info",
            description="Get detailed information about a Docker container",
            inputSchema={
                "type": "object",
                "properties": {"container_id": {"type": "string", "description": "Container ID"}},
                "required": ["container_id"]
            }
        ),
        Tool(
            name="synology_start_docker_container",
            description="Start a Docker container on Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {"container_id": {"type": "string", "description": "Container ID to start"}},
                "required": ["container_id"]
            }
        ),
        Tool(
            name="synology_stop_docker_container",
            description="Stop a Docker container on Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {"container_id": {"type": "string", "description": "Container ID to stop"}},
                "required": ["container_id"]
            }
        ),
        Tool(
            name="synology_restart_docker_container",
            description="Restart a Docker container on Synology NAS",
            inputSchema={
                "type": "object",
                "properties": {"container_id": {"type": "string", "description": "Container ID to restart"}},
                "required": ["container_id"]
            }
        ),
        Tool(
            name="synology_list_docker_images",
            description="List Docker images on Synology NAS",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        # Synology NAS Tools - Virtual Machine Manager
        Tool(
            name="synology_list_virtual_machines",
            description="List virtual machines in Synology Virtual Machine Manager",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="synology_get_vm_info",
            description="Get detailed information about a virtual machine",
            inputSchema={
                "type": "object",
                "properties": {"guest_id": {"type": "string", "description": "VM ID"}},
                "required": ["guest_id"]
            }
        ),
        Tool(
            name="synology_start_vm",
            description="Start a virtual machine in Synology Virtual Machine Manager",
            inputSchema={
                "type": "object",
                "properties": {"guest_id": {"type": "string", "description": "VM ID to start"}},
                "required": ["guest_id"]
            }
        ),
        Tool(
            name="synology_stop_vm",
            description="Stop a virtual machine in Synology Virtual Machine Manager",
            inputSchema={
                "type": "object",
                "properties": {
                    "guest_id": {"type": "string", "description": "VM ID to stop"},
                    "force": {"type": "boolean", "description": "Force power off", "default": False}
                },
                "required": ["guest_id"]
            }
        ),
        # Synology NAS Tools - Monitoring
        Tool(
            name="synology_list_logs",
            description="List system logs from Synology NAS Log Center",
            inputSchema={
                "type": "object",
                "properties": {
                    "log_type": {"type": "string", "description": "Log type: connection, transfer, etc.", "default": "connection"},
                    "offset": {"type": "integer", "description": "Starting offset", "default": 0},
                    "limit": {"type": "integer", "description": "Maximum logs to return", "default": 100}
                },
                "required": []
            }
        ),
        Tool(
            name="synology_get_resource_usage",
            description="Get current resource usage from Synology NAS (CPU, memory, disk, network)",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="synology_list_photo_albums",
            description="List photo albums in Synology Photos",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="synology_get_drive_status",
            description="Get Synology Drive status and version",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="synology_list_drive_team_folders",
            description="List Synology Drive team folders",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
    ]


# -----------------------------------------------------------------------------
# MCP Protocol Handlers
# -----------------------------------------------------------------------------

@mcp.list_tools()
async def list_tools() -> list[Tool]:
    """Return the list of available tools."""
    return get_tool_definitions()


@mcp.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute a tool and return the result."""
    import json
    
    logger.info(f"Calling tool: {name} with arguments: {arguments}")
    
    try:
        result = await execute_tool(name, arguments)
        
        # Convert result to JSON string for MCP response
        if hasattr(result, 'model_dump'):
            result_dict = result.model_dump()
        elif isinstance(result, dict):
            result_dict = result
        else:
            result_dict = {"result": str(result)}
        
        return [TextContent(
            type="text",
            text=json.dumps(result_dict, indent=2, default=str)
        )]
        
    except Exception as e:
        logger.error(f"Tool execution failed: {name}", exc_info=True)
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
        )]


async def execute_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Execute the specified tool with the given arguments."""
    
    # Ensure logging goes to stderr before importing tools
    # (tools may reconfigure logging on import)
    setup_mcp_logging(settings.mcp_log_level)
    
    # Import tools lazily to avoid circular imports
    # UniFi tools
    if name == "unifi_list_devices":
        from mcp_tools.unifi.devices import unifi_list_devices, UniFiListDevicesInput
        params = UniFiListDevicesInput(**arguments)
        return await unifi_list_devices(params)
    
    elif name == "unifi_get_security_settings":
        from mcp_tools.unifi.security import unifi_get_security_settings, UniFiSecuritySettingsInput
        params = UniFiSecuritySettingsInput(**arguments)
        return await unifi_get_security_settings(params)
    
    elif name == "unifi_apply_changes":
        from mcp_tools.unifi.changes import unifi_apply_changes, UniFiApplyChangesInput
        params = UniFiApplyChangesInput(**arguments)
        return await unifi_apply_changes(params)
    
    elif name == "network_scan_local":
        from mcp_tools.unifi.network_scan import network_scan_local, NetworkScanInput
        params = NetworkScanInput(**arguments)
        return await network_scan_local(params)
    
    elif name == "network_hardening_audit":
        from mcp_tools.unifi.audit import network_hardening_audit, NetworkHardeningAuditInput
        params = NetworkHardeningAuditInput(**arguments)
        return await network_hardening_audit(params)
    
    elif name == "network_apply_hardening_plan":
        from mcp_tools.unifi.hardening import network_apply_hardening_plan, NetworkApplyHardeningPlanInput, HardeningPlan
        # Need to reconstruct the plan object
        plan_data = arguments.get("plan", {})
        arguments["plan"] = HardeningPlan(**plan_data)
        params = NetworkApplyHardeningPlanInput(**arguments)
        return await network_apply_hardening_plan(params)
    
    # Azure tools
    elif name == "azure_cli_run":
        from mcp_tools.azure.cli import run_azure_cli, AzureCliInput
        params = AzureCliInput(**arguments)
        return await run_azure_cli(params)
    
    elif name == "azure_cost_get_summary":
        from mcp_tools.azure.cost import get_cost_summary, AzureCostInput, TimePeriod
        # Convert time_period string to enum
        if "time_period" in arguments:
            arguments["time_period"] = TimePeriod(arguments["time_period"])
        params = AzureCostInput(**arguments)
        return await get_cost_summary(params)
    
    elif name == "http_health_probe":
        from mcp_tools.azure.monitor import http_health_probe, HttpHealthProbeInput
        params = HttpHealthProbeInput(**arguments)
        return await http_health_probe(params)
    
    # Synology FileStation tools
    elif name == "synology_list_files":
        from mcp_tools.synology.filestation import synology_list_files, SynologyListFilesInput
        params = SynologyListFilesInput(**arguments)
        return await synology_list_files(params)
    
    elif name == "synology_get_file_info":
        from mcp_tools.synology.filestation import synology_get_file_info, SynologyGetFileInfoInput
        params = SynologyGetFileInfoInput(**arguments)
        return await synology_get_file_info(params)
    
    elif name == "synology_create_folder":
        from mcp_tools.synology.filestation import synology_create_folder, SynologyCreateFolderInput
        params = SynologyCreateFolderInput(**arguments)
        return await synology_create_folder(params)
    
    elif name == "synology_delete_files":
        from mcp_tools.synology.filestation import synology_delete_files, SynologyDeleteFilesInput
        params = SynologyDeleteFilesInput(**arguments)
        return await synology_delete_files(params)
    
    elif name == "synology_move_files":
        from mcp_tools.synology.filestation import synology_move_files, SynologyMoveFilesInput
        params = SynologyMoveFilesInput(**arguments)
        return await synology_move_files(params)
    
    elif name == "synology_rename_file":
        from mcp_tools.synology.filestation import synology_rename_file, SynologyRenameFileInput
        params = SynologyRenameFileInput(**arguments)
        return await synology_rename_file(params)
    
    elif name == "synology_search_files":
        from mcp_tools.synology.filestation import synology_search_files, SynologySearchFilesInput
        params = SynologySearchFilesInput(**arguments)
        return await synology_search_files(params)
    
    # Synology Download Station tools
    elif name == "synology_list_downloads":
        from mcp_tools.synology.download_station import synology_list_downloads, SynologyListDownloadsInput
        params = SynologyListDownloadsInput(**arguments)
        return await synology_list_downloads(params)
    
    elif name == "synology_add_download":
        from mcp_tools.synology.download_station import synology_add_download, SynologyAddDownloadInput
        params = SynologyAddDownloadInput(**arguments)
        return await synology_add_download(params)
    
    elif name == "synology_pause_download":
        from mcp_tools.synology.download_station import synology_pause_download, SynologyPauseDownloadInput
        params = SynologyPauseDownloadInput(**arguments)
        return await synology_pause_download(params)
    
    elif name == "synology_resume_download":
        from mcp_tools.synology.download_station import synology_resume_download, SynologyResumeDownloadInput
        params = SynologyResumeDownloadInput(**arguments)
        return await synology_resume_download(params)
    
    elif name == "synology_delete_download":
        from mcp_tools.synology.download_station import synology_delete_download, SynologyDeleteDownloadInput
        params = SynologyDeleteDownloadInput(**arguments)
        return await synology_delete_download(params)
    
    # Synology System tools
    elif name == "synology_get_system_info":
        from mcp_tools.synology.system import synology_get_system_info, SynologyGetSystemInfoInput
        params = SynologyGetSystemInfoInput(**arguments)
        return await synology_get_system_info(params)
    
    elif name == "synology_get_storage_info":
        from mcp_tools.synology.system import synology_get_storage_info, SynologyGetStorageInfoInput
        params = SynologyGetStorageInfoInput(**arguments)
        return await synology_get_storage_info(params)
    
    elif name == "synology_get_network_info":
        from mcp_tools.synology.system import synology_get_network_info, SynologyGetNetworkInfoInput
        params = SynologyGetNetworkInfoInput(**arguments)
        return await synology_get_network_info(params)
    
    # Synology User tools
    elif name == "synology_list_users":
        from mcp_tools.synology.users import synology_list_users, SynologyListUsersInput
        params = SynologyListUsersInput(**arguments)
        return await synology_list_users(params)
    
    elif name == "synology_get_user_info":
        from mcp_tools.synology.users import synology_get_user_info, SynologyGetUserInfoInput
        params = SynologyGetUserInfoInput(**arguments)
        return await synology_get_user_info(params)
    
    elif name == "synology_create_user":
        from mcp_tools.synology.users import synology_create_user, SynologyCreateUserInput
        params = SynologyCreateUserInput(**arguments)
        return await synology_create_user(params)
    
    elif name == "synology_delete_user":
        from mcp_tools.synology.users import synology_delete_user, SynologyDeleteUserInput
        params = SynologyDeleteUserInput(**arguments)
        return await synology_delete_user(params)
    
    # Synology Package tools
    elif name == "synology_list_packages":
        from mcp_tools.synology.packages import synology_list_packages, SynologyListPackagesInput
        params = SynologyListPackagesInput(**arguments)
        return await synology_list_packages(params)
    
    elif name == "synology_install_package":
        from mcp_tools.synology.packages import synology_install_package, SynologyInstallPackageInput
        params = SynologyInstallPackageInput(**arguments)
        return await synology_install_package(params)
    
    elif name == "synology_uninstall_package":
        from mcp_tools.synology.packages import synology_uninstall_package, SynologyUninstallPackageInput
        params = SynologyUninstallPackageInput(**arguments)
        return await synology_uninstall_package(params)
    
    # Synology Surveillance Station tools
    elif name == "synology_list_cameras":
        from mcp_tools.synology.surveillance import synology_list_cameras, SynologyListCamerasInput
        params = SynologyListCamerasInput(**arguments)
        return await synology_list_cameras(params)
    
    elif name == "synology_get_camera_info":
        from mcp_tools.synology.surveillance import synology_get_camera_info, SynologyGetCameraInfoInput
        params = SynologyGetCameraInfoInput(**arguments)
        return await synology_get_camera_info(params)
    
    elif name == "synology_enable_camera":
        from mcp_tools.synology.surveillance import synology_enable_camera, SynologyEnableCameraInput
        params = SynologyEnableCameraInput(**arguments)
        return await synology_enable_camera(params)
    
    # Synology Backup tools
    elif name == "synology_list_backup_tasks":
        from mcp_tools.synology.backup import synology_list_backup_tasks, SynologyListBackupTasksInput
        params = SynologyListBackupTasksInput(**arguments)
        return await synology_list_backup_tasks(params)
    
    elif name == "synology_run_backup_task":
        from mcp_tools.synology.backup import synology_run_backup_task, SynologyRunBackupTaskInput
        params = SynologyRunBackupTaskInput(**arguments)
        return await synology_run_backup_task(params)
    
    elif name == "synology_get_backup_status":
        from mcp_tools.synology.backup import synology_get_backup_status, SynologyGetBackupStatusInput
        params = SynologyGetBackupStatusInput(**arguments)
        return await synology_get_backup_status(params)
    
    # Synology Group tools
    elif name == "synology_list_groups":
        from mcp_tools.synology.groups import synology_list_groups, SynologyListGroupsInput
        params = SynologyListGroupsInput(**arguments)
        return await synology_list_groups(params)
    
    elif name == "synology_get_group_info":
        from mcp_tools.synology.groups import synology_get_group_info, SynologyGetGroupInfoInput
        params = SynologyGetGroupInfoInput(**arguments)
        return await synology_get_group_info(params)
    
    elif name == "synology_create_group":
        from mcp_tools.synology.groups import synology_create_group, SynologyCreateGroupInput
        params = SynologyCreateGroupInput(**arguments)
        return await synology_create_group(params)
    
    elif name == "synology_delete_group":
        from mcp_tools.synology.groups import synology_delete_group, SynologyDeleteGroupInput
        params = SynologyDeleteGroupInput(**arguments)
        return await synology_delete_group(params)
    
    elif name == "synology_add_group_member":
        from mcp_tools.synology.groups import synology_add_group_member, SynologyAddGroupMemberInput
        params = SynologyAddGroupMemberInput(**arguments)
        return await synology_add_group_member(params)
    
    elif name == "synology_remove_group_member":
        from mcp_tools.synology.groups import synology_remove_group_member, SynologyRemoveGroupMemberInput
        params = SynologyRemoveGroupMemberInput(**arguments)
        return await synology_remove_group_member(params)
    
    # Synology Shared Folder tools
    elif name == "synology_list_shared_folders":
        from mcp_tools.synology.shared_folders import synology_list_shared_folders, SynologyListSharedFoldersInput
        params = SynologyListSharedFoldersInput(**arguments)
        return await synology_list_shared_folders(params)
    
    elif name == "synology_get_shared_folder_info":
        from mcp_tools.synology.shared_folders import synology_get_shared_folder_info, SynologyGetSharedFolderInfoInput
        params = SynologyGetSharedFolderInfoInput(**arguments)
        return await synology_get_shared_folder_info(params)
    
    elif name == "synology_create_shared_folder":
        from mcp_tools.synology.shared_folders import synology_create_shared_folder, SynologyCreateSharedFolderInput
        params = SynologyCreateSharedFolderInput(**arguments)
        return await synology_create_shared_folder(params)
    
    elif name == "synology_delete_shared_folder":
        from mcp_tools.synology.shared_folders import synology_delete_shared_folder, SynologyDeleteSharedFolderInput
        params = SynologyDeleteSharedFolderInput(**arguments)
        return await synology_delete_shared_folder(params)
    
    # Synology Web Station tools
    elif name == "synology_list_web_services":
        from mcp_tools.synology.webstation import synology_list_web_services, SynologyListWebServicesInput
        params = SynologyListWebServicesInput(**arguments)
        return await synology_list_web_services(params)
    
    elif name == "synology_list_php_profiles":
        from mcp_tools.synology.webstation import synology_list_php_profiles, SynologyListPhpProfilesInput
        params = SynologyListPhpProfilesInput(**arguments)
        return await synology_list_php_profiles(params)
    
    elif name == "synology_get_webstation_status":
        from mcp_tools.synology.webstation import synology_get_webstation_status, SynologyGetWebstationStatusInput
        params = SynologyGetWebstationStatusInput(**arguments)
        return await synology_get_webstation_status(params)
    
    # Synology Network tools
    elif name == "synology_get_network_config":
        from mcp_tools.synology.network import synology_get_network_config, SynologyGetNetworkConfigInput
        params = SynologyGetNetworkConfigInput(**arguments)
        return await synology_get_network_config(params)
    
    elif name == "synology_list_network_interfaces":
        from mcp_tools.synology.network import synology_list_network_interfaces, SynologyListNetworkInterfacesInput
        params = SynologyListNetworkInterfacesInput(**arguments)
        return await synology_list_network_interfaces(params)
    
    # Synology Security tools
    elif name == "synology_get_security_settings":
        from mcp_tools.synology.security import synology_get_security_settings, SynologyGetSecuritySettingsInput
        params = SynologyGetSecuritySettingsInput(**arguments)
        return await synology_get_security_settings(params)
    
    elif name == "synology_list_firewall_rules":
        from mcp_tools.synology.security import synology_list_firewall_rules, SynologyListFirewallRulesInput
        params = SynologyListFirewallRulesInput(**arguments)
        return await synology_list_firewall_rules(params)
    
    elif name == "synology_get_autoblock_settings":
        from mcp_tools.synology.security import synology_get_autoblock_settings, SynologyGetAutoblockSettingsInput
        params = SynologyGetAutoblockSettingsInput(**arguments)
        return await synology_get_autoblock_settings(params)
    
    elif name == "synology_list_blocked_ips":
        from mcp_tools.synology.security import synology_list_blocked_ips, SynologyListBlockedIpsInput
        params = SynologyListBlockedIpsInput(**arguments)
        return await synology_list_blocked_ips(params)
    
    elif name == "synology_run_security_scan":
        from mcp_tools.synology.security import synology_run_security_scan, SynologyRunSecurityScanInput
        params = SynologyRunSecurityScanInput(**arguments)
        return await synology_run_security_scan(params)
    
    # Synology Task Scheduler tools
    elif name == "synology_list_scheduled_tasks":
        from mcp_tools.synology.tasks import synology_list_scheduled_tasks, SynologyListScheduledTasksInput
        params = SynologyListScheduledTasksInput(**arguments)
        return await synology_list_scheduled_tasks(params)
    
    elif name == "synology_run_scheduled_task":
        from mcp_tools.synology.tasks import synology_run_scheduled_task, SynologyRunScheduledTaskInput
        params = SynologyRunScheduledTaskInput(**arguments)
        return await synology_run_scheduled_task(params)
    
    elif name == "synology_enable_scheduled_task":
        from mcp_tools.synology.tasks import synology_enable_scheduled_task, SynologyEnableScheduledTaskInput
        params = SynologyEnableScheduledTaskInput(**arguments)
        return await synology_enable_scheduled_task(params)
    
    # Synology Docker tools
    elif name == "synology_list_docker_containers":
        from mcp_tools.synology.docker import synology_list_docker_containers, SynologyListDockerContainersInput
        params = SynologyListDockerContainersInput(**arguments)
        return await synology_list_docker_containers(params)
    
    elif name == "synology_get_docker_container_info":
        from mcp_tools.synology.docker import synology_get_docker_container_info, SynologyGetDockerContainerInfoInput
        params = SynologyGetDockerContainerInfoInput(**arguments)
        return await synology_get_docker_container_info(params)
    
    elif name == "synology_start_docker_container":
        from mcp_tools.synology.docker import synology_start_docker_container, SynologyStartDockerContainerInput
        params = SynologyStartDockerContainerInput(**arguments)
        return await synology_start_docker_container(params)
    
    elif name == "synology_stop_docker_container":
        from mcp_tools.synology.docker import synology_stop_docker_container, SynologyStopDockerContainerInput
        params = SynologyStopDockerContainerInput(**arguments)
        return await synology_stop_docker_container(params)
    
    elif name == "synology_restart_docker_container":
        from mcp_tools.synology.docker import synology_restart_docker_container, SynologyRestartDockerContainerInput
        params = SynologyRestartDockerContainerInput(**arguments)
        return await synology_restart_docker_container(params)
    
    elif name == "synology_list_docker_images":
        from mcp_tools.synology.docker import synology_list_docker_images, SynologyListDockerImagesInput
        params = SynologyListDockerImagesInput(**arguments)
        return await synology_list_docker_images(params)
    
    # Synology Virtual Machine Manager tools
    elif name == "synology_list_virtual_machines":
        from mcp_tools.synology.virtualization import synology_list_virtual_machines, SynologyListVirtualMachinesInput
        params = SynologyListVirtualMachinesInput(**arguments)
        return await synology_list_virtual_machines(params)
    
    elif name == "synology_get_vm_info":
        from mcp_tools.synology.virtualization import synology_get_vm_info, SynologyGetVmInfoInput
        params = SynologyGetVmInfoInput(**arguments)
        return await synology_get_vm_info(params)
    
    elif name == "synology_start_vm":
        from mcp_tools.synology.virtualization import synology_start_vm, SynologyStartVmInput
        params = SynologyStartVmInput(**arguments)
        return await synology_start_vm(params)
    
    elif name == "synology_stop_vm":
        from mcp_tools.synology.virtualization import synology_stop_vm, SynologyStopVmInput
        params = SynologyStopVmInput(**arguments)
        return await synology_stop_vm(params)
    
    # Synology Monitoring tools
    elif name == "synology_list_logs":
        from mcp_tools.synology.monitoring import synology_list_logs, SynologyListLogsInput
        params = SynologyListLogsInput(**arguments)
        return await synology_list_logs(params)
    
    elif name == "synology_get_resource_usage":
        from mcp_tools.synology.monitoring import synology_get_resource_usage, SynologyGetResourceUsageInput
        params = SynologyGetResourceUsageInput(**arguments)
        return await synology_get_resource_usage(params)
    
    elif name == "synology_list_photo_albums":
        from mcp_tools.synology.monitoring import synology_list_photo_albums, SynologyListPhotoAlbumsInput
        params = SynologyListPhotoAlbumsInput(**arguments)
        return await synology_list_photo_albums(params)
    
    elif name == "synology_get_drive_status":
        from mcp_tools.synology.monitoring import synology_get_drive_status, SynologyGetDriveStatusInput
        params = SynologyGetDriveStatusInput(**arguments)
        return await synology_get_drive_status(params)
    
    elif name == "synology_list_drive_team_folders":
        from mcp_tools.synology.monitoring import synology_list_drive_team_folders, SynologyListDriveTeamFoldersInput
        params = SynologyListDriveTeamFoldersInput(**arguments)
        return await synology_list_drive_team_folders(params)
    
    else:
        raise ValueError(f"Unknown tool: {name}")


# -----------------------------------------------------------------------------
# Main Entry Point
# -----------------------------------------------------------------------------

async def main():
    """Run the MCP server using stdio transport."""
    logger.info("Starting Jexida MCP Server (stdio transport)")
    
    async with stdio_server() as (read_stream, write_stream):
        await mcp.run(
            read_stream,
            write_stream,
            mcp.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())


