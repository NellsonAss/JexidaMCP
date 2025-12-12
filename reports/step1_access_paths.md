# Step 1: Define Management & Break-Glass Paths – Risk Assessment

**Date**: 2025-12-12  
**Status**: Documentation Only (No Changes)

---

## 1. Scope

This step identifies and documents all critical management access paths to ensure:
- MCP server maintains connectivity during hardening
- Admin workstation has break-glass access
- UniFi controller remains reachable
- Recovery procedures are clearly defined

---

## 2. Current State (from MCP tools)

### 2.1 Management Device Network Assignments

| Device | IP Address | Network/SSID | Connection Type | Role |
|--------|------------|--------------|-----------------|------|
| **jexidamcp** (MCP Server) | 192.168.1.224 | Yellow Brick Road | Wired | MCP Automation Server |
| **Lion** (UniFi Gateway) | 192.168.1.1 (LAN) | Yellow Brick Road | Gateway | Network Controller |
| **Tinman** (Switch) | 192.168.1.235 | Yellow Brick Road | Wired | Core Switch |
| **unifi** | 192.168.1.83 | Yellow Brick Road | Wired | UniFi Management |
| **DESKTOP-DU7FO19** | 192.168.1.86 | New England Clam Router | WiFi | Admin Workstation (presumed) |

### 2.2 Management Network Details

**Primary Management Network**: Yellow Brick Road
- **Subnet**: 192.168.1.0/24
- **VLAN**: None (untagged/native)
- **DHCP**: Enabled
- **Purpose**: Main LAN with all management devices

**Key Observations**:
1. MCP server is on the main LAN (Yellow Brick Road) - wired connection
2. UniFi Gateway (Lion) management interface is on the main LAN
3. Core switch (Tinman) is on the main LAN
4. Admin workstation connects via "New England Clam Router" SSID (same 192.168.1.x subnet)

### 2.3 Access Paths Diagram

```
Internet
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  Lion (UXGPRO Gateway) - 192.168.1.1                        │
│  UniFi Controller: https://192.168.1.1                      │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  Tinman (US24PRO Switch) - 192.168.1.235                    │
│  Yellow Brick Road (Main LAN) - 192.168.1.0/24              │
└─────────────────────────────────────────────────────────────┘
    │
    ├──► jexidamcp (MCP Server) - 192.168.1.224 [WIRED]
    │    └── SSH: jexida@192.168.1.224
    │    └── API: http://192.168.1.224:8080
    │
    ├──► nas (Synology) - 192.168.1.52, 192.168.1.53 [WIRED]
    │
    └──► Access Points (UAL6 x3)
         ├── Yellow Brick Office - 192.168.1.193
         ├── Yellow Brick Lanai - 192.168.1.182
         └── Yellow Brick Bedroom - 192.168.1.4
              │
              └──► New England Clam Router SSID
                   └── DESKTOP-DU7FO19 (Admin) - 192.168.1.86
```

---

## 3. Break-Glass Procedures

### 3.1 Primary Access: MCP Server

**Normal Operation**:
```bash
# From admin workstation
ssh jexida@192.168.1.224

# API access
curl http://192.168.1.224:8080/tools/api/tools/
```

**If MCP Server Unreachable**:
1. Verify admin workstation is on 192.168.1.x subnet
2. Check if MCP server is powered on
3. Try direct SSH from another device on Yellow Brick Road
4. If SSH fails, access via console if available

### 3.2 Secondary Access: UniFi Controller Direct

**Normal Operation**:
- Access UniFi Controller at `https://192.168.1.1` from any device on Yellow Brick Road

**Break-Glass Procedure**:
1. Connect admin workstation via Ethernet directly to switch
2. Ensure static IP in 192.168.1.x range (e.g., 192.168.1.99)
3. Access `https://192.168.1.1` via browser
4. Login with UniFi credentials
5. Navigate to Settings → System → Backup
6. Restore from latest backup if needed

### 3.3 Emergency Network Recovery

**If Unable to Access Controller via Network**:
1. Connect laptop directly to Gateway (Lion) console port
2. Access local management interface
3. Reset network to factory defaults (last resort)
4. Restore from offline backup

### 3.4 Critical IP Addresses

| Resource | IP Address | Access Method |
|----------|------------|---------------|
| UniFi Controller | 192.168.1.1 | HTTPS (web UI) |
| MCP Server | 192.168.1.224 | SSH / HTTP:8080 |
| Core Switch | 192.168.1.235 | SSH / UniFi |
| NAS (Primary) | 192.168.1.52 | DSM Web UI |

