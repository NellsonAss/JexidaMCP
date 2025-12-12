# Step 9: Remote Access Hardening – Risk Assessment

**Date**: 2025-12-12  
**Status**: ANALYSIS COMPLETE - Manual Changes Required (MCP Read-Only)

---

## 1. Scope

This step hardens remote access configuration:
- Review VPN configuration
- Identify WAN→controller and WAN→LAN port-forwards
- Prefer VPN-based remote access
- Disable or lock down direct WAN access

---

## 2. Current State (from MCP tools)

### 2.1 Remote Access Settings

| Setting | Status | Risk |
|---------|--------|------|
| UPnP | ❌ Disabled | ✅ Good |
| NAT-PMP | ⚠️ Enabled | ⚠️ Medium |
| SSH | ⚠️ Enabled | ⚠️ Medium |
| SSH Password Auth | ⚠️ Enabled | ⚠️ Medium |
| UniFi Cloud Access | ⚠️ Enabled | ⚠️ Low-Medium |

### 2.2 Port Forwards

Based on firewall rules analysis: **No custom port forwards detected**

### 2.3 VPN Status

VPN configuration not detected in security settings.

---

## 3. Proposed Changes

### 3.1 Disable Cloud Access (Optional)

Cloud access allows remote management without VPN. Consider disabling if:
- You have VPN access to network
- You don't need remote management

### 3.2 Disable NAT-PMP

Already covered in Step 7, but critical for remote access security.

### 3.3 Enable VPN (Recommended)

If remote access is needed:
- Use built-in WireGuard or L2TP VPN
- Access controller only through VPN

---

## 4. API Access Issue

**CRITICAL**: MCP server has **READ-ONLY** access to UniFi controller.

Changes must be applied manually.

---

## 5. Manual Configuration Instructions

### 5.1 Disable Cloud Access (If VPN Available)

1. UniFi Controller → Settings → System
2. Find "Remote Access"
3. Disable "UniFi Cloud Access"
4. Click "Apply"

**Note**: This disables access via unifi.ui.com. You'll need VPN for remote access.

### 5.2 Set Up WireGuard VPN

1. UniFi Controller → Settings → Teleport & VPN
2. Enable "WireGuard"
3. Create VPN configuration
4. Download client profile
5. Install on remote devices

### 5.3 Review and Remove Port Forwards

1. UniFi Controller → Settings → Firewall & Security
2. Go to "Port Forwarding" tab
3. Review each rule:
   - If not needed, delete
   - If needed, document purpose
4. Click "Apply"

### 5.4 Create VPN-Only Management Rule

After VPN is configured:
1. Disable SSH on WAN
2. Allow management only from LAN and VPN subnets

---

## 6. Rollback Plan

### 6.1 If Cloud Access Needed Again

1. UniFi Controller → Settings → System
2. Re-enable "UniFi Cloud Access"
3. Click "Apply"

### 6.2 If VPN Causes Issues

1. Ensure local LAN access works
2. Disable VPN if needed
3. Re-enable cloud access for remote management

---

## 7. Summary

### 7.1 Changes Applied via MCP

| Change | Status |
|--------|--------|
| Review port forwards | ✅ Complete (none found) |
| Disable cloud access | ❌ BLOCKED |
| Configure VPN | ❌ BLOCKED |

### 7.2 Manual Actions Required

- [ ] Review cloud access necessity
- [ ] Set up WireGuard VPN if needed
- [ ] Disable NAT-PMP (Step 7)
- [ ] Disable SSH password auth (Step 8)
- [ ] Consider disabling cloud access after VPN setup

### 7.3 Priority Actions

| Action | Priority | Risk if Not Done |
|--------|----------|------------------|
| Disable NAT-PMP | HIGH | Automatic port mapping |
| Set up VPN | MEDIUM | Need cloud access for remote |
| Disable cloud access | LOW | Adds extra attack surface |

---

**Step 9 Status**: ⚠️ BLOCKED - Manual intervention required

