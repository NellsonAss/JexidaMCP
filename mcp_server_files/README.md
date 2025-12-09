# JexidaMCP Server

MCP (Master Control Program) Server for Azure management, network automation, and security hardening.

## Overview

JexidaMCP is a FastAPI-based server that exposes MCP tools for:
- Azure CLI command execution
- Azure cost summaries
- HTTP health probes
- UniFi network inventory and management
- Network security auditing and hardening

It's designed to be called by AI agents or web apps that handle UI/orchestration while JexidaMCP handles authentication and execution.

## Quick Start

### 1. Install Dependencies

```bash
cd ~/mcp_projects/mcp_server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the example environment file and edit as needed:

```bash
cp .env.example .env
nano .env
```

### 3. Authenticate to Azure

```bash
az login
```

### 4. Start the Server

```bash
./run.sh
```

Or manually:

```bash
uvicorn main:app --host 0.0.0.0 --port 8080
```

### 5. Verify

```bash
curl http://localhost:8080/health
# {"status":"healthy","version":"0.1.0"}

curl http://localhost:8080/api/tools
# [list of available tools]
```

## Web Dashboard

JexidaMCP includes a web dashboard for managing secrets and monitoring your infrastructure.

Access the dashboard at: `http://localhost:8080/`

### Dashboard Features

- **Secret Management**: Add, edit, and delete credentials for Azure, UniFi, and other services
- **Encrypted Storage**: All secrets are encrypted at rest using Fernet (AES-128-CBC)
- **Monitoring**: View system health, Azure costs, and UniFi device status
- **Action Triggers**: Execute MCP tools directly from the web interface

See `docs/dashboard.md` for detailed documentation.

### Setting Up Secrets

1. Generate an encryption key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

2. Add to your `.env` file:
```
SECRET_ENCRYPTION_KEY=your-generated-key-here
```

3. Access the dashboard and add your credentials via the web interface.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web dashboard |
| `/secrets` | GET | Secrets management |
| `/monitoring` | GET | Monitoring dashboard |
| `/health` | GET | Health check |
| `/docs` | GET | Swagger UI documentation |
| `/redoc` | GET | ReDoc documentation |
| `/api/tools` | GET | List available tools |
| `/api/tools/{name}/execute` | POST | Execute a tool |

## Available Tools

### Azure Tools

1. **azure_cli.run** - Execute Azure CLI commands
2. **azure_cost.get_summary** - Get cost summaries (mock data)
3. **monitor.http_health_probe** - HTTP health checks

See `docs/azure-tools.md` for detailed documentation.

### UniFi Network Tools

1. **unifi_list_devices** - List all UniFi devices (gateways, switches, APs)
2. **unifi_get_security_settings** - Get comprehensive security configuration
3. **unifi_apply_changes** - Apply configuration changes with dry-run support
4. **network_scan_local** - Run nmap scans to discover devices and open ports
5. **network_hardening_audit** - Audit network against security best practices
6. **network_apply_hardening_plan** - Apply hardening recommendations in phases

