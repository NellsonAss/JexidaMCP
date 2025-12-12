"""Seed migration to populate Tool records from existing definitions.

This migration creates Tool records for all the tools that were previously
defined in the FastAPI MCP server (mcp_server_files/mcp_server.py).
"""

from django.db import migrations


def seed_tools(apps, schema_editor):
    """Create initial Tool records."""
    Tool = apps.get_model("mcp_tools_core", "Tool")
    
    tools_to_create = [
        # UniFi Tools
        {
            "name": "unifi_list_devices",
            "description": "List all UniFi devices (gateways, switches, access points) from the controller",
            "input_schema": {
                "type": "object",
                "properties": {
                    "site_id": {
                        "type": "string",
                        "description": "UniFi site ID (defaults to configured site)"
                    }
                },
                "required": []
            },
            "handler_path": "mcp_tools_core.tools.unifi.devices.unifi_list_devices",
            "tags": "unifi,network,inventory",
        },
        {
            "name": "unifi_get_security_settings",
            "description": "Get comprehensive security settings from UniFi controller including WiFi, VLANs, firewall rules, remote access, and threat management",
            "input_schema": {
                "type": "object",
                "properties": {
                    "site_id": {"type": "string", "description": "UniFi site ID"},
                    "include_firewall_rules": {"type": "boolean", "description": "Include detailed firewall rules", "default": True}
                },
                "required": []
            },
            "handler_path": "mcp_tools_core.tools.unifi.security.unifi_get_security_settings",
            "tags": "unifi,network,security",
        },
        {
            "name": "unifi_apply_changes",
            "description": "Apply configuration changes to UniFi controller with dry-run support",
            "input_schema": {
                "type": "object",
                "properties": {
                    "dry_run": {"type": "boolean", "default": True},
                    "site_id": {"type": "string"},
                    "wifi_edits": {"type": "array", "items": {"type": "object"}},
                    "firewall_edits": {"type": "array", "items": {"type": "object"}},
                    "vlan_edits": {"type": "array", "items": {"type": "object"}},
                    "upnp_edits": {"type": "object"}
                },
                "required": []
            },
            "handler_path": "mcp_tools_core.tools.unifi.changes.unifi_apply_changes",
            "tags": "unifi,network,configuration",
        },
        {
            "name": "network_scan_local",
            "description": "Run a local network scan using nmap to discover devices and open ports",
            "input_schema": {
                "type": "object",
                "properties": {
                    "subnets": {"type": "array", "items": {"type": "string"}, "description": "Subnets to scan in CIDR notation"},
                    "ports": {"type": "string", "description": "Port specification: 'top-100', 'top-1000', 'common', or port range", "default": "top-100"}
                },
                "required": ["subnets"]
            },
            "handler_path": "mcp_tools_core.tools.unifi.network_scan.network_scan_local",
            "tags": "network,security,scan",
        },
        {
            "name": "network_hardening_audit",
            "description": "Perform a comprehensive security audit of UniFi network configuration against best practices",
            "input_schema": {
                "type": "object",
                "properties": {
                    "site_id": {"type": "string"},
                    "run_scan": {"type": "boolean", "default": False},
                    "scan_subnets": {"type": "array", "items": {"type": "string"}},
                    "policy_path": {"type": "string"}
                },
                "required": []
            },
            "handler_path": "mcp_tools_core.tools.unifi.audit.network_hardening_audit",
            "tags": "unifi,network,security,audit",
        },
        {
            "name": "network_apply_hardening_plan",
            "description": "Apply a hardening plan from the security audit in controlled phases",
            "input_schema": {
                "type": "object",
                "properties": {
                    "plan": {"type": "object", "description": "Hardening plan from audit"},
                    "confirm": {"type": "boolean", "default": False},
                    "phased": {"type": "boolean", "default": True},
                    "site_id": {"type": "string"},
                    "stop_on_failure": {"type": "boolean", "default": True}
                },
                "required": ["plan"]
            },
            "handler_path": "mcp_tools_core.tools.unifi.hardening.network_apply_hardening_plan",
            "tags": "unifi,network,security,hardening",
        },
        # Azure Tools
        {
            "name": "azure_cli_run",
            "description": "Execute an Azure CLI command safely with subscription context",
            "input_schema": {
                "type": "object",
                "properties": {
                    "subscription_id": {"type": "string", "description": "Azure subscription ID (GUID)"},
                    "command": {"type": "string", "description": "Azure CLI command after 'az'"},
                    "dry_run": {"type": "boolean", "default": False}
                },
                "required": ["subscription_id", "command"]
            },
            "handler_path": "mcp_tools_core.tools.azure.cli.azure_cli_run",
            "tags": "azure,cli",
        },
        {
            "name": "azure_cost_get_summary",
            "description": "Get Azure cost summary for a subscription or resource group",
            "input_schema": {
                "type": "object",
                "properties": {
                    "subscription_id": {"type": "string"},
                    "resource_group": {"type": "string"},
                    "time_period": {"type": "string", "enum": ["Last7Days", "Last30Days", "MonthToDate"], "default": "Last30Days"}
                },
                "required": ["subscription_id"]
            },
            "handler_path": "mcp_tools_core.tools.azure.cost.azure_cost_get_summary",
            "tags": "azure,cost,billing",
        },
        {
            "name": "http_health_probe",
            "description": "Perform HTTP health check on a URL endpoint",
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to probe (http/https)"},
                    "method": {"type": "string", "default": "GET"},
                    "expected_status": {"type": "integer", "default": 200},
                    "timeout_seconds": {"type": "integer"}
                },
                "required": ["url"]
            },
            "handler_path": "mcp_tools_core.tools.azure.monitor.http_health_probe",
            "tags": "monitoring,health,http",
        },
        # Synology FileStation Tools
        {
            "name": "synology_list_files",
            "description": "List files and folders in a Synology NAS directory",
            "input_schema": {
                "type": "object",
                "properties": {
                    "folder_path": {"type": "string", "default": "/"},
                    "offset": {"type": "integer", "default": 0},
                    "limit": {"type": "integer", "default": 100},
                    "sort_by": {"type": "string", "default": "name"},
                    "sort_direction": {"type": "string", "default": "asc"}
                },
                "required": []
            },
            "handler_path": "mcp_tools_core.tools.synology.filestation.synology_list_files",
            "tags": "synology,nas,filestation",
        },
        {
            "name": "synology_get_file_info",
            "description": "Get detailed information about a file or folder on Synology NAS",
            "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            "handler_path": "mcp_tools_core.tools.synology.filestation.synology_get_file_info",
            "tags": "synology,nas,filestation",
        },
        {
            "name": "synology_create_folder",
            "description": "Create a new folder on Synology NAS",
            "input_schema": {"type": "object", "properties": {"folder_path": {"type": "string"}, "name": {"type": "string"}}, "required": ["folder_path", "name"]},
            "handler_path": "mcp_tools_core.tools.synology.filestation.synology_create_folder",
            "tags": "synology,nas,filestation",
        },
        {
            "name": "synology_delete_files",
            "description": "Delete files or folders from Synology NAS",
            "input_schema": {"type": "object", "properties": {"paths": {"type": "array", "items": {"type": "string"}}}, "required": ["paths"]},
            "handler_path": "mcp_tools_core.tools.synology.filestation.synology_delete_files",
            "tags": "synology,nas,filestation",
        },
        {
            "name": "synology_move_files",
            "description": "Move files or folders to another location on Synology NAS",
            "input_schema": {"type": "object", "properties": {"paths": {"type": "array", "items": {"type": "string"}}, "dest_folder": {"type": "string"}, "overwrite": {"type": "boolean", "default": False}}, "required": ["paths", "dest_folder"]},
            "handler_path": "mcp_tools_core.tools.synology.filestation.synology_move_files",
            "tags": "synology,nas,filestation",
        },
        {
            "name": "synology_search_files",
            "description": "Search for files on Synology NAS",
            "input_schema": {"type": "object", "properties": {"folder_path": {"type": "string"}, "pattern": {"type": "string"}, "extension": {"type": "string"}, "file_type": {"type": "string", "default": "all"}}, "required": ["folder_path", "pattern"]},
            "handler_path": "mcp_tools_core.tools.synology.filestation.synology_search_files",
            "tags": "synology,nas,filestation",
        },
        # Synology System Tools
        {
            "name": "synology_get_system_info",
            "description": "Get system information from Synology NAS including CPU, memory, and uptime",
            "input_schema": {"type": "object", "properties": {}, "required": []},
            "handler_path": "mcp_tools_core.tools.synology.system.synology_get_system_info",
            "tags": "synology,nas,system",
        },
        {
            "name": "synology_get_storage_info",
            "description": "Get storage volume information from Synology NAS",
            "input_schema": {"type": "object", "properties": {}, "required": []},
            "handler_path": "mcp_tools_core.tools.synology.system.synology_get_storage_info",
            "tags": "synology,nas,storage",
        },
        {
            "name": "synology_get_network_info",
            "description": "Get network information from Synology NAS",
            "input_schema": {"type": "object", "properties": {}, "required": []},
            "handler_path": "mcp_tools_core.tools.synology.system.synology_get_network_info",
            "tags": "synology,nas,network",
        },
        # Synology User Tools
        {
            "name": "synology_list_users",
            "description": "List all user accounts on Synology NAS",
            "input_schema": {"type": "object", "properties": {}, "required": []},
            "handler_path": "mcp_tools_core.tools.synology.users.synology_list_users",
            "tags": "synology,nas,users",
        },
        {
            "name": "synology_get_user_info",
            "description": "Get information about a specific user on Synology NAS",
            "input_schema": {"type": "object", "properties": {"username": {"type": "string"}}, "required": ["username"]},
            "handler_path": "mcp_tools_core.tools.synology.users.synology_get_user_info",
            "tags": "synology,nas,users",
        },
        {
            "name": "synology_create_user",
            "description": "Create a new user account on Synology NAS",
            "input_schema": {"type": "object", "properties": {"username": {"type": "string"}, "password": {"type": "string"}, "description": {"type": "string"}, "email": {"type": "string"}}, "required": ["username", "password"]},
            "handler_path": "mcp_tools_core.tools.synology.users.synology_create_user",
            "tags": "synology,nas,users",
        },
        # Synology Docker Tools
        {
            "name": "synology_list_docker_containers",
            "description": "List Docker containers on Synology NAS",
            "input_schema": {"type": "object", "properties": {}, "required": []},
            "handler_path": "mcp_tools_core.tools.synology.docker.synology_list_docker_containers",
            "tags": "synology,nas,docker",
        },
        {
            "name": "synology_start_docker_container",
            "description": "Start a Docker container on Synology NAS",
            "input_schema": {"type": "object", "properties": {"container_id": {"type": "string"}}, "required": ["container_id"]},
            "handler_path": "mcp_tools_core.tools.synology.docker.synology_start_docker_container",
            "tags": "synology,nas,docker",
        },
        {
            "name": "synology_stop_docker_container",
            "description": "Stop a Docker container on Synology NAS",
            "input_schema": {"type": "object", "properties": {"container_id": {"type": "string"}}, "required": ["container_id"]},
            "handler_path": "mcp_tools_core.tools.synology.docker.synology_stop_docker_container",
            "tags": "synology,nas,docker",
        },
        # Synology Backup Tools
        {
            "name": "synology_list_backup_tasks",
            "description": "List Hyper Backup tasks on Synology NAS",
            "input_schema": {"type": "object", "properties": {}, "required": []},
            "handler_path": "mcp_tools_core.tools.synology.backup.synology_list_backup_tasks",
            "tags": "synology,nas,backup",
        },
        {
            "name": "synology_run_backup_task",
            "description": "Trigger a Hyper Backup task to run on Synology NAS",
            "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": ["task_id"]},
            "handler_path": "mcp_tools_core.tools.synology.backup.synology_run_backup_task",
            "tags": "synology,nas,backup",
        },
        # Synology Security Tools
        {
            "name": "synology_get_security_settings",
            "description": "Get security settings from Synology NAS",
            "input_schema": {"type": "object", "properties": {}, "required": []},
            "handler_path": "mcp_tools_core.tools.synology.security.synology_get_security_settings",
            "tags": "synology,nas,security",
        },
        {
            "name": "synology_list_firewall_rules",
            "description": "List firewall rules on Synology NAS",
            "input_schema": {"type": "object", "properties": {}, "required": []},
            "handler_path": "mcp_tools_core.tools.synology.security.synology_list_firewall_rules",
            "tags": "synology,nas,security,firewall",
        },
        # Synology Monitoring Tools
        {
            "name": "synology_get_resource_usage",
            "description": "Get current resource usage from Synology NAS (CPU, memory, disk, network)",
            "input_schema": {"type": "object", "properties": {}, "required": []},
            "handler_path": "mcp_tools_core.tools.synology.monitoring.synology_get_resource_usage",
            "tags": "synology,nas,monitoring",
        },
        {
            "name": "synology_list_logs",
            "description": "List system logs from Synology NAS Log Center",
            "input_schema": {"type": "object", "properties": {"log_type": {"type": "string", "default": "connection"}, "offset": {"type": "integer", "default": 0}, "limit": {"type": "integer", "default": 100}}, "required": []},
            "handler_path": "mcp_tools_core.tools.synology.monitoring.synology_list_logs",
            "tags": "synology,nas,monitoring,logs",
        },
    ]
    
    # Bulk create all tools
    for tool_data in tools_to_create:
        Tool.objects.create(**tool_data)


def reverse_seed_tools(apps, schema_editor):
    """Remove seeded Tool records."""
    Tool = apps.get_model("mcp_tools_core", "Tool")
    # Delete all tools that were seeded (by handler_path prefix)
    Tool.objects.filter(handler_path__startswith="mcp_tools_core.tools.").delete()


class Migration(migrations.Migration):
    """Seed Tool records from existing MCP server definitions."""

    dependencies = [
        ("mcp_tools_core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_tools, reverse_seed_tools),
    ]

