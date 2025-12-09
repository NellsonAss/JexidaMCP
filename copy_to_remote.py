#!/usr/bin/env python3
"""
Helper script to copy files to remote server and restart service.

Usage:
    python3 copy_to_remote.py <local_file> <remote_path> [host] [user]
    
Example:
    python3 copy_to_remote.py mcp_server_files/server.py /opt/jexida-mcp/server.py
"""
import sys
import subprocess
import json
from pathlib import Path

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 copy_to_remote.py <local_file> <remote_path> [host] [user]")
        print("\nExample:")
        print("  python3 copy_to_remote.py mcp_server_files/server.py /opt/jexida-mcp/server.py")
        sys.exit(1)
    
    local_file = Path(sys.argv[1])
    remote_path = sys.argv[2]
    host = sys.argv[3] if len(sys.argv) > 3 else "192.168.1.224"
    user = sys.argv[4] if len(sys.argv) > 4 else "jexida"
    
    if not local_file.exists():
        print(f"Error: Local file not found: {local_file}")
        sys.exit(1)
    
    # Copy file using SCP
    scp_command = [
        "scp",
        str(local_file),
        f"{user}@{host}:{remote_path}"
    ]
    
    print(f"Copying {local_file} to {user}@{host}:{remote_path}...")
    try:
        result = subprocess.run(
            scp_command,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            print(f"✓ File copied successfully")
            print(f"  Remote path: {remote_path}")
            return 0
        else:
            print(f"✗ SCP failed with exit code {result.returncode}")
            print(f"  Stderr: {result.stderr}")
            return result.returncode
    except Exception as e:
        print(f"✗ Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

