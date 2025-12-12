"""Quick script to get WiFi client count from UniFi controller."""

import asyncio
import sys
sys.path.insert(0, '.')
from mcp_tools.unifi.client import UniFiClient

async def get_clients():
    async with UniFiClient() as client:
        # stat/sta returns all connected stations (clients)
        clients = await client._get('stat/sta')
        wifi_clients = [c for c in clients if c.get('is_wired') == False]
        wired_clients = [c for c in clients if c.get('is_wired') == True]
        print(f'Total connected devices: {len(clients)}')
        print(f'WiFi clients: {len(wifi_clients)}')
        print(f'Wired clients: {len(wired_clients)}')
        print()
        print('WiFi clients:')
        for c in wifi_clients:
            name = c.get('name') or c.get('hostname') or c.get('mac', 'Unknown')
            ip = c.get('ip', 'N/A')
            essid = c.get('essid', 'N/A')
            print(f'  - {name}: {ip} ({essid})')

if __name__ == '__main__':
    asyncio.run(get_clients())

