# WSL2 SSH Workaround Guide

## Problem

SSH from devcontainer to `192.168.1.224` times out because Docker Desktop on WSL2 isolates containers from the host's LAN network.

## Quick Solution: Test from WSL2 Directly

**Step 1:** Exit the devcontainer (close VS Code or use `F1` → `Dev Containers: Reopen Folder Locally`)

**Step 2:** Open WSL2 terminal and test SSH:
```bash
ssh jexida@192.168.1.224 "echo 'test'"
```

**Step 3:** If SSH works from WSL2, you have two options:

### Option A: Work from WSL2 (Recommended)
- Open VS Code from WSL2: `code .` (from WSL2 terminal)
- Install dependencies: `pip install -e .`
- SSH will work normally

### Option B: Use SSH Proxy/Jump Host (Advanced)
Set up an SSH proxy through the WSL2 host (requires additional configuration)

## Why This Happens

Docker Desktop on Windows/WSL2 runs in a VM that:
- Has its own network (`192.168.65.x`)
- Cannot directly access Windows host's LAN (`192.168.1.x`)
- `--network=host` doesn't work (Windows limitation)

## Docker Desktop Configuration (If Needed)

1. Open Docker Desktop
2. Settings → Resources → WSL Integration
3. Ensure your WSL distro is enabled
4. Restart Docker Desktop

This won't fix the network isolation, but ensures Docker uses WSL2 backend properly.

## Alternative: Use Docker Compose with Custom Network

You could create a `docker-compose.yml` with custom network configuration, but this is complex and may not solve the issue.

## Recommended Approach

**For development:** Work directly from WSL2 instead of devcontainer when you need SSH access to local network servers.

**For CI/CD:** Use a different approach (GitHub Actions, etc.) that has proper network access.

