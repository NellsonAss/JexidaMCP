# Why SSH Suddenly Stopped Working

## Common Reasons for Sudden SSH Connection Loss

### 1. **Server IP Address Changed (Most Common)**
**What happened:** The server's IP address changed due to DHCP lease renewal
- Router assigned a new IP address
- Server rebooted and got a different IP
- Network configuration changed

**How to check:**
- Log into your router's admin panel
- Check DHCP client list for the server
- Look for hostname "jexida" or MAC address
- The IP might now be something like `192.168.1.225` or `192.168.1.230`

**Solution:** Update the IP address in your configuration

### 2. **Server Restarted/Crashed**
**What happened:** The server rebooted and SSH service didn't start
- Power outage
- System crash
- Manual restart
- SSH daemon failed to start

**How to check:**
- Check if server is powered on (LEDs, fans)
- Try accessing via web interface if available
- Check if other services are responding

**Solution:** Physically access server or use IPMI/KVM to check status

### 3. **Windows Network Adapter Changed**
**What happened:** Your Windows machine switched networks
- Connected to different WiFi network
- Ethernet cable unplugged/switched
- VPN connected/disconnected
- Network adapter disabled

**How to check:**
```cmd
ipconfig
```
Look at your IP address - are you still on `192.168.1.x`?

**Solution:** Ensure you're on the correct network

### 4. **Firewall Rule Changed**
**What happened:** Firewall started blocking SSH
- Windows Firewall update
- Antivirus software update
- Router firewall rule changed
- Server firewall rule changed

**How to check:**
- Windows Firewall: Check recent changes
- Router: Check firewall logs
- Server: Check if SSH port is still open

**Solution:** Temporarily disable firewall to test, then re-enable with proper rules

### 5. **Router Configuration Changed**
**What happened:** Router settings were modified
- AP isolation enabled (devices can't talk to each other)
- Guest network isolation
- Port forwarding rules removed
- DHCP range changed

**How to check:**
- Log into router admin panel
- Check AP isolation settings
- Verify DHCP settings

**Solution:** Disable AP isolation, ensure devices are on same network segment

### 6. **SSH Service Stopped on Server**
**What happened:** SSH daemon crashed or was stopped
- Systemd service failed
- SSH configuration error
- Disk full (can't write logs)
- Service manually stopped

**How to check:**
- If you have physical/console access: `systemctl status ssh`
- Check server logs
- Try other services on the server

**Solution:** Restart SSH service on server

### 7. **Network Infrastructure Change**
**What happened:** Network topology changed
- New router installed
- Network segment changed
- VLAN configuration changed
- Switch configuration changed

**How to check:**
- Verify router model/IP hasn't changed
- Check if other devices can still access server
- Verify network topology

**Solution:** Update network configuration or IP addresses

### 8. **Windows Update/System Change**
**What happened:** Windows update changed network behavior
- Network adapter driver updated
- Windows Firewall rules reset
- Network profile changed (Public vs Private)
- WSL2 network configuration changed

**How to check:**
- Check Windows Update history
- Review recent system changes
- Check network adapter status

**Solution:** Review and restore network settings

## Diagnostic Checklist

Run these checks to identify what changed:

### ✅ Check 1: Your Network Configuration
```cmd
ipconfig /all
```
- Are you on `192.168.1.x`?
- Is your default gateway correct?
- Are you on WiFi or Ethernet?

### ✅ Check 2: Can You Reach Other Devices?
```cmd
ping 192.168.1.1
```
(Replace with your router IP)
- If this fails, your network connection is the issue

### ✅ Check 3: Scan for the Server
If you have `nmap` or similar:
```cmd
nmap -sn 192.168.1.0/24
```
This will show all devices on your network and their IPs

### ✅ Check 4: Router DHCP Client List
- Log into router (usually `192.168.1.1` or `192.168.0.1`)
- Check DHCP client list
- Look for your server's hostname or MAC address
- Note the current IP address

### ✅ Check 5: Check Recent Changes
- When did SSH last work?
- What changed since then?
  - Windows updates?
  - Router restart?
  - Server restart?
  - Network cable moved?
  - WiFi network changed?

## Most Likely Scenarios (In Order)

1. **Server IP changed** (DHCP lease renewal) - 60% probability
2. **Server restarted and SSH didn't start** - 20% probability  
3. **Windows network adapter changed** - 10% probability
4. **Firewall rule changed** - 5% probability
5. **Router configuration changed** - 5% probability

## Quick Fix Attempts

### Attempt 1: Find the Server's New IP
```cmd
arp -a | findstr "192.168.1"
```
This shows recent ARP entries - might reveal the server's MAC address

### Attempt 2: Try Common Alternative IPs
If the server IP changed, it's likely nearby:
- `192.168.1.225`
- `192.168.1.226`
- `192.168.1.230`
- `192.168.1.200`

### Attempt 3: Check Router Admin Panel
Most routers show connected devices with their hostnames

## Next Steps

1. **Check router DHCP client list** - This is the fastest way to find the new IP
2. **Verify your Windows machine is on the correct network**
3. **Check if server is powered on and running**
4. **Try pinging the router** to verify basic connectivity

The most common cause is the server's IP address changed due to DHCP. Check your router's admin panel first!

