#!/usr/bin/env python3
"""Test config loading on remote server."""
from config import get_settings

s = get_settings()
print(f"UniFi URL: {s.unifi_controller_url}")
print(f"UniFi User: {s.unifi_username}")
print(f"UniFi Site: {s.unifi_site}")


