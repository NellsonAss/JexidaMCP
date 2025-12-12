# Step 2: VLAN Architecture Evaluation – Risk Assessment

**Date**: 2025-12-12  
**Status**: PLANNING ONLY (No Changes)

---

## 1. Scope

This step analyzes the current VLAN architecture and proposes a target segmentation plan.

**CRITICAL CONSTRAINT**: This plan will ONLY create NEW VLANs and SSIDs. Existing SSIDs will NEVER be moved to different VLANs to ensure device connectivity is preserved.

---

## 2. Current State (from MCP tools)

### 2.1 Current Network Architecture

| Network Name | Purpose | VLAN ID | Subnet | DHCP | Device Count |
|--------------|---------|---------|--------|------|--------------|
| Yellow Brick Road | Main LAN | None (native) | 192.168.1.0/24 | ✅ | ~35 |
| Emerald City | Corporate | 2 | 192.168.2.0/24 | ✅ | 2 |
| Munchkin Land | Corporate | 3 | 192.168.3.0/24 | ✅ | 0 |
| WWWest | Corporate | 4 | 192.168.4.0/24 | ✅ | 0 |
| Internet 1 | WAN | N/A | Dynamic | ❌ | - |
| Internet 2 | WAN | N/A | Dynamic | ❌ | - |

### 2.2 Current SSID → Network Mapping

| SSID | VLAN Assignment | Network | Purpose |
|------|-----------------|---------|---------|
| New England Clam Router | None (native) | Yellow Brick Road | Primary WiFi |
| OZPINHEAD | None (native) | Yellow Brick Road | Secondary WiFi |
| KidsDroolParentsRule | None (native) | Yellow Brick Road | Kids WiFi |
| FlyingMonkeys | None (native) | Yellow Brick Road | IoT/Smart Home |

**⚠️ CRITICAL**: All SSIDs currently use the native/untagged VLAN (Yellow Brick Road). These assignments will NOT be changed.

### 2.3 Current Device Distribution by SSID

Based on connected clients analysis:

| SSID | Devices | Device Types |
|------|---------|--------------|
| **Yellow Brick Road** (wired) | 15+ | Servers, cameras, switches, NAS, MCP |
| **New England Clam Router** | 10+ | Phones, laptops, workstations, printers |
| **OZPINHEAD** | 2 | Galaxy phones (Emerald City VLAN 2) |
| **KidsDroolParentsRule** | 4 | Tablets, TVs, printer |
| **FlyingMonkeys** | 15+ | Smart plugs, speakers, IoT, cameras |

### 2.4 Security Gaps Identified

| Gap | Severity | Description |
|-----|----------|-------------|
| No IoT VLAN | HIGH | IoT devices (smart plugs, speakers) share main LAN |
| No Guest VLAN | HIGH | No isolated guest network exists |
| No Camera VLAN | MEDIUM | Cameras share main LAN with servers |
| Flat Network | HIGH | All WiFi SSIDs use same subnet |

---

## 3. Proposed Changes

### 3.1 Target VLAN Architecture

**CONSTRAINT**: Only CREATE new VLANs. Never modify existing network assignments.

| VLAN ID | Network Name | Purpose | Subnet | Create? |
|---------|--------------|---------|--------|---------|
| (native) | Yellow Brick Road | Main LAN/Management | 192.168.1.0/24 | EXISTS |
| 2 | Emerald City | Corporate | 192.168.2.0/24 | EXISTS |
| 3 | Munchkin Land | Corporate | 192.168.3.0/24 | EXISTS |
| 4 | WWWest | Corporate | 192.168.4.0/24 | EXISTS |
| **30** | **IoT** | Smart home devices | 192.168.30.0/24 | **NEW** |
| **40** | **Guest** | Guest access | 192.168.40.0/24 | **NEW** |

### 3.2 NEW SSIDs to Create (for new VLANs)

| New SSID | VLAN | Purpose | Security |
|----------|------|---------|----------|
| **IoT-Devices** | 30 (IoT) | New IoT network | WPA2-PSK |
| **Guest-WiFi** | 40 (Guest) | Guest access | WPA2-PSK, Client Isolation |

### 3.3 Existing SSIDs (DO NOT CHANGE)

| SSID | Current VLAN | Action |
|------|--------------|--------|
| New England Clam Router | Native | ❌ PRESERVE |
| OZPINHEAD | Native | ❌ PRESERVE |
| KidsDroolParentsRule | Native | ❌ PRESERVE |
| FlyingMonkeys | Native | ❌ PRESERVE |

---

## 4. Risk Analysis

### 4.1 What This Plan Does NOT Do

| Action | Reason |
|--------|--------|
| Move FlyingMonkeys to IoT VLAN | Would disconnect 15+ devices |
| Create dedicated Camera VLAN | Cameras already on wired LAN |
| Create Management VLAN | MCP server must stay on main LAN |
| Move any existing SSIDs | Violates device connectivity guarantee |

### 4.2 Risk Level: LOW

This plan only adds new networks and SSIDs. Existing devices continue to work exactly as before.

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| New VLAN conflicts with existing | Low | Medium | Use VLAN IDs 30, 40 (not in use) |
| New SSID confuses users | Low | Low | Use clear naming |
| Firewall rules block traffic | Low | Medium | Test before enforcing |

---

## 5. Migration Strategy

### 5.1 Phase 1: Create Infrastructure

