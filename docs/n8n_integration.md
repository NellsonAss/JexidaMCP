# n8n Integration Guide

This guide explains how to deploy and control n8n automation platform via JexidaMCP.

## Overview

JexidaMCP provides full integration with n8n, including:
- Automated deployment to worker nodes
- Workflow management via REST API
- Webhook triggering
- SSH-based administration (restart, backup, restore)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         JexidaMCP System                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────┐         ┌─────────────────────────────────┐   │
│  │   Jexida CLI     │         │      MCP Server                 │   │
│  │                  │         │      192.168.1.224              │   │
│  │  /n8n commands   │◀───────▶│                                 │   │
│  │                  │  REST   │  ┌────────────────────────────┐ │   │
│  └──────────────────┘   API   │  │     n8n MCP Tools          │ │   │
│                               │  │                            │ │   │
│                               │  │  • n8n_health_check        │ │   │
│                               │  │  • n8n_list_workflows      │ │   │
│                               │  │  • n8n_run_workflow        │ │   │
│                               │  │  • n8n_trigger_webhook     │ │   │
│                               │  │  • n8n_restart_stack       │ │   │
│                               │  │  • n8n_backup              │ │   │
│                               │  └────────────────────────────┘ │   │
│                               └──────────────┬──────────────────┘   │
│                                              │                       │
│                           ┌──────────────────┼──────────────────┐   │
│                           │ HTTP API         │ SSH              │   │
│                           ▼                  ▼                  │   │
│                  ┌─────────────────────────────────────────┐    │   │
│                  │         Worker Node (JexidaDroid2)       │    │   │
│                  │         192.168.1.254                    │    │   │
│                  │                                          │    │   │
│                  │    ┌────────────────────────────────┐   │    │   │
│                  │    │         Docker                  │   │    │   │
│                  │    │    ┌────────────────────────┐  │   │    │   │
│                  │    │    │        n8n             │  │   │    │   │
│                  │    │    │    Port 5678           │  │   │    │   │
│                  │    │    │                        │  │   │    │   │
│                  │    │    │  • Workflows           │  │   │    │   │
│                  │    │    │  • Webhooks            │  │   │    │   │
│                  │    │    │  • Credentials         │  │   │    │   │
│                  │    │    └────────────────────────┘  │   │    │   │
│                  │    └────────────────────────────────┘   │    │   │
│                  │                                          │    │   │
│                  │    /opt/n8n/                             │    │   │
│                  │    ├── docker-compose.yml                │    │   │
│                  │    ├── .env                              │    │   │
│                  │    ├── data/                             │    │   │
│                  │    └── backups/                          │    │   │
│                  └─────────────────────────────────────────┘    │   │
│                                                                  │   │
└──────────────────────────────────────────────────────────────────┘
```

## Deployment

### Prerequisites

1. A registered worker node with SSH access configured
2. The worker node must have internet access (for Docker installation)

### Deploy via MCP Tool

```bash
# Using the API
curl -X POST http://192.168.1.224:8080/tools/api/tools/n8n_deploy_stack/run/ \
  -H "Content-Type: application/json" \
  -d '{
    "node_name": "JexidaDroid2",
    "n8n_user": "admin",
    "n8n_password": "your-secure-password",
    "encryption_key": "auto"
  }'
```

The deployment will:
1. Install Docker and Docker Compose
2. Create `/opt/n8n/` directory structure
3. Generate docker-compose.yml and .env files
4. Start the n8n container

**Important:** Save the returned `encryption_key` - you'll need it for recovery!

### Manual Deployment

If you prefer manual deployment, copy and run the setup script:

```bash
# Copy to worker node
scp scripts/setup_n8n_node.sh jexida@192.168.1.254:/tmp/

# Run with credentials
ssh jexida@192.168.1.254 "chmod +x /tmp/setup_n8n_node.sh && /tmp/setup_n8n_node.sh admin 'your-password' 'your-32-byte-hex-key'"
```

## MCP Tools Reference

### API Tools

| Tool | Description |
|------|-------------|
| `n8n_health_check` | Check if n8n is running and healthy |
| `n8n_list_workflows` | List all workflows (optionally filter active only) |
| `n8n_get_workflow` | Get full workflow details including nodes |
| `n8n_run_workflow` | Execute a workflow with optional payload |
| `n8n_get_execution` | Get status and results of an execution |
| `n8n_trigger_webhook` | Trigger a webhook endpoint |

### Admin Tools (SSH-based)

| Tool | Description |
|------|-------------|
| `n8n_restart_stack` | Restart the Docker container |
| `n8n_backup` | Create a tarball backup of n8n data |
| `n8n_restore_backup` | Restore from a backup file |

### Deployment Tools

| Tool | Description |
|------|-------------|
| `n8n_deploy_stack` | Deploy n8n to a worker node |

## CLI Usage

The Jexida CLI provides convenient commands for n8n:

```bash
# Show help
/n8n

