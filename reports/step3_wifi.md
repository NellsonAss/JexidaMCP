# Step 3: WiFi Hardening – Risk Assessment

**Date**: 2025-12-12  
**Status**: PARTIAL - Manual Changes Required

---

## 1. Scope

This step hardens WiFi security settings:
- Remove unused SSIDs
- Enforce WPA2/WPA3 where possible
- Enable Protected Management Frames (PMF)
- Enable guest isolation where appropriate

---

## 2. Current State (from MCP tools)

### 2.1 SSID Inventory

| SSID | Enabled | Security | WPA Mode | WPA3 | PMF | VLAN | Client Isolation |
|------|---------|----------|----------|------|-----|------|------------------|
| New England Clam Router | ✅ | WPA-PSK | WPA2 | ❌ | ❌ Disabled | None | ❌ |
| OZPINHEAD | ✅ | WPA-PSK | WPA2 | ❌ | ❌ Disabled | None | ❌ |
| KidsDroolParentsRule | ✅ | WPA-PSK | WPA2 | ❌ | ❌ Disabled | None | ❌ |
| FlyingMonkeys | ✅ | WPA-PSK | WPA2 | ❌ | ❌ Disabled | None | ❌ |

### 2.2 Security Findings

| Finding | Severity | SSID | Issue |
|---------|----------|------|-------|
| F002, F004, F006, F008 | LOW | All 4 SSIDs | WPA3 not enabled |
| F003, F005, F007, F009 | MEDIUM | All 4 SSIDs | PMF not enabled |

### 2.3 All SSIDs Are In Use

Based on client analysis, all 4 SSIDs have connected devices:
- **New England Clam Router**: 10+ devices (phones, laptops, printers)
- **OZPINHEAD**: 2 devices (Galaxy phones on VLAN 2)
- **KidsDroolParentsRule**: 4 devices (tablets, TVs)
- **FlyingMonkeys**: 15+ devices (smart plugs, speakers, IoT)

**No SSIDs can be removed** - all are actively in use.

---

## 3. Proposed Changes

### 3.1 Safe Changes (Auto-Apply Attempted)

| Change | SSID | Description | Status |
|--------|------|-------------|--------|
| Enable PMF | New England Clam Router | Set pmf_mode to "required" | ⚠️ BLOCKED |
| Enable PMF | OZPINHEAD | Set pmf_mode to "required" | ⚠️ BLOCKED |
| Enable PMF | KidsDroolParentsRule | Set pmf_mode to "required" | ⚠️ BLOCKED |
| Enable PMF | FlyingMonkeys | Set pmf_mode to "required" | ⚠️ BLOCKED |

### 3.2 API Access Issue

**CRITICAL**: MCP server has **READ-ONLY** access to UniFi controller.

All write operations failed with:
```
API request failed: {"error":{"code":403,"message":"Forbidden"}}
```

This affects:
- WiFi configuration changes
- Firewall rule creation
- VLAN creation
- UPnP/NAT-PMP settings changes

---

## 4. Risk Analysis

### 4.1 Current Risk Level: MEDIUM

| Risk | Impact | Status |
|------|--------|--------|
| PMF not enabled | Vulnerable to deauth attacks | Unmitigated |
| WPA3 not enabled | Legacy security only | Low priority |
| All devices on main LAN | Flat network | Unmitigated |

### 4.2 Mitigation Required

The following options are available:

**Option A: Fix MCP API Credentials** (Recommended)
1. Update UniFi API credentials on MCP server to use an account with write permissions
2. Re-run hardening steps

**Option B: Manual Configuration**
1. Apply changes via UniFi Controller UI
2. Document changes in this report

---

## 5. Manual Configuration Instructions

Since MCP cannot write to the UniFi controller, apply these changes manually:

### 5.1 Enable PMF on All SSIDs

For each SSID, navigate to:
1. UniFi Controller → Settings → WiFi
2. Click on the SSID name
3. Expand "Advanced" section
4. Set "Protected Management Frames" to **Required**
5. Click "Apply Changes"