---

## 4. Risk Analysis

### 4.1 Current Risks

| Risk | Severity | Description |
|------|----------|-------------|
| Flat Network | Medium | All devices share same subnet; no VLAN isolation |
| Single Point of Failure | Medium | Main LAN failure affects all management |
| No Dedicated Management VLAN | Low | Management traffic mixed with user traffic |

### 4.2 Mitigation During Hardening

1. **Never modify Yellow Brick Road network** - This is the management network
2. **Never change SSID VLAN assignments** for existing SSIDs
3. **Test connectivity after each change** before proceeding
4. **Keep break-glass device on main LAN** at all times

---

## 5. Preconditions & Tests

### 5.1 Verification Tests (Run Before Each Step)

```powershell
# Test 1: MCP API Connectivity
Invoke-RestMethod -Uri "http://192.168.1.224:8080/tools/api/tools/" -Method GET

# Test 2: UniFi Controller via MCP
Invoke-RestMethod -Uri "http://192.168.1.224:8080/tools/api/tools/unifi_list_devices/run/" -Method POST -ContentType "application/json" -Body '{}'

# Test 3: SSH to MCP Server
ssh jexida@192.168.1.224 "echo 'MCP SSH OK'"
```

### 5.2 Post-Change Verification

After any network change, verify:
1. MCP API responds (Test 1)
2. UniFi devices still visible (Test 2)
3. SSH access works (Test 3)

---

## 6. Rollback Plan

### 6.1 If MCP Loses Controller Access

1. Access UniFi Controller directly via `https://192.168.1.1`
2. Check recent changes in Settings → System → Backup
3. Revert last change manually via UI
4. If needed, restore from backup

### 6.2 If Admin Loses Network Access

1. Connect directly to switch via Ethernet
2. Set static IP: 192.168.1.99/24, Gateway: 192.168.1.1
3. Access controller at `https://192.168.1.1`
4. Disable any blocking firewall rules
5. Re-enable MCP server access

### 6.3 Complete Network Recovery

1. Factory reset Gateway (hold reset button 10+ seconds)
2. Connect directly via default IP (192.168.1.1)
3. Re-adopt all devices
4. Restore from backup file

---

## 7. Post-Change Verification

### 7.1 Changes Made This Step

**NONE** - This step is documentation only.

### 7.2 Recommendations for Future Steps

1. **Do NOT create a separate management VLAN** at this time
   - Risk of disrupting MCP access outweighs benefit
   - Current setup is functional for hardening

2. **Do NOT create a separate admin SSID** at this time
   - Admin workstation on "New England Clam Router" is sufficient
   - Same subnet as management devices

3. **Preserve the following during all steps**:
   - Yellow Brick Road network (192.168.1.0/24)
   - New England Clam Router SSID configuration
   - MCP server IP (192.168.1.224)
   - Gateway IP (192.168.1.1)

---

## 8. Device Inventory for Protection

### 8.1 Devices That MUST Remain Accessible

| Device | IP | Must Reach | Critical For |
|--------|-----|------------|--------------|
| jexidamcp | 192.168.1.224 | Gateway, Internet | MCP automation |
| Lion | 192.168.1.1 | All devices | Network control |
| Tinman | 192.168.1.235 | All ports | Switch management |
| Admin Workstation | 192.168.1.86 | MCP, Gateway | Break-glass access |

### 8.2 SSIDs That MUST NOT Be Moved to Different VLANs

| SSID | Current VLAN | Reason |
|------|--------------|--------|
| New England Clam Router | None (main LAN) | Admin workstation access |
| OZPINHEAD | None (main LAN) | User connectivity |
| KidsDroolParentsRule | None (main LAN) | User connectivity |
| FlyingMonkeys | None (main LAN) | IoT devices (move later to IoT VLAN) |

---

## 9. Summary

### Key Findings

1. **MCP Server Location**: Wired on Yellow Brick Road (192.168.1.224)
2. **Break-Glass Device**: Admin workstation on New England Clam Router SSID
3. **Controller Access**: Direct via https://192.168.1.1
4. **Risk Level**: LOW - All management on same reliable LAN

### Constraints for Remaining Steps

- ✅ Yellow Brick Road network: NEVER modify
- ✅ Existing SSID VLAN assignments: NEVER change
- ✅ Gateway IP (192.168.1.1): PRESERVE
- ✅ MCP Server IP (192.168.1.224): PRESERVE
- ✅ New IoT/Guest VLANs: CREATE NEW, don't reassign existing

---

**Step 1 Status**: ✅ COMPLETE (Documentation Only)

