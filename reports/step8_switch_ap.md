# Step 8: Switch & AP Hardening – Risk Assessment

**Date**: 2025-12-12  
**Status**: ANALYSIS COMPLETE - Manual Changes Required (MCP Read-Only)

---

## 1. Scope

This step hardens switch and access point settings:
- Identify unused ports
- Disable or assign unused ports to a "dead" VLAN
- Restrict SSH/management access

---

## 2. Current State (from MCP tools)

### 2.1 Device Inventory

| Device | Model | Type | IP | Ports |
|--------|-------|------|-----|-------|
| Yellow Brick Office | UAL6 | AP | 192.168.1.193 | N/A |
| Tinman | US24PRO | Switch | 192.168.1.235 | 24 |
| Yellow Brick Lanai | UAL6 | AP | 192.168.1.182 | N/A |
| Yellow Brick Bedroom | UAL6 | AP | 192.168.1.4 | N/A |
| Lion | UXGPRO | Gateway | 192.168.1.1 | 8 |

### 2.2 SSH Settings

| Setting | Status |
|---------|--------|
| SSH Enabled | ⚠️ Yes |
| SSH Password Auth | ⚠️ Yes |

### 2.3 Security Findings

| Finding | Severity | Issue |
|---------|----------|-------|
| F015 | MEDIUM | SSH enabled on devices |
| F016 | MEDIUM | SSH password authentication enabled |

---

## 3. Proposed Changes

### 3.1 Disable SSH (If Not Needed)

| Setting | Current | Target |
|---------|---------|--------|
| SSH Enabled | Yes | No (or key-only) |
| SSH Password Auth | Yes | No |

### 3.2 Switch Port Security

For unused ports on Tinman switch:
- Assign to "disabled" or "dead" VLAN
- Or administratively disable

---

## 4. API Access Issue

**CRITICAL**: MCP server has **READ-ONLY** access to UniFi controller.

Changes must be applied manually.

---

## 5. Manual Configuration Instructions

### 5.1 Disable SSH (Recommended)

1. UniFi Controller → Settings → System
2. Find "Device Authentication" or "Advanced"
3. Disable SSH or set to key-only
4. Click "Apply"

**Note**: Disabling SSH means you cannot SSH directly to UniFi devices. All management goes through the controller UI.

### 5.2 Identify Unused Switch Ports

1. UniFi Controller → Devices
2. Click on "Tinman" (US24PRO)
3. Go to "Ports" tab
4. Review port status:
   - "Connected" = in use
   - "Disconnected" = potentially unused
5. For each unused port, note the port number

### 5.3 Disable Unused Ports

For each unused port:
1. Click on the port
2. Set "Port Profile" to "Disabled"
3. Click "Apply"

### 5.4 Create Dead VLAN (Alternative)

If you prefer to keep ports active but isolated:
1. Create a new VLAN "Dead" (ID: 999)
2. No DHCP, no gateway
3. Assign unused ports to this VLAN

---

## 6. Rollback Plan

### 6.1 If Port Disable Causes Issues

1. UniFi Controller → Devices → Tinman
2. Find the disabled port
3. Set "Port Profile" to "All"
4. Click "Apply"

### 6.2 Re-enable SSH

If SSH is needed for troubleshooting:
1. UniFi Controller → Settings → System
2. Re-enable SSH
3. Connect via SSH to device
4. Disable SSH when done

---

## 7. Summary

### 7.1 Changes Applied via MCP

| Change | Status |
|--------|--------|
| Disable SSH | ❌ BLOCKED |
| Disable unused ports | ❌ BLOCKED |

### 7.2 Manual Actions Required

- [ ] Review switch ports and identify unused
- [ ] Disable unused ports or assign to dead VLAN
- [ ] Disable SSH if not needed
- [ ] If SSH needed, use key-only authentication

---

**Step 8 Status**: ⚠️ BLOCKED - Manual intervention required

