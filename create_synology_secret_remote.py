#!/usr/bin/env python3
"""Script to create Synology secrets in the database on remote server.

This script creates the three required secrets for Synology NAS access:
- url: The Synology NAS URL
- username: The username for authentication
- password: The password for authentication
"""

import os
import sys
from pathlib import Path

# Change to the server directory
SERVER_DIR = Path("/opt/jexida-mcp")
os.chdir(SERVER_DIR)

# Add current directory to path
sys.path.insert(0, str(SERVER_DIR))

from getpass import getpass
from database import Secret, encrypt_value, get_session_local, init_db

# Synology credentials
SYNOLOGY_URL = "https://192.168.1.52:5001/"
SYNOLOGY_USERNAME = "Bludo"

def main():
    """Create Synology secrets."""
    # Initialize database (creates tables if they don't exist)
    init_db()
    
    # Get password from command line argument, environment variable, or prompt
    if len(sys.argv) > 1:
        password = sys.argv[1]
    elif os.environ.get("SYNOLOGY_PASSWORD"):
        password = os.environ.get("SYNOLOGY_PASSWORD")
    else:
        print(f"Creating Synology secrets for user: {SYNOLOGY_USERNAME}")
        print(f"URL: {SYNOLOGY_URL}")
        password = getpass("Enter password: ")
    
    if not password:
        print("Error: Password cannot be empty")
        sys.exit(1)
    
    # Create database session
    SessionLocal = get_session_local()
    db = SessionLocal()
    
    try:
        # Define the secrets to create
        secrets_to_create = [
            {
                "name": "Synology NAS URL",
                "service_type": "synology",
                "key": "url",
                "value": SYNOLOGY_URL
            },
            {
                "name": "Synology Username",
                "service_type": "synology",
                "key": "username",
                "value": SYNOLOGY_USERNAME
            },
            {
                "name": "Synology Password",
                "service_type": "synology",
                "key": "password",
                "value": password
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        for secret_data in secrets_to_create:
            # Check if secret already exists
            existing = db.query(Secret).filter(
                Secret.service_type == secret_data["service_type"],
                Secret.key == secret_data["key"]
            ).first()
            
            if existing:
                # Update existing secret
                encrypted = encrypt_value(secret_data["value"])
                existing.encrypted_value = encrypted
                existing.name = secret_data["name"]
                updated_count += 1
                print(f"Updated: {secret_data['service_type']}/{secret_data['key']}")
            else:
                # Create new secret
                encrypted = encrypt_value(secret_data["value"])
                secret = Secret(
                    name=secret_data["name"],
                    service_type=secret_data["service_type"],
                    key=secret_data["key"],
                    encrypted_value=encrypted
                )
                db.add(secret)
                created_count += 1
                print(f"Created: {secret_data['service_type']}/{secret_data['key']}")
        
        # Commit all changes
        db.commit()
        
        print(f"\nSuccess! Created {created_count} new secret(s), updated {updated_count} existing secret(s).")
        print("Synology secrets are now configured.")
        
    except Exception as e:
        db.rollback()
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()

