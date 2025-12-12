# Step 4: VLAN Segmentation Changes – Risk Assessment

**Date**: 2025-12-12  
**Status**: BLOCKED - Manual Changes Required (MCP Read-Only)

---

## 1. Scope

This step creates NEW VLANs and SSIDs for network segmentation.

**CRITICAL CONSTRAINT**: Only CREATE new VLANs and SSIDs. NEVER move existing SSIDs to different VLANs.

---

## 2. Current State (from MCP tools)

### 2.1 Existing VLANs

| VLAN ID | Network Name | Subnet | Purpose | Status |
|---------|--------------|--------|---------|--------|
| (native) | Yellow Brick Road | 192.168.1.0/24 | Main LAN | PRESERVE |
| 2 | Emerald City | 192.168.2.0/24 | Corporate | PRESERVE |
| 3 | Munchkin Land | 192.168.3.0/24 | Corporate | PRESERVE |
| 4 | WWWest | 192.168.4.0/24 | Corporate | PRESERVE |

### 2.2 Existing SSIDs (DO NOT CHANGE)

| SSID | VLAN | Status |
|------|------|--------|
| New England Clam Router | Native | ❌ DO NOT CHANGE |
| OZPINHEAD | Native | ❌ DO NOT CHANGE |
| KidsDroolParentsRule | Native | ❌ DO NOT CHANGE |
| FlyingMonkeys | Native | ❌ DO NOT CHANGE |

---

## 3. Proposed Changes

### 3.1 New VLANs to Create

| VLAN ID | Name | Subnet | DHCP Range | Purpose |
|---------|------|--------|------------|---------|
| 30 | IoT | 192.168.30.0/24 | .10-.200 | Smart home devices |
| 40 | Guest | 192.168.40.0/24 | .10-.200 | Guest access |

### 3.2 New SSIDs to Create

| SSID Name | VLAN | Security | Guest | Client Isolation |
|-----------|------|----------|-------|------------------|
| IoT-Devices | 30 | WPA2-PSK | ❌ | ❌ |
| Guest-WiFi | 40 | WPA2-PSK | ✅ | ✅ |

---

## 4. API Access Issue

**CRITICAL**: MCP server has **READ-ONLY** access to UniFi controller.

All write operations fail with 403 Forbidden. Changes must be applied manually.

---

## 5. Manual Configuration Instructions

### 5.1 Create IoT VLAN (ID: 30)

1. UniFi Controller → Settings → Networks
2. Click "+ Create New Network"
3. Configure:
   - **Name**: IoT
   - **Purpose**: Corporate
   - **VLAN ID**: 30
   - **Gateway/Subnet**: 192.168.30.1/24
   - **DHCP Mode**: DHCP Server
   - **DHCP Range**: 192.168.30.10 - 192.168.30.200
4. Click "Add Network"

### 5.2 Create Guest VLAN (ID: 40)

1. UniFi Controller → Settings → Networks
2. Click "+ Create New Network"
3. Configure:
   - **Name**: Guest
   - **Purpose**: Guest (enables guest policies)
   - **VLAN ID**: 40
   - **Gateway/Subnet**: 192.168.40.1/24
   - **DHCP Mode**: DHCP Server
   - **DHCP Range**: 192.168.40.10 - 192.168.40.200
4. Click "Add Network"

### 5.3 Create IoT-Devices SSID

1. UniFi Controller → Settings → WiFi
2. Click "+ Create New WiFi Network"
3. Configure:
   - **Name**: IoT-Devices
   - **Password**: [Choose a strong password]
   - **Network**: IoT (VLAN 30)
   - **Security Protocol**: WPA2
4. Expand Advanced:
   - **Protected Management Frames**: Optional
5. Click "Add WiFi Network"

### 5.4 Create Guest-WiFi SSID

1. UniFi Controller → Settings → WiFi
2. Click "+ Create New WiFi Network"
3. Configure:
   - **Name**: Guest-WiFi
   - **Password**: [Choose a guest password]
   - **Network**: Guest (VLAN 40)
   - **Security Protocol**: WPA2
4. Expand Advanced:
   - **Client Isolation**: ✅ Enabled
   - **Protected Management Frames**: Optional
5. Click "Add WiFi Network"

---

## 6. Rollback Plan

### 6.1 If New VLANs Cause Issues

1. UniFi Controller → Settings → WiFi
2. Click on "IoT-Devices" or "Guest-WiFi"
3. Click "Delete"
4. UniFi Controller → Settings → Networks
5. Click on "IoT" or "Guest"
6. Click "Delete Network"

### 6.2 Impact of Rollback

- Devices connected to new SSIDs will disconnect
- Devices on original SSIDs: NO IMPACT

---

## 7. Post-Change Verification

### 7.1 Test New Networks

After creating VLANs and SSIDs:

1. Connect a test device to "IoT-Devices" SSID
2. Verify IP address is in 192.168.30.x range
3. Verify internet access works
4. Connect a test device to "Guest-WiFi" SSID
5. Verify IP address is in 192.168.40.x range
6. Verify internet access works

### 7.2 Verify Existing Devices

Check that all existing devices remain connected:

```powershell
$response = Invoke-RestMethod -Uri "http://192.168.1.224:8080/tools/api/tools/unifi_list_clients/run/" -Method POST -ContentType "application/json" -Body '{}'
$response.result.clients | Group-Object network | Select-Object Name, Count
```

Expected: Devices should still be on their original networks.

---

## 8. Summary

### 8.1 Changes Applied via MCP

| Change | Status |
|--------|--------|
| Create IoT VLAN | ❌ BLOCKED |
| Create Guest VLAN | ❌ BLOCKED |
| Create IoT-Devices SSID | ❌ BLOCKED |
| Create Guest-WiFi SSID | ❌ BLOCKED |

### 8.2 Manual Actions Required

- [ ] Create IoT VLAN (ID: 30)
- [ ] Create Guest VLAN (ID: 40)
- [ ] Create IoT-Devices SSID
- [ ] Create Guest-WiFi SSID

### 8.3 Device Connectivity Guarantee

✅ **All existing devices will remain on their current networks**
✅ **No SSIDs will be moved to different VLANs**
✅ **New VLANs/SSIDs are additive only**

---

**Step 4 Status**: ⚠️ BLOCKED - Manual intervention required

