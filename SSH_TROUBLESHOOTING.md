# SSH Connection Troubleshooting Guide

## Problem: SSH Connection Timeout

If you're experiencing `Connection timed out` when trying to SSH to `192.168.1.224` from the devcontainer, this is likely a network isolation issue.

## Root Cause

Devcontainers run in Docker, which by default isolates containers from the host's local network. On WSL2/Windows, this isolation is even more pronounced because:
- WSL2 uses a virtual network adapter
- Docker Desktop creates its own network bridge
- Containers can't directly access the host's LAN (192.168.x.x)

## Solutions

### Solution 1: Use Host Network Mode (Linux/Mac)

If you're on Linux or Mac, the devcontainer is configured to use host networking:

```json
"runArgs": ["--network=host"]
```

**To apply this fix:**
1. Rebuild the devcontainer: `F1` → `Dev Containers: Rebuild Container`
2. Test SSH: `ssh jexida@192.168.1.224 "echo 'test'"`

### Solution 2: WSL2 Network Bridge (Windows/WSL2)

On Windows/WSL2, host networking doesn't work. Instead:

1. **Find your WSL2 IP address:**
   ```bash
   # From Windows PowerShell or CMD
   wsl hostname -I
   ```

2. **From WSL2, test if server is reachable:**
   ```bash
   # Inside WSL2 (not in devcontainer)
   ssh jexida@192.168.1.224 "echo 'test'"
   ```

3. **If SSH works from WSL2 but not from devcontainer:**
   - The devcontainer needs to use WSL2's network
   - Try accessing via the WSL2 host IP instead
   - Or configure Docker Desktop to use WSL2 backend

### Solution 3: Docker Desktop Network Configuration (Windows)

1. Open Docker Desktop
2. Go to Settings → Resources → Network
3. Ensure "Use WSL 2 based engine" is enabled
4. Try restarting Docker Desktop

### Solution 4: Use Host Gateway (Alternative)

If host networking doesn't work, you can try accessing the host via `host.docker.internal`:

```bash
# Test if host gateway is accessible
ping host.docker.internal
```

Then configure SSH to route through the host gateway (requires additional setup).

### Solution 5: Run from WSL2 Directly (Bypass Devcontainer)

If devcontainer networking continues to be problematic:

1. Open WSL2 terminal
2. Navigate to project: `cd /mnt/c/Dev/JexidaMCP` (adjust path)
3. Run commands directly from WSL2

## Verification Steps

1. **Check container network:**
   ```bash
   ip route show
   hostname -I
   ```

2. **Test connectivity:**
   ```bash
   ssh -v jexida@192.168.1.224 "echo 'test'" 2>&1 | head -20
   ```

3. **Check if server is actually reachable:**
   - Verify server is running: `ping 192.168.1.224` (if ping works)
   - Check SSH service: `ssh -v` output shows connection attempts
   - Verify firewall rules on server

## Common Error Messages

- **"Connection timed out"**: Network isolation or server unreachable
- **"Connection refused"**: Server is down or SSH not running
- **"Permission denied"**: SSH key authentication failed
- **"Host key verification failed"**: SSH known_hosts issue

## Quick Test

Run this to diagnose:
```bash
ssh -v -o ConnectTimeout=10 jexida@192.168.1.224 "echo 'test'" 2>&1 | grep -E "(Connecting|timeout|refused|Permission)"
```

## Next Steps

If none of these solutions work:
1. Verify the server at 192.168.1.224 is actually running and accessible
2. Check if you can SSH from your host machine (outside devcontainer)
3. Consider using a VPN or SSH tunnel if server is on a different network
4. Check Docker Desktop/WSL2 network settings


