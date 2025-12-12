# Step 7: DNS & DHCP Security – Risk Assessment

**Date**: 2025-12-12  
**Status**: BLOCKED - Manual Changes Required (MCP Read-Only)

---

## 1. Scope

This step secures DNS and DHCP services:
- Identify misconfigurations
- Disable NAT-PMP
- Enforce secure DNS servers
- Configure DHCP settings per VLAN

---

## 2. Current State (from MCP tools)

### 2.1 DNS/DHCP Settings

| Setting | Status |
|---------|--------|
| UPnP | ❌ Disabled |
| NAT-PMP | ⚠️ Enabled |
| DNS Filtering | ✅ Enabled |

### 2.2 DHCP Configuration by Network

| Network | Subnet | DHCP | Range |
|---------|--------|------|-------|
| Yellow Brick Road | 192.168.1.0/24 | ✅ | Configured |
| Emerald City | 192.168.2.0/24 | ✅ | Configured |
| Munchkin Land | 192.168.3.0/24 | ✅ | Configured |
| WWWest | 192.168.4.0/24 | ✅ | Configured |

### 2.3 Security Finding

| Finding | Severity | Issue |
|---------|----------|-------|
| F014 | HIGH | NAT-PMP is enabled |

---

## 3. Proposed Changes

### 3.1 Disable NAT-PMP

| Setting | Current | Target |
|---------|---------|--------|
| NAT-PMP | Enabled | Disabled |

NAT-PMP allows automatic port forwarding, which is a security risk.

### 3.2 Configure DNS for New VLANs

When IoT and Guest VLANs are created:
- Use gateway as DNS server
- Enable DNS filtering

---

## 4. API Access Issue

**CRITICAL**: MCP server has **READ-ONLY** access to UniFi controller.

Changes must be applied manually.

---

## 5. Manual Configuration Instructions

### 5.1 Disable NAT-PMP

1. UniFi Controller → Settings → Security
2. Find "Port Forwarding" or "UPnP" section
3. Disable "NAT-PMP"
4. Verify UPnP is also disabled
5. Click "Apply"

### 5.2 Configure DNS for IoT VLAN

When IoT VLAN is created:
1. UniFi Controller → Settings → Networks
2. Click on "IoT"
3. DNS settings:
   - Use Gateway DNS (recommended)
   - Or set specific DNS: 1.1.1.3, 1.0.0.3 (Cloudflare filtered)
4. Click "Apply"

### 5.3 Configure DNS for Guest VLAN

When Guest VLAN is created:
1. UniFi Controller → Settings → Networks
2. Click on "Guest"
3. DNS settings:
   - Use Gateway DNS (filtered)
4. Click "Apply"

---

## 6. Rollback Plan

### 6.1 If NAT-PMP Disable Breaks Applications

Some applications (like game consoles) rely on NAT-PMP:
1. UniFi Controller → Settings → Security
2. Re-enable NAT-PMP temporarily
3. Create manual port forwards for specific devices
4. Disable NAT-PMP again

### 6.2 Impact Assessment

| Device Type | NAT-PMP Impact |
|-------------|----------------|
| Game consoles | May need manual port forwards |
| VoIP phones | Usually unaffected |
| Smart TVs | Usually unaffected |
| General browsing | Unaffected |

---

## 7. Summary

### 7.1 Changes Applied via MCP

| Change | Status |
|--------|--------|
| Disable NAT-PMP | ❌ BLOCKED |
| Configure DNS | ❌ BLOCKED |

### 7.2 Manual Actions Required

- [ ] Disable NAT-PMP
- [ ] Configure DNS for new VLANs (after creation)

---

**Step 7 Status**: ⚠️ BLOCKED - Manual intervention required

