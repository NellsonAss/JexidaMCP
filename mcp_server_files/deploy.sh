#!/bin/bash
# JexidaMCP Deployment Script for Ubuntu Server
# Run this script on the target server to set up the application

set -e

# Configuration
APP_DIR="/opt/jexida-mcp"
APP_USER="jexida"
PYTHON_VERSION="python3"

echo "=============================================="
echo "JexidaMCP Deployment Script"
echo "=============================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo)"
    exit 1
fi

# Create application user if it doesn't exist
if ! id "$APP_USER" &>/dev/null; then
    echo "Creating user: $APP_USER"
    useradd -r -s /bin/false -d "$APP_DIR" "$APP_USER"
fi

# Create application directory
echo "Setting up application directory: $APP_DIR"
mkdir -p "$APP_DIR"

# Copy application files (assumes script is run from mcp_server_files directory)
echo "Copying application files..."
cp -r . "$APP_DIR/"

# Create virtual environment
echo "Creating Python virtual environment..."
cd "$APP_DIR"
$PYTHON_VERSION -m venv venv
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Generate secrets if .env doesn't exist
if [ ! -f "$APP_DIR/.env" ]; then
    echo "Creating .env from template..."
    cp env.production .env
    
    # Generate encryption key
    ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    sed -i "s/SECRET_ENCRYPTION_KEY=CHANGE_ME_GENERATE_A_KEY/SECRET_ENCRYPTION_KEY=$ENCRYPTION_KEY/" .env
    
    # Generate session secret
    SESSION_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/AUTH_SESSION_SECRET=CHANGE_ME_GENERATE_A_SECRET/AUTH_SESSION_SECRET=$SESSION_SECRET/" .env
    
    echo ""
    echo "=============================================="
    echo "IMPORTANT: Set your password in .env file!"
    echo "Edit $APP_DIR/.env and set AUTH_PASSWORD"
    echo "=============================================="
fi

# Set permissions
echo "Setting permissions..."
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chmod 600 "$APP_DIR/.env"
chmod 600 "$APP_DIR/secrets.db" 2>/dev/null || true

# Install systemd service
echo "Installing systemd service..."
cp jexida-mcp.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable jexida-mcp

echo ""
echo "=============================================="
echo "Deployment complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo "1. Edit $APP_DIR/.env and set AUTH_PASSWORD"
echo "2. Start the service: systemctl start jexida-mcp"
echo "3. Check status: systemctl status jexida-mcp"
echo "4. View logs: journalctl -u jexida-mcp -f"
echo ""
echo "The dashboard will be available at: http://$(hostname -I | awk '{print $1}'):8080"







