#!/usr/bin/env python3
"""Check UniFi secrets - decrypt with provided key."""
import sqlite3
from cryptography.fernet import Fernet
import sys

def main():
    # Check MCP server database
    db_path = 'mcp_server_files/secrets.db'
    
    # Get encryption key from command line or environment
    key = None
    if len(sys.argv) > 1:
        key = sys.argv[1]
    
    print(f"Checking: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT key, encrypted_value FROM secrets WHERE service_type='unifi'")
    results = cursor.fetchall()
    
    if results:
        print("\nUniFi secrets stored:")
        for key_name, encrypted_value in results:
            if key:
                try:
                    fernet = Fernet(key.encode())
                    decrypted = fernet.decrypt(encrypted_value.encode()).decode()
                    print(f"  {key_name}: {decrypted}")
                except Exception as e:
                    print(f"  {key_name}: [encrypted] (decrypt error: {e})")
            else:
                print(f"  {key_name}: [encrypted]")
        
        if not key:
            print("\nTo decrypt, provide SECRET_ENCRYPTION_KEY as argument:")
            print("  python check_unifi.py <encryption_key>")
    else:
        print("No UniFi secrets found")
    
    conn.close()

if __name__ == '__main__':
    main()

