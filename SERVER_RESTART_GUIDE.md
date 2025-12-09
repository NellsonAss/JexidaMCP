# Server Restart Guide

## Current Status
- Server at `192.168.1.224:8080` is not responding
- SSH connection refused (port 22)
- HTTP health endpoint not responding

## Diagnosis Steps

### 1. Check if the server is running
```bash
# If you have SSH access:
ssh jexida@192.168.1.224 "systemctl status jexida-mcp.service"

# Or check if the process is running:
ssh jexida@192.168.1.224 "ps aux | grep uvicorn"
```

### 2. Check systemd service status
```bash
ssh jexida@192.168.1.224 "systemctl status jexida-mcp.service --no-pager"
```

### 3. Check recent logs
```bash
# Systemd journal logs
ssh jexida@192.168.1.224 "journalctl -u jexida-mcp.service -n 50 --no-pager"

# Or check application logs if they exist
ssh jexida@192.168.1.224 "tail -50 /opt/jexida-mcp/server.log"
```

## Restart Options

### Option 1: Restart via systemd (Recommended)
```bash
ssh jexida@192.168.1.224 "sudo systemctl restart jexida-mcp.service"
```

### Option 2: Start manually (if systemd service not working)
```bash
ssh jexida@192.168.1.224 "cd /opt/jexida-mcp && source venv/bin/activate && ./run.sh"
```

### Option 3: Direct uvicorn command
```bash
ssh jexida@192.168.1.224 "cd /opt/jexida-mcp && source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8080"
```

## Common Issues and Solutions

### Issue: Service keeps crashing
**Check logs for errors:**
```bash
ssh jexida@192.168.1.224 "journalctl -u jexida-mcp.service -n 100 --no-pager | grep -i error"
```

**Common causes:**
- Missing environment variables in `.env` file
- Database connection issues
- Port 8080 already in use
- Python dependencies missing

### Issue: Port 8080 already in use
```bash
# Check what's using port 8080
ssh jexida@192.168.1.224 "sudo lsof -i :8080"

# Kill the process if needed
ssh jexida@192.168.1.224 "sudo kill -9 <PID>"
```

### Issue: Missing dependencies
```bash
ssh jexida@192.168.1.224 "cd /opt/jexida-mcp && source venv/bin/activate && pip install -r requirements.txt"
```

### Issue: Environment variables not loaded
```bash
# Check if .env file exists
ssh jexida@192.168.1.224 "ls -la /opt/jexida-mcp/.env"

# Verify environment file is readable by systemd
ssh jexida@192.168.1.224 "sudo systemctl show jexida-mcp.service | grep EnvironmentFile"
```

## Verification

After restarting, verify the server is running:

```bash
# Check service status
ssh jexida@192.168.1.224 "systemctl status jexida-mcp.service"

# Test health endpoint
curl http://192.168.1.224:8080/health

# Should return: {"status":"healthy","version":"0.1.0"}
```

## If SSH is Not Available

If you have physical or console access to the server:

1. **Login directly** to the server
2. **Check system status:**
   ```bash
   systemctl status jexida-mcp.service
   ```
3. **Restart the service:**
   ```bash
   sudo systemctl restart jexida-mcp.service
   ```
4. **Check logs:**
   ```bash
   journalctl -u jexida-mcp.service -f
   ```

## Emergency Manual Start

If systemd service is completely broken:

```bash
cd /opt/jexida-mcp
source venv/bin/activate
export $(cat .env | xargs)  # Load environment variables
python main.py
```

Or use the run script:
```bash
cd /opt/jexida-mcp
./run.sh
```