Apply to:
- [ ] New England Clam Router
- [ ] OZPINHEAD
- [ ] KidsDroolParentsRule
- [ ] FlyingMonkeys

### 5.2 Optional: Enable WPA2-WPA3 Transition Mode

For better security while maintaining compatibility:
1. UniFi Controller → Settings → WiFi
2. Click on the SSID name
3. Under "Security Protocol", select "WPA2/WPA3"
4. Click "Apply Changes"

**Note**: Some older devices may not support WPA3. Test on non-critical SSIDs first.

### 5.3 Optional: Enable Client Isolation on FlyingMonkeys

Since FlyingMonkeys is used for IoT devices:
1. UniFi Controller → Settings → WiFi
2. Click on "FlyingMonkeys"
3. Enable "Client Isolation"
4. Click "Apply Changes"

This prevents IoT devices from communicating with each other.

---

## 6. Rollback Plan

### 6.1 If PMF Causes Device Connectivity Issues

Some older devices may not support PMF. If devices cannot connect after enabling PMF:

1. UniFi Controller → Settings → WiFi
2. Click on the affected SSID
3. Set "Protected Management Frames" to **Optional** or **Disabled**
4. Click "Apply Changes"
5. Wait 30 seconds for APs to update
6. Reconnect device

### 6.2 Device Compatibility

| Device Type | PMF Support |
|-------------|-------------|
| iPhones (2017+) | ✅ Supported |
| Android (8.0+) | ✅ Supported |
| Windows 10/11 | ✅ Supported |
| macOS (2018+) | ✅ Supported |
| Older Smart Devices | ⚠️ May not support |
| IoT devices | ⚠️ Check manufacturer |

---

## 7. Post-Change Verification

### 7.1 Changes Applied via MCP

| Change | Status |
|--------|--------|
| Enable PMF on all SSIDs | ❌ BLOCKED (403 Forbidden) |
| Disable NAT-PMP | ❌ BLOCKED (403 Forbidden) |
| Remove unused SSIDs | N/A (all in use) |

### 7.2 Verification Commands

After manual changes, run security audit to verify:

```powershell
$response = Invoke-RestMethod -Uri "http://192.168.1.224:8080/tools/api/tools/security_audit_unifi/run/" -Method POST -ContentType "application/json" -Body '{"depth": "full", "profile": "baseline"}'
$response.result.findings | Where-Object { $_.code -like "NO_PMF*" }
```

Expected: No findings with code "NO_PMF" after enabling PMF.

---

## 8. Remediation for MCP Write Access

### 8.1 Check UniFi Account Permissions

The MCP server's UniFi credentials may be read-only. To fix:

1. Log into UniFi Controller
2. Navigate to Settings → Admins & Users
3. Find the account used by MCP (check `.env` on MCP server)
4. Ensure role is "Super Admin" or has write permissions
5. Restart MCP service after credential update

### 8.2 Update MCP Environment

On the MCP server, check credentials:

```bash
ssh jexida@192.168.1.224
cat /opt/jexida-mcp/.env | grep -i unifi
```

Verify:
- `UNIFI_USERNAME` has admin access
- `UNIFI_PASSWORD` is correct
- `UNIFI_HOST` is correct

---

## 9. Summary

### 9.1 Step 3 Status

| Task | Status |
|------|--------|
| Identify unused SSIDs | ✅ Complete (none found) |
| Enable PMF | ⚠️ Manual required |
| Enable WPA3 | ⏸️ Optional (low priority) |
| Enable guest isolation | ⏸️ Optional |
| MCP write access | ❌ Not working |

### 9.2 Action Items

1. **Fix MCP API Access** (Priority: HIGH)
   - Check UniFi admin account permissions
   - Update MCP credentials if needed
   - Restart MCP service

2. **Manual WiFi Hardening** (if MCP not fixable)
   - Enable PMF on all SSIDs via UniFi UI
   - Document completion in this report

### 9.3 Devices Affected

**NONE** - No changes were applied.

All existing devices remain connected to their current SSIDs with no disruption.

---

**Step 3 Status**: ⚠️ BLOCKED - Manual intervention required

