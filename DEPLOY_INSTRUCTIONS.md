# Django Dashboard Deployment Instructions

The devcontainer cannot directly SSH to your local network (192.168.1.224). 
You need to run the deployment from your **local machine** or a terminal with network access.

## Quick Deploy

### Option 1: Run from your local machine (recommended)

1. Open a terminal **outside** the devcontainer (e.g., Windows PowerShell, WSL, or macOS Terminal)

2. Navigate to your project directory:
   ```bash
   cd /path/to/JexidaMCP
   ```

3. Run the deployment script:
   ```bash
   python deploy_django.py
   ```

   Or if Python isn't set up locally, run these commands manually:

### Option 2: Manual deployment via SSH

From a terminal with access to 192.168.1.224:

```bash
# 1. Create directories on server
ssh jexida@192.168.1.224 "mkdir -p /opt/jexida-mcp/jexida_dashboard /opt/jexida-mcp/core"

# 2. Sync Django project
rsync -avz --delete \
    --exclude '__pycache__' --exclude '*.pyc' --exclude '.git' \
    --exclude 'db.sqlite3' --exclude 'staticfiles' \
    jexida_dashboard/ jexida@192.168.1.224:/opt/jexida-mcp/jexida_dashboard/

# 3. Sync core services
rsync -avz --delete \
    --exclude '__pycache__' --exclude '*.pyc' --exclude '.git' \
    core/ jexida@192.168.1.224:/opt/jexida-mcp/core/

# 4. Install dependencies
ssh jexida@192.168.1.224 "cd /opt/jexida-mcp && source venv/bin/activate && pip install django gunicorn python-dotenv dj-database-url"

# 5. Run migrations
ssh jexida@192.168.1.224 "cd /opt/jexida-mcp/jexida_dashboard && source /opt/jexida-mcp/venv/bin/activate && export PYTHONPATH=/opt/jexida-mcp && python manage.py migrate --noinput"

# 6. Collect static files
ssh jexida@192.168.1.224 "cd /opt/jexida-mcp/jexida_dashboard && source /opt/jexida-mcp/venv/bin/activate && export PYTHONPATH=/opt/jexida-mcp && python manage.py collectstatic --noinput"

# 7. Copy and install systemd service
scp jexida_dashboard/jexida-django.service jexida@192.168.1.224:/tmp/
ssh jexida@192.168.1.224 "sudo mv /tmp/jexida-django.service /etc/systemd/system/jexida-mcp.service && sudo systemctl daemon-reload"

# 8. Restart service
ssh jexida@192.168.1.224 "sudo systemctl restart jexida-mcp.service"

# 9. Check status
ssh jexida@192.168.1.224 "sudo systemctl status jexida-mcp.service"
```

## After Deployment

The Django dashboard will be available at: **http://192.168.1.224:8080/**

### Troubleshooting

If the service fails to start, check logs:
```bash
ssh jexida@192.168.1.224 "sudo journalctl -u jexida-mcp.service -n 50"
```

If there are import errors, ensure PYTHONPATH is set:
```bash
ssh jexida@192.168.1.224 "cd /opt/jexida-mcp/jexida_dashboard && source /opt/jexida-mcp/venv/bin/activate && export PYTHONPATH=/opt/jexida-mcp && python -c 'import core; print(core)'"
```

### Rolling Back to FastAPI

If you need to roll back to the original FastAPI server:

```bash
# Restore original service file
ssh jexida@192.168.1.224 "sudo cp /opt/jexida-mcp/mcp_server_files/jexida-mcp.service /etc/systemd/system/jexida-mcp.service && sudo systemctl daemon-reload && sudo systemctl restart jexida-mcp.service"
```

