#!/usr/bin/env python3
"""
Deploy database connection fix to remote server.

This script:
1. Copies server.py and database.py to remote server
2. Verifies the files were copied correctly
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
FILES_TO_DEPLOY = [
    ("mcp_server_files/server.py", "/opt/jexida-mcp/server.py"),
    ("mcp_server_files/database.py", "/opt/jexida-mcp/database.py"),
]
SERVICE_NAME = "jexida-mcp.service"

def run_ssh_command(command: str) -> tuple:
    """Run SSH command and return (stdout, stderr, exit_code)."""
    client = SSHClient(host=HOST, user=USER)
    return client.execute_command(command)

def main():
    print("=" * 60)
    print("Deploying Database Connection Fix to Remote Server")
    print("=" * 60)
    
    # Step 1: Verify local files exist
    print(f"\n1. Checking local files...")
    for local_file, remote_path in FILES_TO_DEPLOY:
        local_path = Path(local_file)
        if not local_path.exists():
            print(f"   ✗ Local file not found: {local_file}")
            return 1
        print(f"   ✓ Found: {local_file}")
    
    # Step 2: Copy files using SCP
    print(f"\n2. Copying files to remote server...")
    for local_file, remote_path in FILES_TO_DEPLOY:
        local_path = Path(local_file)
        scp_command = ["scp", str(local_path), f"{USER}@{HOST}:{remote_path}"]
        try:
            result = subprocess.run(scp_command, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                print(f"   ✓ Copied: {local_file} -> {remote_path}")
            else:
                print(f"   ✗ SCP failed for {local_file}: {result.stderr}")
                return 1
        except Exception as e:
            print(f"   ✗ Error copying {local_file}: {e}")
            return 1
    
    # Step 3: Verify remote files
    print(f"\n3. Verifying remote files...")
    for local_file, remote_path in FILES_TO_DEPLOY:
        # Check if file exists and has content
        stdout, stderr, exit_code = run_ssh_command(f"test -f {remote_path} && wc -l {remote_path}")
        if exit_code == 0:
            print(f"   ✓ Verified: {remote_path} ({stdout.strip()})")
        else:
            print(f"   ✗ Verification failed for {remote_path}")
            print(f"   Exit code: {exit_code}, Stderr: {stderr}")
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
    stdout, stderr, exit_code = run_ssh_command(f"systemctl status {SERVICE_NAME} --no-pager -n 10")
    if exit_code == 0:
        print(f"   ✓ Service status:")
        print(f"   {stdout}")
    else:
        print(f"   ⚠ Could not get service status (exit code: {exit_code})")
        print(f"   Stderr: {stderr}")
    
    # Step 6: Test health endpoint
    print(f"\n6. Testing health endpoint...")
    stdout, stderr, exit_code = run_ssh_command("curl -s http://localhost:8080/health")
    if exit_code == 0 and "healthy" in stdout:
        print(f"   ✓ Health check passed: {stdout.strip()}")
    else:
        print(f"   ⚠ Health check failed or inconclusive")
        print(f"   Response: {stdout}")
        print(f"   Stderr: {stderr}")
    
    print(f"\n{'=' * 60}")
    print("Deployment complete!")
    print(f"{'=' * 60}")
    print(f"\nServer should be available at: http://{HOST}:8080/")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())