1. Create IoT VLAN (ID: 30)
2. Create Guest VLAN (ID: 40)
3. Create "IoT-Devices" SSID on IoT VLAN
4. Create "Guest-WiFi" SSID on Guest VLAN

### 5.2 Phase 2: Add Firewall Rules

1. Block IoT VLAN → Main LAN (allow established)
2. Block Guest VLAN → All internal (allow internet only)
3. Allow Main LAN → IoT (for management)

### 5.3 Phase 3: Optional Device Migration (User-Initiated)

Users can OPTIONALLY move their IoT devices to the new "IoT-Devices" SSID:
- Smart plugs → IoT-Devices
- Smart speakers → IoT-Devices
- Smart TVs → IoT-Devices

**This is NOT automated. Devices only move if users reconnect them to the new SSID.**

---

## 6. Rollback Plan

### 6.1 If New VLANs Cause Issues

1. Disable the new SSID (IoT-Devices or Guest-WiFi)
2. Devices will disconnect from new SSID
3. Users reconnect to original SSID (still working)
4. Delete the new VLAN if needed

### 6.2 Rollback Steps

```
1. Disable new SSID:
   - UniFi Controller → WiFi → [New SSID] → Disable

2. Delete new SSID (if needed):
   - UniFi Controller → WiFi → [New SSID] → Delete

3. Delete new VLAN (if needed):
   - UniFi Controller → Networks → [New Network] → Delete
```

### 6.3 Impact of Rollback

- Devices on new SSID will need to reconnect to original SSIDs
- Devices on original SSIDs: NO IMPACT

---

## 7. Dependencies

### 7.1 Prerequisites for Step 4 (Implementation)

1. ✅ MCP server connectivity verified (Step 0)
2. ✅ Break-glass procedures documented (Step 1)
3. ✅ VLAN plan approved (This step)
4. ⬜ WiFi hardening complete (Step 3)

### 7.2 Network Diagram (Target State)

```
                        Internet
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Lion (Gateway) - 192.168.1.1                               │
└─────────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
            ▼               ▼               ▼
    ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
    │ Yellow Brick  │ │  IoT VLAN     │ │ Guest VLAN    │
    │ Road (Native) │ │  (NEW - 30)   │ │ (NEW - 40)    │
    │ 192.168.1.0/24│ │ 192.168.30.0  │ │ 192.168.40.0  │
    └───────────────┘ └───────────────┘ └───────────────┘
            │               │               │
    ┌───────┴───────┐       │               │
    │               │       │               │
    ▼               ▼       ▼               ▼
┌────────┐    ┌────────┐ ┌────────────┐ ┌────────────┐
│ MCP    │    │Existing│ │IoT-Devices │ │ Guest-WiFi │
│Server  │    │ SSIDs  │ │   (NEW)    │ │   (NEW)    │
└────────┘    └────────┘ └────────────┘ └────────────┘
```

---

## 8. VLAN Configuration Details

### 8.1 IoT VLAN (ID: 30)

```json
{
  "name": "IoT",
  "purpose": "corporate",
  "vlan_enabled": true,
  "vlan": 30,
  "ip_subnet": "192.168.30.1/24",
  "dhcpd_enabled": true,
  "dhcpd_start": "192.168.30.10",
  "dhcpd_stop": "192.168.30.200",
  "igmp_snooping": false
}
```

### 8.2 Guest VLAN (ID: 40)

```json
{
  "name": "Guest",
  "purpose": "guest",
  "vlan_enabled": true,
  "vlan": 40,
  "ip_subnet": "192.168.40.1/24",
  "dhcpd_enabled": true,
  "dhcpd_start": "192.168.40.10",
  "dhcpd_stop": "192.168.40.200",
  "igmp_snooping": false
}
```

### 8.3 IoT-Devices SSID

```json
{
  "name": "IoT-Devices",
  "security": "wpapsk",
  "wpa_mode": "wpa2",
  "vlan_enabled": true,
  "vlan": 30,
  "is_guest": false,
  "l2_isolation": false,
  "pmf_mode": "optional"
}
```

### 8.4 Guest-WiFi SSID

```json
{
  "name": "Guest-WiFi",
  "security": "wpapsk",
  "wpa_mode": "wpa2",
  "vlan_enabled": true,
  "vlan": 40,
  "is_guest": true,
  "l2_isolation": true,
  "pmf_mode": "optional"
}
```

---

## 9. Summary

### 9.1 What Will Be Created (Step 4)

| Item | Type | Description |
|------|------|-------------|
| IoT | VLAN 30 | New network for IoT devices |
| Guest | VLAN 40 | New network for guests |
| IoT-Devices | SSID | WiFi on IoT VLAN |
| Guest-WiFi | SSID | WiFi on Guest VLAN |

### 9.2 What Will NOT Change

| Item | Current State | Action |
|------|---------------|--------|
| Yellow Brick Road | Native LAN | PRESERVE |
| All existing SSIDs | Native VLAN | PRESERVE |
| MCP Server | 192.168.1.224 | PRESERVE |
| All existing devices | Current network | PRESERVE |

### 9.3 Device Connectivity Guarantee

✅ **All existing devices will remain on their current networks**
✅ **No SSIDs will be moved to different VLANs**
✅ **New VLANs/SSIDs are additive only**
✅ **Device migration is user-initiated, not automated**

---

**Step 2 Status**: ✅ COMPLETE (Planning Only - No Changes Made)

