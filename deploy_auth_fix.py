#!/usr/bin/env python3
"""
Deploy auth fix to remote server.

This script:
1. Copies server.py to remote server
2. Verifies the file was copied correctly
3. Restarts the jexida-mcp service
4. Checks service status
"""
import sys
import subprocess
import json
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from jexida_cli.ssh_client import SSHClient

HOST = "192.168.1.224"
USER = "jexida"
LOCAL_FILE = Path("mcp_server_files/server.py")
REMOTE_PATH = "/opt/jexida-mcp/server.py"
SERVICE_NAME = "jexida-mcp.service"

def run_ssh_command(command: str) -> tuple:
    """Run SSH command and return (stdout, stderr, exit_code)."""
    client = SSHClient(host=HOST, user=USER)
    return client.execute_command(command)

def main():
    print("=" * 60)
    print("Deploying Auth Fix to Remote Server")
    print("=" * 60)
    
    # Step 1: Verify local file has the fix
    print(f"\n1. Checking local file: {LOCAL_FILE}")
    if not LOCAL_FILE.exists():
        print(f"   ✗ Local file not found!")
        return 1
    
    with open(LOCAL_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
        if 'TEMPORARILY DISABLED' in content and 'return False' in content:
            print(f"   ✓ Local file has auth disabled")
        else:
            print(f"   ✗ Local file doesn't have the fix!")
            return 1
    
    # Step 2: Copy file using SCP
    print(f"\n2. Copying file to remote server...")
    scp_command = ["scp", str(LOCAL_FILE), f"{USER}@{HOST}:{REMOTE_PATH}"]
    try:
        result = subprocess.run(scp_command, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            print(f"   ✓ File copied successfully")
        else:
            print(f"   ✗ SCP failed: {result.stderr}")
            return 1
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return 1
    
    # Step 3: Verify remote file has the fix
    print(f"\n3. Verifying remote file...")
    stdout, stderr, exit_code = run_ssh_command(f"grep -A 3 'def is_auth_enabled' {REMOTE_PATH}")
    if exit_code == 0 and 'return False' in stdout:
        print(f"   ✓ Remote file has auth disabled")
        print(f"   Content: {stdout.strip()}")
    else:
        print(f"   ✗ Remote file verification failed")
        print(f"   Exit code: {exit_code}")
        print(f"   Stdout: {stdout}")
        print(f"   Stderr: {stderr}")
        return 1
    
    # Step 4: Restart service
    print(f"\n4. Restarting service: {SERVICE_NAME}")
    stdout, stderr, exit_code = run_ssh_command(f"sudo systemctl restart {SERVICE_NAME}")
    if exit_code == 0:
        print(f"   ✓ Service restarted")
    else:
        print(f"   ✗ Service restart failed")
        print(f"   Exit code: {exit_code}")
        print(f"   Stderr: {stderr}")
        return 1
    
    # Step 5: Check service status
    print(f"\n5. Checking service status...")
    stdout, stderr, exit_code = run_ssh_command(f"systemctl status {SERVICE_NAME} --no-pager")
    if exit_code == 0:
        print(f"   ✓ Service is running")
        # Show first few lines
        lines = stdout.split('\n')[:5]
        for line in lines:
            print(f"   {line}")
    else:
        print(f"   ⚠ Service status check returned non-zero exit code")
        print(f"   Output: {stdout}")
    
    print("\n" + "=" * 60)
    print("Deployment complete!")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())




