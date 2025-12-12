# Register all UniFi tools via MCP API
# Run this script to register all 19 new UniFi tools

$apiUrl = "http://192.168.1.224:8080"
$baseUrl = "$apiUrl/tools/api/tools/register_mcp_tool/run/"

Write-Host "Registering UniFi tools via MCP API..." -ForegroundColor Cyan
Write-Host ""

# Helper function to register a tool
function Register-Tool {
    param(
        [string]$Name,
        [string]$Description,
        [string]$HandlerPath,
        [string]$Tags,
        [hashtable]$InputSchema
    )
    
    $body = @{
        name = $Name
        description = $Description
        handler_path = $HandlerPath
        tags = $Tags
        input_schema = $InputSchema
        is_active = $true
        restart_service = $false
    } | ConvertTo-Json -Depth 10
    
    try {
        Write-Host "Registering $Name..." -NoNewline
        $response = Invoke-RestMethod -Uri $baseUrl -Method POST -ContentType "application/json" -Body $body
        if ($response.success) {
            Write-Host " [OK]" -ForegroundColor Green
            return $true
        } else {
            Write-Host " [FAILED: $($response.error)]" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host " [ERROR: $_]" -ForegroundColor Red
        return $false
    }
}

# Controller tools
Register-Tool -Name "unifi_controller_get_config" `
    -Description "Retrieve full UniFi controller configuration including networks, WLANs, firewall rules, devices, and settings" `
    -HandlerPath "mcp_tools_core.tools.unifi.controller.unifi_controller_get_config" `
    -Tags "unifi,controller,config" `
    -InputSchema @{
        type = "object"
        properties = @{
            scope = @{
                type = "string"
                enum = @("all", "networks", "wlans", "firewall", "devices", "vlans", "settings")
                default = "all"
                description = "Configuration scope"
            }
            site_id = @{
                type = "string"
                description = "UniFi site ID (optional)"
            }
        }
        required = @()
    }

Register-Tool -Name "unifi_controller_backup" `
    -Description "Create a timestamped controller backup. Always create a backup before making significant changes." `
    -HandlerPath "mcp_tools_core.tools.unifi.controller.unifi_controller_backup" `
    -Tags "unifi,controller,backup" `
    -InputSchema @{
        type = "object"
        properties = @{
            label = @{
                type = "string"
                enum = @("pre-hardening", "pre-change", "manual", "scheduled")
                default = "manual"
                description = "Backup label/reason"
            }
            site_id = @{
                type = "string"
                description = "UniFi site ID (optional)"
            }
        }
        required = @()
    }

Register-Tool -Name "unifi_controller_list_backups" `
    -Description "List all available controller backups with metadata" `
    -HandlerPath "mcp_tools_core.tools.unifi.controller.unifi_controller_list_backups" `
    -Tags "unifi,controller,backup" `
    -InputSchema @{
        type = "object"
        properties = @{
            site_id = @{
                type = "string"
                description = "UniFi site ID (optional)"
            }
        }
        required = @()
    }

Register-Tool -Name "unifi_controller_restore" `
    -Description "Restore a controller backup. WARNING: This will restart the controller and replace all current configuration. Requires confirmation_token=CONFIRM_RESTORE." `
    -HandlerPath "mcp_tools_core.tools.unifi.controller.unifi_controller_restore" `
    -Tags "unifi,controller,backup,restore" `
    -InputSchema @{
        type = "object"
        properties = @{
            backup_id = @{
                type = "string"
                description = "ID of the backup to restore"
            }
            confirmation_token = @{
                type = "string"
                description = "Confirmation token: must be 'CONFIRM_RESTORE' to proceed"
            }
            site_id = @{
                type = "string"
                description = "UniFi site ID (optional)"
            }
        }
        required = @("backup_id", "confirmation_token")
    }

# Topology
Register-Tool -Name "unifi_network_topology" `
    -Description "Build a graph representation of the network including switch-to-AP connections, port usage, VLAN assignments, and PoE state" `
    -HandlerPath "mcp_tools_core.tools.unifi.topology.unifi_network_topology" `
    -Tags "unifi,network,topology" `
    -InputSchema @{
        type = "object"
        properties = @{
            site_id = @{
                type = "string"
                description = "UniFi site ID (optional)"
            }
            include_ports = @{
                type = "boolean"
                default = $true
                description = "Include detailed port information"
            }
        }
        required = @()
    }

# Security monitoring
Register-Tool -Name "security_monitor_unifi" `
    -Description "Real-time or periodic monitoring of security events including unauthorized device joins, rogue APs, port state changes, authentication failures, and WAN attacks/IPS alerts" `
    -HandlerPath "mcp_tools_core.tools.unifi.monitoring.security_monitor_unifi" `
    -Tags "unifi,security,monitoring" `
    -InputSchema @{
        type = "object"
        properties = @{
            interval = @{
                type = "string"
                enum = @("5m", "30m", "1h", "snapshot")
                default = "snapshot"
                description = "Monitoring interval"
            }
            mode = @{
                type = "string"
                enum = @("watch", "snapshot")
                default = "snapshot"
                description = "Monitoring mode"
            }
            site_id = @{
                type = "string"
                description = "UniFi site ID (optional)"
            }
            limit = @{
                type = "integer"
                default = 50
                description = "Maximum number of alerts/events to return"
            }
        }
        required = @()
    }

# VLAN management
Register-Tool -Name "unifi_vlan_create" `
    -Description "Create a new VLAN/network with subnet validation and DHCP pool configuration" `
    -HandlerPath "mcp_tools_core.tools.unifi.vlan_mgmt.unifi_vlan_create" `
    -Tags "unifi,vlan,network" `
    -InputSchema @{
        type = "object"
        properties = @{
            name = @{
                type = "string"
                description = "VLAN/Network name"
            }
            vlan_id = @{
                type = "integer"
                description = "VLAN ID (1-4094)"
            }
            subnet = @{
                type = "string"
                description = "IP subnet in CIDR notation"
            }
            dhcp = @{
                type = "boolean"
                default = $true
                description = "Enable DHCP"
            }
            dhcp_start = @{
                type = "string"
                description = "DHCP start IP (optional)"
            }
            dhcp_stop = @{
                type = "string"
                description = "DHCP stop IP (optional)"
            }
            purpose = @{
                type = "string"
                default = "corporate"
                description = "Network purpose"
            }
            site_id = @{
                type = "string"
                description = "UniFi site ID (optional)"
            }
        }
        required = @("name", "vlan_id", "subnet")
    }

Register-Tool -Name "unifi_vlan_update" `
    -Description "Update VLAN/network configuration including DHCP settings and subnet" `
    -HandlerPath "mcp_tools_core.tools.unifi.vlan_mgmt.unifi_vlan_update" `
    -Tags "unifi,vlan,network" `
    -InputSchema @{
        type = "object"
        properties = @{
            network_id = @{
                type = "string"
                description = "Network ID to update"
            }
            network_name = @{
                type = "string"
                description = "Network name (if ID not provided)"
            }
            dhcp_enabled = @{
                type = "boolean"
                description = "Enable/disable DHCP"
            }
            dhcp_start = @{
                type = "string"
                description = "DHCP start IP"
            }
            dhcp_stop = @{
                type = "string"
                description = "DHCP stop IP"
            }
            subnet = @{
                type = "string"
                description = "IP subnet"
            }
            description = @{
                type = "string"
                description = "Network description"
            }
            site_id = @{
                type = "string"
                description = "UniFi site ID (optional)"
            }
        }
        required = @()
    }

# WiFi management
Register-Tool -Name "unifi_wifi_create" `
    -Description "Create a new WiFi network/SSID with security settings, VLAN assignment, and guest network options" `
    -HandlerPath "mcp_tools_core.tools.unifi.wifi_mgmt.unifi_wifi_create" `
    -Tags "unifi,wifi,wlan" `
    -InputSchema @{
        type = "object"
        properties = @{
            name = @{
                type = "string"
                description = "WiFi network name (SSID)"
            }
            vlan_id = @{
                type = "integer"
                description = "VLAN ID to assign (optional)"
            }
            security = @{
                type = "string"
                enum = @("WPA2", "WPA3", "WPA2-WPA3")
                default = "WPA2"
                description = "Security mode"
            }
            password = @{
                type = "string"
                description = "WiFi password"
            }
            guest = @{
                type = "boolean"
                default = $false
                description = "Is guest network"
            }
            hidden = @{
                type = "boolean"
                default = $false
                description = "Hide SSID"
            }
            client_isolation = @{
                type = "boolean"
                default = $false
                description = "Enable client isolation"
            }
            site_id = @{
                type = "string"
                description = "UniFi site ID (optional)"
            }
        }
        required = @("name", "password")
    }

Register-Tool -Name "unifi_wifi_update" `
    -Description "Update WiFi network configuration including password, VLAN, security mode, PMF, and legacy 2.4 GHz settings" `
    -HandlerPath "mcp_tools_core.tools.unifi.wifi_mgmt.unifi_wifi_update" `
    -Tags "unifi,wifi,wlan" `
    -InputSchema @{
        type = "object"
        properties = @{
            wlan_id = @{
                type = "string"
                description = "WLAN ID to update"
            }
            ssid = @{
                type = "string"
                description = "SSID name (if ID not provided)"
            }
            password = @{
                type = "string"
                description = "New WiFi password"
            }
            vlan_id = @{
                type = "integer"
                description = "VLAN ID to assign"
            }
            security = @{
                type = "string"
                enum = @("WPA2", "WPA3", "WPA2-WPA3")
                description = "Security mode"
            }
            enable_pmf = @{
                type = "boolean"
                description = "Enable Protected Management Frames"
            }
            disable_legacy_24ghz = @{
                type = "boolean"
                description = "Disable legacy 2.4 GHz support"
            }
            site_id = @{
                type = "string"
                description = "UniFi site ID (optional)"
            }
        }
        required = @()
    }

# Firewall management
Register-Tool -Name "unifi_firewall_create_rule" `
    -Description "Create a new firewall rule with source/destination networks, protocol, and port specifications" `
    -HandlerPath "mcp_tools_core.tools.unifi.firewall_mgmt.unifi_firewall_create_rule" `
    -Tags "unifi,firewall,security" `
    -InputSchema @{
        type = "object"
        properties = @{
            action = @{
                type = "string"
                enum = @("drop", "accept", "reject")
                description = "Rule action"
            }
            from_network = @{
                type = "string"
                description = "Source network name"
            }
            to_network = @{
                type = "string"
                description = "Destination network name"
            }
            from_address = @{
                type = "string"
                description = "Source IP address/CIDR"
            }
            to_address = @{
                type = "string"
                description = "Destination IP address/CIDR"
            }
            protocol = @{
                type = "string"
                enum = @("all", "tcp", "udp", "icmp")
                default = "all"
                description = "Protocol"
            }
            dst_port = @{
                type = "string"
                description = "Destination port(s)"
            }
            comment = @{
                type = "string"
                default = ""
                description = "Rule comment/description"
            }
            ruleset = @{
                type = "string"
                enum = @("wan_in", "wan_out", "lan_in", "lan_out", "lan_local", "guest_in", "guest_out", "guest_local")
                default = "lan_in"
                description = "Firewall ruleset"
            }
            site_id = @{
                type = "string"
                description = "UniFi site ID (optional)"
            }
        }
        required = @("action")
    }

Register-Tool -Name "unifi_firewall_update_rule" `
    -Description "Update existing firewall rule configuration safely" `
    -HandlerPath "mcp_tools_core.tools.unifi.firewall_mgmt.unifi_firewall_update_rule" `
    -Tags "unifi,firewall,security" `
    -InputSchema @{
        type = "object"
        properties = @{
            rule_id = @{
                type = "string"
                description = "Firewall rule ID to update"
            }
            enabled = @{
                type = "boolean"
                description = "Enable/disable rule"
            }
            action = @{
                type = "string"
                enum = @("drop", "accept", "reject")
                description = "Rule action"
            }
            protocol = @{
                type = "string"
                enum = @("all", "tcp", "udp", "icmp")
                description = "Protocol"
            }
            dst_port = @{
                type = "string"
                description = "Destination port(s)"
            }
            comment = @{
                type = "string"
                description = "Rule comment"
            }
            site_id = @{
                type = "string"
                description = "UniFi site ID (optional)"
            }
        }
        required = @("rule_id")
    }

Register-Tool -Name "unifi_firewall_validate" `
    -Description "Validate firewall rules for issues including rule reordering, redundancy, broken segmentation, and guest network isolation failures" `
    -HandlerPath "mcp_tools_core.tools.unifi.firewall_mgmt.unifi_firewall_validate" `
    -Tags "unifi,firewall,security,validation" `
    -InputSchema @{
        type = "object"
        properties = @{
            site_id = @{
                type = "string"
                description = "UniFi site ID (optional)"
            }
        }
        required = @()
    }

# SSH tools
Register-Tool -Name "ssh_unifi_device_run" `
    -Description "Run arbitrary SSH commands on UniFi devices for troubleshooting, firmware checks, and deep metrics gathering" `
    -HandlerPath "mcp_tools_core.tools.unifi.ssh_tools.ssh_unifi_device_run" `
    -Tags "unifi,ssh,device" `
    -InputSchema @{
        type = "object"
        properties = @{
            host = @{
                type = "string"
                description = "Device IP address or hostname"
            }
            cmd = @{
                type = "string"
                description = "SSH command to execute"
            }
            username = @{
                type = "string"
                default = "root"
                description = "SSH username"
            }
            timeout = @{
                type = "integer"
                default = 30
                description = "Command timeout in seconds"
            }
        }
        required = @("host", "cmd")
    }

Register-Tool -Name "ssh_unifi_device_info" `
    -Description "Run predefined safe diagnostic commands to collect CPU, memory, radio status, PoE power, firmware, and uptime information" `
    -HandlerPath "mcp_tools_core.tools.unifi.ssh_tools.ssh_unifi_device_info" `
    -Tags "unifi,ssh,device,diagnostics" `
    -InputSchema @{
        type = "object"
        properties = @{
            host = @{
                type = "string"
                description = "Device IP address or hostname"
            }
            username = @{
                type = "string"
                default = "root"
                description = "SSH username"
            }
        }
        required = @("host")
    }

Register-Tool -Name "ssh_unifi_device_adopt" `
    -Description "Force device adoption via SSH by running set-inform command. Used for adoption issues when devices will not adopt through the UI" `
    -HandlerPath "mcp_tools_core.tools.unifi.ssh_tools.ssh_unifi_device_adopt" `
    -Tags "unifi,ssh,device,adoption" `
    -InputSchema @{
        type = "object"
        properties = @{
            host = @{
                type = "string"
                description = "Device IP address or hostname"
            }
            controller_url = @{
                type = "string"
                description = "Controller URL"
            }
            username = @{
                type = "string"
                default = "root"
                description = "SSH username"
            }
        }
        required = @("host", "controller_url")
    }

# Config management
Register-Tool -Name "unifi_config_export" `
    -Description "Export controller configuration in JSON + diff-friendly format" `
    -HandlerPath "mcp_tools_core.tools.unifi.config_mgmt.unifi_config_export" `
    -Tags "unifi,config,export" `
    -InputSchema @{
        type = "object"
        properties = @{
            site_id = @{
                type = "string"
                description = "UniFi site ID (optional)"
            }
            format = @{
                type = "string"
                default = "json"
                description = "Export format"
            }
        }
        required = @()
    }

Register-Tool -Name "unifi_config_diff" `
    -Description "Compare two configurations or current config vs backup and return structured differences" `
    -HandlerPath "mcp_tools_core.tools.unifi.config_mgmt.unifi_config_diff" `
    -Tags "unifi,config,diff" `
    -InputSchema @{
        type = "object"
        properties = @{
            config1 = @{
                type = "object"
                description = "First configuration (from export)"
            }
            config2 = @{
                type = "object"
                description = "Second configuration (from export)"
            }
            compare_to_backup = @{
                type = "string"
                description = "Compare current config to backup ID"
            }
            site_id = @{
                type = "string"
                description = "UniFi site ID (optional)"
            }
        }
        required = @()
    }

Register-Tool -Name "unifi_config_drift_monitor" `
    -Description "Monitor for configuration drift outside automation. Compares current configuration to baseline and alerts if unauthorized changes detected" `
    -HandlerPath "mcp_tools_core.tools.unifi.config_mgmt.unifi_config_drift_monitor" `
    -Tags "unifi,config,drift,monitoring" `
    -InputSchema @{
        type = "object"
        properties = @{
            baseline_config = @{
                type = "object"
                description = "Baseline configuration to compare against"
            }
            site_id = @{
                type = "string"
                description = "UniFi site ID (optional)"
            }
            alert_on_drift = @{
                type = "boolean"
                default = $true
                description = "Alert if drift detected"
            }
        }
        required = @("baseline_config")
    }

Write-Host ""
Write-Host "Registration complete!" -ForegroundColor Green

