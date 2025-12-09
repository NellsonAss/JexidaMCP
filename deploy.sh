#!/bin/bash
# Django Dashboard Deployment Script
# Run this from your host machine (not the devcontainer)

set -e

HOST="192.168.1.224"
USER="jexida"
APP_DIR="/opt/jexida-mcp"

echo "=============================================="
echo "Deploying Django Dashboard to MCP Server"
echo "=============================================="

# Check SSH access
echo ""
echo "1. Testing SSH connection..."
if ! ssh -o ConnectTimeout=5 ${USER}@${HOST} "echo 'SSH OK'" 2>/dev/null; then
    echo "   ✗ Cannot connect to ${USER}@${HOST}"
    echo "   Make sure SSH is running and you have access."
    exit 1
fi
echo "   ✓ SSH connection OK"

# Create directories
echo ""
echo "2. Creating remote directories..."
ssh ${USER}@${HOST} "mkdir -p ${APP_DIR}/jexida_dashboard ${APP_DIR}/core"
echo "   ✓ Directories created"

# Sync Django project
echo ""
echo "3. Syncing Django project..."
rsync -avz --delete \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.git' \
    --exclude 'db.sqlite3' \
    --exclude 'staticfiles' \
    jexida_dashboard/ ${USER}@${HOST}:${APP_DIR}/jexida_dashboard/
echo "   ✓ Django project synced"

# Sync core services
echo ""
echo "4. Syncing core services..."
rsync -avz --delete \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.git' \
    core/ ${USER}@${HOST}:${APP_DIR}/core/
echo "   ✓ Core services synced"

# Install dependencies
echo ""
echo "5. Installing Python dependencies..."
ssh ${USER}@${HOST} "cd ${APP_DIR} && source venv/bin/activate && pip install django gunicorn python-dotenv dj-database-url"
echo "   ✓ Dependencies installed"

# Run migrations
echo ""
echo "6. Running Django migrations..."
ssh ${USER}@${HOST} "cd ${APP_DIR}/jexida_dashboard && source ${APP_DIR}/venv/bin/activate && export PYTHONPATH=${APP_DIR} && python manage.py migrate --noinput"
echo "   ✓ Migrations complete"

# Collect static files
echo ""
echo "7. Collecting static files..."
ssh ${USER}@${HOST} "cd ${APP_DIR}/jexida_dashboard && source ${APP_DIR}/venv/bin/activate && export PYTHONPATH=${APP_DIR} && python manage.py collectstatic --noinput" || true
echo "   ✓ Static files collected"

# Update systemd service
echo ""
echo "8. Updating systemd service..."
scp jexida_dashboard/jexida-django.service ${USER}@${HOST}:/tmp/jexida-django.service
ssh ${USER}@${HOST} "sudo mv /tmp/jexida-django.service /etc/systemd/system/jexida-mcp.service && sudo systemctl daemon-reload"
echo "   ✓ Service updated"

# Restart service
echo ""
echo "9. Restarting service..."
ssh ${USER}@${HOST} "sudo systemctl restart jexida-mcp.service"
sleep 3
echo "   ✓ Service restarted"

# Check status
echo ""
echo "10. Checking service status..."
ssh ${USER}@${HOST} "systemctl status jexida-mcp.service --no-pager -n 5" || true

echo ""
echo "=============================================="
echo "Deployment complete!"
echo "=============================================="
echo ""
echo "Dashboard available at: http://${HOST}:8080/"
echo ""
echo "To check logs: ssh ${USER}@${HOST} 'sudo journalctl -u jexida-mcp.service -f'"

