#!/usr/bin/env python3
"""
Deploy Django dashboard to remote MCP server.

This script:
1. Pushes code to GitHub
2. SSH to server and pulls latest code
3. Installs dependencies
4. Runs Django migrations
5. Collects static files
6. Updates systemd service to run Django
7. Restarts the service
"""
import sys
import subprocess
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from jexida_cli.ssh_client import SSHClient

HOST = "192.168.1.224"
USER = "jexida"
APP_DIR = "/opt/jexida-mcp"
DJANGO_DIR = f"{APP_DIR}/jexida_dashboard"
SERVICE_NAME = "jexida-mcp.service"


def run_local_command(command: list) -> tuple:
    """Run a local command and return (stdout, stderr, exit_code)."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", 124
    except Exception as e:
        return "", str(e), 1


def run_ssh_command(command: str) -> tuple:
    """Run SSH command and return (stdout, stderr, exit_code)."""
    client = SSHClient(host=HOST, user=USER)
    return client.execute_command(command)


def main():
    print("=" * 60)
    print("Deploying Django Dashboard to MCP Server")
    print("=" * 60)

    # Step 1: Push to GitHub
    print("\n1. Pushing code to GitHub...")
    
    # Add all files
    stdout, stderr, exit_code = run_local_command(["git", "add", "-A"])
    if exit_code != 0:
        print(f"   ⚠ git add warning: {stderr}")
    
    # Commit (may fail if nothing to commit)
    stdout, stderr, exit_code = run_local_command(
        ["git", "commit", "-m", "Deploy Django dashboard migration"]
    )
    if exit_code == 0:
        print("   ✓ Changes committed")
    else:
        print(f"   ⚠ Commit: {stdout.strip() or stderr.strip()}")
    
    # Push
    stdout, stderr, exit_code = run_local_command(["git", "push", "origin", "HEAD"])
    if exit_code == 0:
        print("   ✓ Pushed to GitHub")
    else:
        print(f"   ✗ Push failed: {stderr}")
        return 1

    # Step 2: Pull on remote server
    print(f"\n2. Pulling latest code on server ({HOST})...")
    stdout, stderr, exit_code = run_ssh_command(f"cd {APP_DIR} && git pull origin HEAD")
    if exit_code == 0:
        print(f"   ✓ Code pulled")
        if stdout.strip():
            for line in stdout.strip().split('\n')[:5]:
                print(f"      {line}")
    else:
        print(f"   ✗ Git pull failed: {stderr}")
        return 1

    # Step 3: Install Python dependencies (including Django, gunicorn)
    print("\n3. Installing Python dependencies...")
    deps_cmd = f"""
cd {APP_DIR} && 
source venv/bin/activate && 
pip install django gunicorn python-dotenv dj-database-url cryptography
"""
    stdout, stderr, exit_code = run_ssh_command(deps_cmd)
    if exit_code == 0:
        print("   ✓ Dependencies installed")
    else:
        print(f"   ✗ Dependency install failed: {stderr}")
        return 1

    # Step 4: Run Django migrations
    print("\n4. Running Django migrations...")
    migrate_cmd = f"""
cd {DJANGO_DIR} && 
source {APP_DIR}/venv/bin/activate && 
python manage.py migrate --noinput
"""
    stdout, stderr, exit_code = run_ssh_command(migrate_cmd)
    if exit_code == 0:
        print("   ✓ Migrations applied")
        if stdout.strip():
            for line in stdout.strip().split('\n')[-5:]:
                print(f"      {line}")
    else:
        print(f"   ✗ Migration failed: {stderr}")
        print(f"   stdout: {stdout}")
        return 1

    # Step 5: Collect static files
    print("\n5. Collecting static files...")
    static_cmd = f"""
cd {DJANGO_DIR} && 
source {APP_DIR}/venv/bin/activate && 
python manage.py collectstatic --noinput
"""
    stdout, stderr, exit_code = run_ssh_command(static_cmd)
    if exit_code == 0:
        print("   ✓ Static files collected")
    else:
        print(f"   ⚠ Static collection warning: {stderr}")

    # Step 6: Update systemd service for Django
    print("\n6. Updating systemd service for Django...")
    
    # Copy new service file
    scp_cmd = [
        "scp",
        "jexida_dashboard/jexida-django.service",
        f"{USER}@{HOST}:/tmp/jexida-django.service"
    ]
    result = subprocess.run(scp_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"   ✗ Failed to copy service file: {result.stderr}")
        return 1
    print("   ✓ Service file copied")
    
    # Install service file (requires sudo)
    service_cmd = f"""
sudo mv /tmp/jexida-django.service /etc/systemd/system/{SERVICE_NAME} && 
sudo systemctl daemon-reload
"""
    stdout, stderr, exit_code = run_ssh_command(service_cmd)
    if exit_code == 0:
        print("   ✓ Service file installed")
    else:
        print(f"   ✗ Service install failed: {stderr}")
        return 1

    # Step 7: Restart service
    print(f"\n7. Restarting service: {SERVICE_NAME}...")
    stdout, stderr, exit_code = run_ssh_command(f"sudo systemctl restart {SERVICE_NAME}")
    if exit_code == 0:
        print("   ✓ Service restarted")
    else:
        print(f"   ✗ Service restart failed: {stderr}")
        return 1

    # Step 8: Check service status
    print("\n8. Checking service status...")
    import time
    time.sleep(3)  # Give service time to start
    
    stdout, stderr, exit_code = run_ssh_command(f"systemctl status {SERVICE_NAME} --no-pager -n 10")
    if exit_code == 0 or "Active: active" in stdout:
        print("   ✓ Service is running")
        for line in stdout.strip().split('\n')[:15]:
            print(f"      {line}")
    else:
        print(f"   ⚠ Service status: {exit_code}")
        print(f"   {stdout}")
        print(f"   {stderr}")

    # Step 9: Test health endpoint
    print("\n9. Testing Django dashboard...")
    stdout, stderr, exit_code = run_ssh_command("curl -s http://localhost:8080/")
    if exit_code == 0 and len(stdout) > 0:
        print(f"   ✓ Dashboard responding ({len(stdout)} bytes)")
    else:
        print(f"   ⚠ Dashboard test inconclusive")
        print(f"   Response: {stdout[:200] if stdout else 'empty'}")

    print(f"\n{'=' * 60}")
    print("Deployment complete!")
    print(f"{'=' * 60}")
    print(f"\nDjango Dashboard available at: http://{HOST}:8080/")

    return 0


if __name__ == "__main__":
    sys.exit(main())