See the [UniFi Tools Guide](#unifi-network-hardening-guide) below for detailed usage.

## Configuration

### Server Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_SERVER_PORT` | 8080 | Server port |
| `MCP_SERVER_HOST` | 0.0.0.0 | Server host |
| `MCP_LOG_LEVEL` | INFO | Logging level |

### Azure Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `AZURE_CLI_PATH` | az | Path to Azure CLI |
| `AZURE_CLI_TIMEOUT` | 300 | Command timeout (seconds) |

See `docs/azure-tools.md` for Azure-specific configuration.

### UniFi Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `UNIFI_CONTROLLER_URL` | - | UniFi Controller URL (e.g., `https://192.168.1.1`) |
| `UNIFI_USERNAME` | - | UniFi admin username |
| `UNIFI_PASSWORD` | - | UniFi admin password |
| `UNIFI_SITE` | default | UniFi site ID |
| `UNIFI_VERIFY_SSL` | False | Verify SSL certificates |
| `UNIFI_TIMEOUT` | 30 | API request timeout (seconds) |

### Network Scanning Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `NMAP_PATH` | nmap | Path to nmap binary |
| `NMAP_TIMEOUT` | 300 | Scan timeout (seconds) |

**Note:** The MCP server must have network access to the UniFi controller and `nmap` installed for scanning.

## Development

### Running Tests

```bash
source venv/bin/activate
pytest tests/ -v
```

### Code Structure

```
mcp_server/
├── main.py                  # Entry point
├── server.py                # FastAPI app, routes, and dashboard
├── config.py                # Configuration management
├── config_db.py             # Database-backed config loading
├── database.py              # SQLAlchemy models and encryption
├── schemas.py               # Pydantic models for forms
├── dashboard.py             # Monitoring data fetching
├── logging_config.py        # Structured logging
├── tool_registry.py         # Tool registration system
├── security_policy.json     # Network hardening policy rules
├── templates/               # Jinja2 templates for web dashboard
│   ├── base.html
│   ├── dashboard.html
│   ├── secrets_list.html
│   ├── secret_form.html
│   ├── monitoring.html
│   └── partials/
├── static/                  # Static assets (CSS, JS)
├── migrations/              # Alembic database migrations
├── mcp_tools/
│   ├── azure/
│   │   ├── cli.py           # azure_cli.run
│   │   ├── cost.py          # azure_cost.get_summary
│   │   ├── monitor.py       # monitor.http_health_probe
│   │   └── utils.py         # Shared utilities
│   └── unifi/
│       ├── client.py        # UniFi API client
│       ├── devices.py       # unifi_list_devices
│       ├── security.py      # unifi_get_security_settings
│       ├── changes.py       # unifi_apply_changes
│       ├── diff.py          # Change planning helpers
│       ├── network_scan.py  # network_scan_local
│       ├── audit.py         # network_hardening_audit
│       └── hardening.py     # network_apply_hardening_plan
├── tests/
│   ├── test_azure_cli.py
│   ├── test_unifi_*.py      # UniFi tool tests
│   └── fixtures/            # Mock API responses
└── docs/
    ├── azure-tools.md
    ├── azuremanagement-integration.md
    └── dashboard.md
```

## Security

- Commands are sanitized to prevent shell injection
- Secrets are never logged
- All operations have timeouts
- Subscription IDs are validated

## UniFi Network Hardening Guide

### Prerequisites

1. Configure UniFi credentials in your `.env` file:

```bash
UNIFI_CONTROLLER_URL=https://192.168.1.1
UNIFI_USERNAME=admin
UNIFI_PASSWORD=your_password
UNIFI_SITE=default
UNIFI_VERIFY_SSL=false
```

2. Install `nmap` for network scanning (optional but recommended):

```bash
# Ubuntu/Debian
sudo apt-get install nmap

# macOS
brew install nmap
```

### Basic Workflow

#### 1. Inventory Your Network

First, list all your UniFi devices:

```json
// POST /api/tools/unifi_list_devices/execute
{
  "site_id": "default"
}
```

#### 2. Review Security Configuration

Get a comprehensive view of your security settings:

```json
// POST /api/tools/unifi_get_security_settings/execute
{
  "include_firewall_rules": true
}
```

#### 3. Run a Security Audit

Audit your configuration against best practices:

```json
// POST /api/tools/network_hardening_audit/execute
{
  "run_scan": true,
  "scan_subnets": ["192.168.1.0/24", "192.168.2.0/24"]
}
```

This returns:
- **findings**: Security issues with severity levels (low/medium/high)
- **recommended_changes**: Structured changes that can be applied
- **notes**: Additional observations

#### 4. Preview Hardening Changes

Preview what changes would be made without applying them:

```json
// POST /api/tools/network_apply_hardening_plan/execute
{
  "plan": {
    "changes": [/* recommended_changes from audit */]
  },
  "confirm": false,
  "phased": true
}
```

#### 5. Apply Hardening (with Confirmation)

When ready, apply the changes in phases:

```json
// POST /api/tools/network_apply_hardening_plan/execute
{
  "plan": {
    "changes": [/* recommended_changes from audit */]
  },
  "confirm": true,
  "phased": true,
  "stop_on_failure": true
}
```

**Phases:**
- **Phase 1**: Low-risk changes (disable UPnP, enable client isolation)
- **Phase 2**: Firewall rule changes
- **Phase 3**: VLAN and network segmentation changes

### Security Policy

The default security policy (`security_policy.json`) enforces:

- **WiFi**: WPA2/WPA3 encryption required, no open networks
- **Guest Networks**: Client isolation enabled, separate VLAN
- **Remote Access**: UPnP and NAT-PMP disabled
- **Threat Management**: IDS/IPS recommended
- **Firewall**: Flag overly permissive rules

You can customize the policy by editing `security_policy.json`.

### Manual Changes

For granular control, use `unifi_apply_changes` directly:

```json
// POST /api/tools/unifi_apply_changes/execute
{
  "dry_run": true,
  "wifi_edits": [
    {
      "ssid": "GuestNetwork",
      "l2_isolation": true,
      "vlan_enabled": true,
      "vlan": 100
    }
  ],
  "upnp_edits": {
    "upnp_enabled": false
  }
}
```

Set `dry_run: false` to apply the changes.

## Roadmap

- **Phase 2**: Azure authentication tools
- **Phase 3**: Azure inventory tools
- **Phase 4**: Resource deployment tools
- **Phase 5**: Long-running operations
- **Phase 6-10**: Monitoring, testing, cost optimization, security
- **Network**: Additional network vendors, automated backup/restore

## License

Internal use only.

