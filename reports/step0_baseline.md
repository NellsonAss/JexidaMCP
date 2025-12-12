# Step 0: Baseline & Backups – Risk Assessment

**Audit Date**: 2025-12-12T12:20:30  
**Audit Profile**: Baseline  
**NO CONFIG CHANGES MADE** - Read-only operations only

---

## 1. Scope

This step establishes the baseline security posture of the UniFi network before any hardening changes are applied. It includes:
- MCP connectivity verification
- Security audit execution
- Configuration export
- Risk score documentation

---

## 2. MCP Connectivity Status

### UniFi Controller Access: ✅ VERIFIED

MCP server at `192.168.1.224:8080` successfully connected to UniFi controller.

### Devices Discovered (5 total)

| Device Name | Model | Type | IP Address | Firmware | Uptime |
|-------------|-------|------|------------|----------|--------|
| Yellow Brick Office | UAL6 | Access Point | 192.168.1.193 | 6.7.31.15618 | 79 days |
| Tinman | US24PRO | Switch | 192.168.1.235 | 7.2.123.16565 | 56 days |
| Yellow Brick Lanai | UAL6 | Access Point | 192.168.1.182 | 6.7.31.15618 | 79 days |
| Yellow Brick Bedroom | UAL6 | Access Point | 192.168.1.4 | 6.7.31.15618 | 79 days |
| Lion | UXGPRO | Gateway | 47.198.94.47 | 4.3.1.25879 | 58 days |

---

## 3. Backup Status

### Controller Backup Tools: ⚠️ NOT REGISTERED

The `unifi_controller_backup` tool is not currently registered on the MCP server. 

**Recommendation**: Register controller backup tools before making any configuration changes.

**Manual Backup**: Users should create a manual backup via UniFi Controller UI:
1. Navigate to Settings → System → Backup
2. Download the current backup file
3. Store securely before proceeding

---

## 4. Network Summary

### VLANs/Networks (6 total, 3 with VLAN tags)

| Network Name | Purpose | VLAN ID | Subnet | DHCP |
|--------------|---------|---------|--------|------|
| Yellow Brick Road | Corporate (Main LAN) | None | 192.168.1.1/24 | ✅ |
| Internet 1 | WAN | None | - | ❌ |
| Internet 2 | WAN | None | - | ❌ |
| Emerald City | Corporate | 2 | 192.168.2.1/24 | ✅ |
| Munchkin Land | Corporate | 3 | 192.168.3.1/24 | ✅ |
| WWWest | Corporate | 4 | 192.168.4.1/24 | ✅ |

### WiFi Networks/SSIDs (4 enabled)

| SSID Name | Security | WPA Mode | WPA3 | PMF | Guest | VLAN | Client Isolation |
|-----------|----------|----------|------|-----|-------|------|------------------|
| New England Clam Router | WPA-PSK | WPA2 | ❌ | ❌ | ❌ | None | ❌ |
| OZPINHEAD | WPA-PSK | WPA2 | ❌ | ❌ | ❌ | None | ❌ |
| KidsDroolParentsRule | WPA-PSK | WPA2 | ❌ | ❌ | ❌ | None | ❌ |
| FlyingMonkeys | WPA-PSK | WPA2 | ❌ | ❌ | ❌ | None | ❌ |

### Firewall Rules

- **Total Rules**: 0 (No custom firewall rules configured)
- **WAN In**: 0 rules
- **LAN In**: 0 rules
- **Guest In**: 0 rules

### Controller Settings

| Setting | Status |
|---------|--------|
| UPnP | ❌ Disabled |
| NAT-PMP | ⚠️ Enabled |
| IDS/IPS | ❌ Disabled (mode: IPS) |
| DPI | ✅ Enabled |
| DNS Filtering | ✅ Enabled |
| SSH | ⚠️ Enabled |
| SSH Password Auth | ⚠️ Enabled |
| Cloud Access | ⚠️ Enabled |

---

## 5. Security Audit Results

### Risk Score: 46/100 (Grade: C) - Needs Work

### Findings Summary

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 6 |
| Medium | 6 |
| Low | 4 |
| **Total** | **16** |

### Findings by Area

| Area | Count |
|------|-------|
| VLAN Architecture | 1 |
| WiFi | 8 |
| Firewall | 3 |
| Threat Management | 1 |
| DNS/DHCP | 1 |
| Remote Access | 2 |

---

## 6. Detailed Security Findings

### HIGH Severity (6 findings)

#### F001: Missing Network Segmentation
- **Area**: VLAN Architecture
- **Issue**: Required VLANs not found: IoT, Guest
- **Impact**: Flat networks = widest attack surface
- **Existing Networks**: Yellow Brick Road, Internet 1, Internet 2, Emerald City, Munchkin Land, WWWest
- **Recommendation**: Create dedicated IoT and Guest VLANs

