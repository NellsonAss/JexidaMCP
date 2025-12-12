# Worker Nodes Setup Guide

This guide explains how to prepare a new Ubuntu server as a worker node for JexidaMCP job execution.

## Overview

Worker nodes are remote servers that the MCP platform can SSH into to execute commands and jobs. The MCP server (192.168.1.224) connects to worker nodes via SSH to run commands on behalf of users, LLMs, or automated routines.

## Architecture

```
┌─────────────────────┐         SSH          ┌───────────────────────┐
│   MCP Server        │ ────────────────────▶│   Worker Node         │
│   192.168.1.224     │                       │   192.168.0.66        │
│                     │                       │   (JexidaDroid1)      │
│   - Django App      │                       │   - jexida user       │
│   - Job MCP Tools   │                       │   - Job directories   │
│   - SSH Executor    │                       │   - Python 3          │
└─────────────────────┘                       └───────────────────────┘
```

## Prerequisites

- Fresh Ubuntu 22.04+ server (or compatible Linux distribution)
- Network connectivity from MCP server to worker node
- Root or sudo access on the worker node

## Step 1: Create the `jexida` User

SSH to the new worker node and create a dedicated user:

```bash
# On the worker node (192.168.0.66)
sudo adduser jexida --disabled-password --gecos "Jexida MCP Worker"
sudo usermod -aG sudo jexida  # Optional: for privileged commands
```

## Step 2: Set Up SSH Key-Based Authentication

From the **MCP server** (192.168.1.224), set up SSH key auth to the worker node:

```bash
# On the MCP server (192.168.1.224)
# If the jexida user doesn't have an SSH key, create one:
sudo -u jexida ssh-keygen -t ed25519 -N "" -f /home/jexida/.ssh/id_ed25519

# Copy the public key to the worker node:
sudo -u jexida ssh-copy-id jexida@192.168.0.66

# Test the connection:
sudo -u jexida ssh jexida@192.168.0.66 "echo 'SSH connection successful'"
```

Alternatively, manually add the key on the worker node:

```bash
# On the worker node
sudo mkdir -p /home/jexida/.ssh
sudo chmod 700 /home/jexida/.ssh

# Add the MCP server's public key
echo "YOUR_PUBLIC_KEY_HERE" | sudo tee -a /home/jexida/.ssh/authorized_keys
sudo chmod 600 /home/jexida/.ssh/authorized_keys
sudo chown -R jexida:jexida /home/jexida/.ssh
```

## Step 3: Install Python 3 and Dependencies

On the worker node, ensure Python 3 is installed:

```bash
# On the worker node
sudo apt update
sudo apt install -y python3 python3-pip python3-venv

# Verify installation
python3 --version
```

## Step 4: Create Job Directories

Create standard directories for job output and logs:

```bash
# On the worker node
sudo mkdir -p /opt/jexida-jobs
sudo mkdir -p /var/log/jexida-jobs

# Set ownership
sudo chown jexida:jexida /opt/jexida-jobs
sudo chown jexida:jexida /var/log/jexida-jobs
```

## Step 5: (Optional) Clone JexidaMCP Worker Tools

If the worker needs access to specific JexidaMCP scripts:

```bash
# On the worker node
cd /opt
sudo -u jexida git clone https://github.com/your-org/jexidamcp-worker.git jexida-worker
```

## Step 6: Register the Worker Node in JexidaMCP

On the MCP server, add the worker node to the database:

### Option A: Via Django Shell

```bash
# On the MCP server (192.168.1.224)
cd /opt/jexida-mcp
source venv/bin/activate
cd jexida_dashboard

python manage.py shell <<EOF
from mcp_tools_core.models import WorkerNode
WorkerNode.objects.update_or_create(
    name='JexidaDroid1',
    defaults={
        'host': '192.168.0.66',
        'user': 'jexida',
        'ssh_port': 22,
        'tags': 'ubuntu,worker',
        'is_active': True,
    }
)
print("Worker node registered!")
EOF
```

### Option B: Via Django Admin

1. Navigate to http://192.168.1.224:8080/admin/
2. Log in with admin credentials
3. Go to "MCP Tools Core" → "Worker Nodes"
4. Click "Add Worker Node"
5. Fill in the details:
   - Name: `JexidaDroid1`
   - Host: `192.168.0.66`
   - User: `jexida`
   - SSH Port: `22`
   - Tags: `ubuntu,worker`
   - Is Active: ✓

## Step 7: Verify Connectivity

Use the MCP tools to verify the worker node is reachable:

### Via CLI

```bash
jexida
/nodes list
/nodes check JexidaDroid1
```

### Via API

```bash
curl -X POST http://192.168.1.224:8080/tools/api/tools/check_worker_node/run/ \
  -H "Content-Type: application/json" \
  -d '{"name": "JexidaDroid1", "detailed": true}'
```

### Via Dashboard

1. Navigate to http://192.168.1.224:8080/jobs/nodes/
2. Click "Check" on the node card
3. Verify you see "Reachable" with system info

## Troubleshooting

### SSH Connection Refused

```bash
# Check if SSH is running on the worker
sudo systemctl status ssh

# Check firewall rules
sudo ufw status
sudo ufw allow ssh
```

### Permission Denied

```bash
# Verify key permissions on worker node
ls -la /home/jexida/.ssh/

# Permissions should be:
# .ssh directory: 700
# authorized_keys: 600
```

### Host Key Verification Failed

The MCP SSH executor uses `StrictHostKeyChecking=accept-new` by default. If you see host key issues:

```bash
# On the MCP server, manually accept the host key
sudo -u jexida ssh jexida@192.168.0.66
```

### Python Not Found

```bash
# Install Python on the worker
sudo apt update && sudo apt install -y python3
```

## Security Considerations

1. **Limit sudo access**: Only grant sudo if the worker needs to run privileged commands
2. **Use dedicated user**: The `jexida` user should only be used for MCP job execution
3. **Firewall**: Restrict SSH access to the MCP server's IP only
4. **Audit logs**: Check `/var/log/auth.log` for SSH access logs

## Adding Multiple Worker Nodes

To add more worker nodes, repeat steps 1-7 for each server. Use unique names like:
- `node-ubuntu-1`
- `node-gpu-0` (for GPU-enabled nodes)
- `node-docker-0` (for Docker hosts)

Use tags to categorize nodes for job routing:
- `gpu`: Nodes with GPU acceleration
- `docker`: Nodes with Docker installed
- `high-memory`: Nodes with large RAM
- `ssd`: Nodes with fast storage

