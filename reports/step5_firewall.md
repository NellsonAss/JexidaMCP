# Step 5: Firewall Hardening – Risk Assessment

**Date**: 2025-12-12  
**Status**: BLOCKED - Manual Changes Required (MCP Read-Only)

---

## 1. Scope

This step hardens firewall configuration:
- Export and document current rules
- Create log-only rules for traffic to block
- Convert to blocking rules after observation
- Preserve MCP and admin access rules

---

## 2. Current State (from MCP tools)

### 2.1 Current Firewall Rules

| Ruleset | Rule Count |
|---------|------------|
| WAN In | 0 |
| WAN Out | 0 |
| WAN Local | 0 |
| LAN In | 0 |
| LAN Out | 0 |
| LAN Local | 0 |
| Guest In | 0 |
| Guest Out | 0 |
| Guest Local | 0 |

**⚠️ No custom firewall rules are configured.**

### 2.2 Security Findings

| Finding | Severity | Issue |
|---------|----------|-------|
| F010 | HIGH | Missing deny rule: IoT → LAN |
| F011 | HIGH | Missing deny rule: Guest → LAN |
| F012 | HIGH | Missing deny rule: Cameras → LAN |

---

## 3. Proposed Changes

### 3.1 Phase 1: Log-Only Rules (Observation)

Create these rules with action "Log" to observe traffic patterns:

| Rule Name | Source | Destination | Action | Purpose |
|-----------|--------|-------------|--------|---------|
| Log IoT → LAN | IoT VLAN | LAN | Log | Monitor IoT traffic |
| Log Guest → All | Guest VLAN | All Private | Log | Monitor guest traffic |

### 3.2 Phase 2: Blocking Rules (After Observation)

Convert to blocking rules after reviewing logs:

| Rule Name | Source | Destination | Action | Priority |
|-----------|--------|-------------|--------|----------|
| Block IoT → LAN | IoT VLAN | LAN | Drop | 1 |
| Block Guest → Private | Guest VLAN | RFC1918 | Drop | 2 |
| Allow Established | Any | Any | Accept (Established) | 0 |

### 3.3 Preserve Management Access

**CRITICAL**: Always allow these paths:

| Source | Destination | Port | Purpose |
|--------|-------------|------|---------|
| MCP (192.168.1.224) | Gateway | 443, 8443 | Controller API |
| Admin VLAN | Gateway | 443, 8443 | UI Access |
| All Internal | Gateway | 53 | DNS |
| All Internal | Internet | Any | Outbound |

---

## 4. API Access Issue

**CRITICAL**: MCP server has **READ-ONLY** access to UniFi controller.

All write operations fail with 403 Forbidden. Firewall rules must be created manually.

---

## 5. Manual Configuration Instructions

### 5.1 Prerequisites

Before creating blocking rules:
1. ✅ IoT VLAN exists (Step 4)
2. ✅ Guest VLAN exists (Step 4)
3. ✅ Test devices can reach gateway

### 5.2 Create IoT → LAN Block Rule

1. UniFi Controller → Settings → Firewall & Security
2. Click "Create New Rule"
3. Configure:
   - **Type**: LAN In
   - **Description**: Block IoT to LAN
   - **Action**: Drop
   - **Source**: Network - IoT
   - **Destination**: Network - Yellow Brick Road
   - **Protocol**: All
4. Click "Apply"

### 5.3 Create Guest → Private Block Rule

1. UniFi Controller → Settings → Firewall & Security
2. Click "Create New Rule"
3. Configure:
   - **Type**: Guest In
   - **Description**: Block Guest to Private Networks
   - **Action**: Drop
   - **Source**: Guest Network
   - **Destination**: RFC1918 (Private Networks)
   - **Protocol**: All
4. Click "Apply"

### 5.4 Allow MCP Server to Gateway (Safety Rule)

1. UniFi Controller → Settings → Firewall & Security
2. Click "Create New Rule"
3. Configure:
   - **Type**: LAN In
   - **Description**: Allow MCP to Gateway
   - **Rule Index**: 1 (high priority)
   - **Action**: Accept
   - **Source**: IP/Subnet - 192.168.1.224/32
   - **Destination**: Gateway IP
   - **Protocol**: TCP
   - **Port**: 443, 8443
4. Click "Apply"

---

## 6. Rollback Plan

### 6.1 If Firewall Rules Block Legitimate Traffic

1. UniFi Controller → Settings → Firewall & Security
2. Find the problematic rule
3. Either:
   - Disable the rule (toggle off)
   - Delete the rule
4. Click "Apply"

### 6.2 Emergency: Disable All Custom Rules

If locked out:
1. Access controller via direct ethernet connection
2. Navigate to Firewall & Security
3. Disable all custom rules
4. Re-enable one by one to identify the issue

---

## 7. Post-Change Verification

### 7.1 Test After Each Rule

After adding each firewall rule:

1. Verify MCP can still reach controller:
```powershell
Invoke-RestMethod -Uri "http://192.168.1.224:8080/tools/api/tools/unifi_list_devices/run/" -Method POST -ContentType "application/json" -Body '{}'
```

2. Verify affected devices can still reach internet
3. Verify blocked traffic is actually blocked

### 7.2 Verify MCP Access

```powershell
Test-NetConnection -ComputerName 192.168.1.224 -Port 8080
```

---

## 8. Summary

### 8.1 Changes Applied via MCP

| Change | Status |
|--------|--------|
| Export firewall rules | ✅ Complete (0 rules) |
| Create block rules | ❌ BLOCKED |
| Create allow rules | ❌ BLOCKED |

### 8.2 Manual Actions Required

- [ ] Create "Allow MCP to Gateway" rule first
- [ ] Create "Block IoT → LAN" rule (after IoT VLAN exists)
- [ ] Create "Block Guest → Private" rule (after Guest VLAN exists)

---

**Step 5 Status**: ⚠️ BLOCKED - Manual intervention required