# Health check
/n8n health

# List workflows
/n8n list
/n8n list --active

# Get workflow details
/n8n get 5

# Run a workflow
/n8n run 5
/n8n run 5 {"input": "test data"}

# Check execution status
/n8n exec abc-123

# Trigger webhook
/n8n webhook my-webhook-path
/n8n webhook my-webhook-path {"action": "trigger"}

# Administration
/n8n restart
/n8n backup
/n8n backup my-backup-name
```

## Configuration

### Environment Variables

Set these on the MCP server (in `/opt/jexida-mcp/.env`):

```env
# n8n Connection
N8N_BASE_URL=http://192.168.1.254:5678
N8N_USER=admin
N8N_PASSWORD=your-password

# SSH Access (for admin tools)
N8N_SSH_HOST=192.168.1.254
N8N_SSH_USER=jexida

# Optional
N8N_TIMEOUT=30
```

### Django Settings

Alternatively, add to Django settings:

```python
# settings.py
N8N_BASE_URL = "http://192.168.1.254:5678"
N8N_USER = "admin"
N8N_PASSWORD = os.environ.get("N8N_PASSWORD", "")
N8N_SSH_HOST = "192.168.1.254"
N8N_SSH_USER = "jexida"
```

## Backup and Restore

### Creating Backups

Backups are stored in `/opt/n8n/backups/` on the worker node:

```bash
# Via CLI
/n8n backup

# Via API
curl -X POST http://192.168.1.224:8080/tools/api/tools/n8n_backup/run/ \
  -H "Content-Type: application/json" \
  -d '{"backup_name": "pre-upgrade-backup"}'
```

### Restoring from Backup

```bash
# Via API
curl -X POST http://192.168.1.224:8080/tools/api/tools/n8n_restore_backup/run/ \
  -H "Content-Type: application/json" \
  -d '{
    "backup_file": "/opt/n8n/backups/n8n_backup_20241210_120000.tar.gz",
    "stop_n8n": true
  }'
```

## Troubleshooting

### n8n Not Responding

1. Check container status:
   ```bash
   ssh jexida@192.168.1.254 "docker compose -f /opt/n8n/docker-compose.yml ps"
   ```

2. Check logs:
   ```bash
   ssh jexida@192.168.1.254 "docker compose -f /opt/n8n/docker-compose.yml logs --tail=100"
   ```

3. Restart the stack:
   ```bash
   /n8n restart
   ```

### API Authentication Errors

Verify credentials in the MCP server's environment match the n8n configuration:

```bash
# Check n8n's configured credentials
ssh jexida@192.168.1.254 "cat /opt/n8n/.env"
```

### Webhook Not Triggering

1. Ensure the workflow is **active**
2. Check the webhook path matches exactly
3. Verify n8n is accessible from the MCP server:
   ```bash
   ssh jexida@192.168.1.224 "curl -s http://192.168.1.254:5678/healthz"
   ```

## Security Considerations

1. **Encryption Key**: The n8n encryption key protects stored credentials. Keep it secure!
2. **Basic Auth**: Change the default password after deployment
3. **Network**: Consider placing n8n behind a reverse proxy with HTTPS
4. **Firewall**: Restrict port 5678 to trusted networks only

## API Examples

### Run a Workflow with Input Data

```python
import httpx

response = httpx.post(
    "http://192.168.1.224:8080/tools/api/tools/n8n_run_workflow/run/",
    json={
        "workflow_id": "5",
        "payload": {
            "customer_email": "test@example.com",
            "order_id": "12345"
        }
    }
)
print(response.json())
```

### Poll Execution Status

```python
import httpx
import time

execution_id = "abc-123"

while True:
    response = httpx.post(
        "http://192.168.1.224:8080/tools/api/tools/n8n_get_execution/run/",
        json={"execution_id": execution_id}
    )
    result = response.json().get("result", {})
    
    if result.get("finished"):
        print(f"Execution completed: {result.get('status')}")
        break
    
    time.sleep(2)
```

