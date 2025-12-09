#!/bin/bash
# Post-create script for Dev Container
# This runs after the container is created

set -e

echo "=========================================="
echo "Setting up JexidaMCP Development Environment"
echo "=========================================="

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install project dependencies
echo "Installing project dependencies..."
pip install -e .

# Install server dependencies
echo "Installing server dependencies..."
if [ -f "mcp_server_files/requirements.txt" ]; then
    pip install -r mcp_server_files/requirements.txt
else
    echo "Warning: mcp_server_files/requirements.txt not found"
fi

# Verify installation
echo ""
echo "Verifying installation..."
python3 --version
python3 -c "import jexida_cli; print('✓ jexida_cli imported successfully')" || echo "⚠ jexida_cli import failed"

echo ""
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "You can now use:"
echo "  - python3 get_ssh_output.py (for SSH commands)"
echo "  - python3 migrate_secrets.py (for secret migration)"
echo "  - All other project scripts"
echo ""

