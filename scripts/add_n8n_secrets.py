#!/usr/bin/env python3
"""Add n8n credentials to the secrets store."""

import os
import sys
import django

# Setup Django - script is in /opt/jexida-mcp/scripts/
# Django project is in /opt/jexida-mcp/jexida_dashboard/
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
dashboard_dir = os.path.join(project_root, 'jexida_dashboard')

sys.path.insert(0, dashboard_dir)
os.chdir(dashboard_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jexida_dashboard.settings')
django.setup()

from secrets_app.models import Secret


def add_n8n_secrets():
    """Add n8n credentials to encrypted secrets store.
    
    Reads values from environment variables:
    - N8N_URL (default: http://192.168.1.254:5678)
    - N8N_USERNAME (default: admin)
    - N8N_PASSWORD (required)
    - N8N_ENCRYPTION_KEY (required)
    """
    
    n8n_url = os.environ.get("N8N_URL", "http://192.168.1.254:5678")
    n8n_username = os.environ.get("N8N_USERNAME", "admin")
    n8n_password = os.environ.get("N8N_PASSWORD")
    n8n_encryption_key = os.environ.get("N8N_ENCRYPTION_KEY")
    
    if not n8n_password:
        print("ERROR: N8N_PASSWORD environment variable is required")
        sys.exit(1)
    
    if not n8n_encryption_key:
        print("ERROR: N8N_ENCRYPTION_KEY environment variable is required")
        sys.exit(1)
    
    secrets_to_add = [
        {
            "name": "n8n URL",
            "service_type": "n8n",
            "key": "url",
            "value": n8n_url,
        },
        {
            "name": "n8n Username",
            "service_type": "n8n",
            "key": "username",
            "value": n8n_username,
        },
        {
            "name": "n8n Password",
            "service_type": "n8n",
            "key": "password",
            "value": n8n_password,
        },
        {
            "name": "n8n Encryption Key",
            "service_type": "n8n",
            "key": "encryption_key",
            "value": n8n_encryption_key,
        },
    ]
    
    for secret_data in secrets_to_add:
        # Check if exists
        existing = Secret.objects.filter(
            service_type=secret_data["service_type"],
            key=secret_data["key"]
        ).first()
        
        if existing:
            print(f"Updating existing secret: {secret_data['name']}")
            existing.name = secret_data["name"]
            existing.set_value(secret_data["value"])
            existing.save()
        else:
            print(f"Creating new secret: {secret_data['name']}")
            secret = Secret(
                name=secret_data["name"],
                service_type=secret_data["service_type"],
                key=secret_data["key"],
            )
            secret.set_value(secret_data["value"])
            secret.save()
    
    print("\n✓ n8n secrets added to encrypted store")
    print("\nSecrets now in database:")
    for s in Secret.objects.filter(service_type="n8n"):
        print(f"  - {s.name} ({s.key})")


if __name__ == "__main__":
    add_n8n_secrets()

