# Quick Start: Dev Container Setup

## Prerequisites Checklist

- [ ] Docker Desktop installed and running
- [ ] VS Code installed
- [ ] "Dev Containers" extension installed in VS Code

## Step-by-Step Instructions

### 1. Install Docker Desktop (if not already installed)

Download from: https://www.docker.com/products/docker-desktop/

Make sure Docker Desktop is **running** (you should see the Docker icon in your system tray).

### 2. Install VS Code Extension

1. Open VS Code
2. Press `Ctrl+Shift+X` to open Extensions
3. Search for "Dev Containers"
4. Install the extension by Microsoft (ms-vscode-remote.remote-containers)

### 3. Open Project in Dev Container

**Method 1: Command Palette**
1. Open VS Code in this directory (`C:\Dev\JexidaMCP`)
2. Press `F1` (or `Ctrl+Shift+P`)
3. Type: `Dev Containers: Reopen in Container`
4. Select it and wait for the container to build

**Method 2: Pop-up Notification**
- VS Code should detect the `.devcontainer` folder
- Click the pop-up notification: "Reopen in Container"

### 4. Wait for Container Setup

The first time will take 3-5 minutes as it:
- Downloads the base image
- Installs Python dependencies
- Sets up the development environment

You'll see progress in the VS Code terminal/output panel.

### 5. Verify It Works

Once the container is ready, open a terminal in VS Code (`Ctrl+`` ` or Terminal → New Terminal) and run:

```bash
python3 get_ssh_output.py 192.168.1.224 jexida "echo 'Hello from container!'" tmp/test.json
cat tmp/test.json
```

You should see:
- The command output directly in the terminal
- The JSON file contents displayed
- **No more PowerShell output capture issues!**

## Troubleshooting

### Docker Desktop Not Running
- Make sure Docker Desktop is running (check system tray)
- Restart Docker Desktop if needed

### Container Build Fails
- Check Docker Desktop logs
- Make sure you have enough disk space
- Try rebuilding: `F1` → `Dev Containers: Rebuild Container`

### SSH Not Working
- Your SSH keys should be automatically available
- If not, you may need to configure SSH agent forwarding
- Test: `ssh jexida@192.168.1.224` from container terminal

### Port Forwarding
- If you need to access services running in the container, use VS Code's port forwarding
- Right-click on forwarded ports in the Ports panel

## What's Different?

- **Terminal**: Now runs in Linux (bash) instead of PowerShell
- **Output**: Commands show output directly (no JSON workaround needed)
- **Environment**: Matches your remote Linux server
- **SSH**: Still works the same way

## Next Steps

Once the container is running:
1. Test terminal output: `python3 get_ssh_output.py ...`
2. Run migrations: `python3 migrate_secrets.py`
3. Develop normally - everything should work better!