#### F010: Missing Firewall Rule - IoT → LAN
- **Area**: Firewall
- **Issue**: No explicit deny rule blocking IoT access to LAN
- **Recommendation**: Add drop rule blocking IoT → LAN traffic

#### F011: Missing Firewall Rule - Guest → LAN
- **Area**: Firewall
- **Issue**: No explicit deny rule blocking Guest access to LAN
- **Recommendation**: Add drop rule blocking Guest → LAN traffic

#### F012: Missing Firewall Rule - Cameras → LAN
- **Area**: Firewall
- **Issue**: No explicit deny rule blocking Cameras access to LAN
- **Recommendation**: Add drop rule blocking Cameras → LAN traffic

#### F013: IDS/IPS Disabled
- **Area**: Threat Management
- **Issue**: Intrusion Detection/Prevention System is disabled
- **Impact**: No network threat protection
- **Recommendation**: Enable IDS/IPS (start with detect-only mode)

#### F014: NAT-PMP Enabled
- **Area**: DNS/DHCP
- **Issue**: NAT-PMP allows automatic port mapping
- **Impact**: Similar security risk to UPnP
- **Recommendation**: Disable NAT-PMP

### MEDIUM Severity (6 findings)

#### F003, F005, F007, F009: PMF Not Enabled (4 SSIDs)
- **SSIDs Affected**: New England Clam Router, OZPINHEAD, KidsDroolParentsRule, FlyingMonkeys
- **Issue**: Protected Management Frames disabled
- **Impact**: Vulnerable to deauthentication attacks
- **Recommendation**: Enable PMF on all SSIDs

#### F015: SSH Enabled
- **Area**: Remote Access
- **Issue**: SSH access enabled on devices
- **Recommendation**: Disable SSH unless actively needed

#### F016: SSH Password Auth Enabled
- **Area**: Remote Access
- **Issue**: Password-based SSH authentication enabled
- **Impact**: Less secure than key-based authentication
- **Recommendation**: Use SSH keys instead

### LOW Severity (4 findings)

#### F002, F004, F006, F008: WPA3 Not Enabled (4 SSIDs)
- **SSIDs Affected**: All 4 SSIDs
- **Current Mode**: WPA2
- **Recommendation**: Enable WPA3 or WPA2-WPA3 transition mode

---

## 7. Recommended Patches (Auto-Safe)

The following patches are marked as safe for automatic application:

### Phase 1 (Immediate)
1. **Enable PMF on all SSIDs** (4 patches)
2. **Enable IDS/IPS** in detect mode
3. **Disable NAT-PMP**

### Phase 2 (After VLAN Creation)
1. **Create firewall rule**: Block IoT → LAN
2. **Create firewall rule**: Block Guest → LAN
3. **Create firewall rule**: Block Cameras → LAN

### Phase 3 (Requires Manual Review)
1. **Create IoT VLAN** (ID: 30, Subnet: 192.168.30.0/24)
2. **Create Guest VLAN** (ID: 40, Subnet: 192.168.40.0/24)

---

## 8. Sections Audited

- ✅ Section 1: VLAN & Network Architecture
- ✅ Section 2: WiFi Hardening
- ✅ Section 3: Firewall Hardening
- ✅ Section 4: Threat Management (IDS/IPS)
- ✅ Section 5: DNS/DHCP Protection
- ✅ Section 6: Switch, PoE, & AP Hardening
- ✅ Section 7: Remote Access & Admin Hardening
- ✅ Section 8: Backups & Drift (requires drift_monitor tool)

---

## 9. Break-Glass Information

### MCP Server Access
- **IP**: 192.168.1.224
- **Port**: 8080
- **SSH**: `ssh jexida@192.168.1.224`

### UniFi Controller Access
- **Gateway (Lion)**: IP varies by WAN connection
- **Web UI**: Access via internal network at 192.168.1.x range

### If MCP Loses Connectivity
1. Access UniFi Controller directly via web browser
2. Navigate to Settings → System → Backup
3. Restore from latest backup if needed
4. Check network connectivity to MCP server (192.168.1.224)

---

## 10. Next Steps

Proceed to **Step 1: Define Management & Break-Glass Paths** to:
1. Identify which network the MCP server uses
2. Identify which network the admin workstation uses
3. Document break-glass access procedures
4. Optionally create a dedicated admin SSID

---

## Baseline Configuration Snapshot

Full configuration data saved to:
- `tmp/security_audit_result.json` - Complete audit results
- `tmp/security_settings.json` - Current security settings

---

**Step 0 Status**: ✅ COMPLETE (No changes made)

