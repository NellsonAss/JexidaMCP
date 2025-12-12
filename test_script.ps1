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
            Write-Host " âœ“" -ForegroundColor Green
            return $true
        } else {
            Write-Host " âœ— Failed: $($response.error)" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host " âœ— Error: $_" -ForegroundColor Red
        return $false
    }
}

# Controller tools
Register-Tool -Name "unifi_controller_get_config" `
    -Description "Retrieve full UniFi controller configuration including networks, WLANs, firewall rules, devices, and settings" `
    -HandlerPath "mcp_tools_core.tools.unifi.controller.unifi_controller_get_config" `
    -Tags "unifi,controller,config" `
