#!/usr/bin/env python3
"""Create Synology secrets via the web API.

This script uses HTTP POST requests to create secrets on the remote server.
"""

import sys
import requests
from urllib.parse import urljoin

# Server URL
SERVER_URL = "http://192.168.1.224:8080"

# Synology credentials
SYNOLOGY_URL = "https://192.168.1.52:5001/"
SYNOLOGY_USERNAME = "Bludo"

def create_secret(name, service_type, key, value):
    """Create a secret via POST request."""
    url = urljoin(SERVER_URL, "/secrets")
    data = {
        "name": name,
        "service_type": service_type,
        "key": key,
        "value": value
    }
    
    try:
        response = requests.post(url, data=data, allow_redirects=False)
        if response.status_code == 303:
            print(f"✓ Created: {service_type}/{key}")
            return True
        else:
            print(f"✗ Failed to create {service_type}/{key}: Status {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"✗ Error creating {service_type}/{key}: {e}")
        return False

def main():
    """Create Synology secrets."""
    if len(sys.argv) < 2:
        print("Usage: python3 create_synology_via_api.py <password>")
        print(f"Creating Synology secrets for user: {SYNOLOGY_USERNAME}")
        print(f"URL: {SYNOLOGY_URL}")
        sys.exit(1)
    
    password = sys.argv[1]
    
    if not password:
        print("Error: Password cannot be empty")
        sys.exit(1)
    
    print(f"Creating Synology secrets on {SERVER_URL}...")
    print(f"Username: {SYNOLOGY_USERNAME}")
    print(f"URL: {SYNOLOGY_URL}\n")
    
    secrets = [
        ("Synology NAS URL", "synology", "url", SYNOLOGY_URL),
        ("Synology Username", "synology", "username", SYNOLOGY_USERNAME),
        ("Synology Password", "synology", "password", password),
    ]
    
    success_count = 0
    for name, service_type, key, value in secrets:
        if create_secret(name, service_type, key, value):
            success_count += 1
    
    print(f"\n{'='*50}")
    if success_count == len(secrets):
        print(f"Success! Created {success_count} secret(s).")
        print("Synology secrets are now configured.")
    else:
        print(f"Warning: Only {success_count} of {len(secrets)} secrets were created.")
        print("Some secrets may already exist or there was an error.")

if __name__ == "__main__":
    main()

